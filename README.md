# franky-mcp

An MCP server that lets AI agents query Spanish university admissions data:
universities, degree offerings ("grados"), cut-off grades ("notas de corte") per
academic year, and scholarships ("becas"). It is modelled on the data domain of
[Franky](https://github.com/teferi26/franky-app) (franky.es), a student platform
built by Teferi Laforga.

> [!WARNING]
> **Data notice.** The bundled dataset is a **sample**. University and degree
> names are real, but **cut-off scores, scholarship amounts and income thresholds
> are illustrative, not official**. Every tool response includes a `data_notice`
> field saying so. Always check the university's (and the awarding body's)
> official publication before making a decision. This server is **not connected
> to Franky's production database**.

## What is MCP, and why a server for admissions data?

The [Model Context Protocol](https://modelcontextprotocol.io) is an open standard
for exposing tools, resources and prompts to AI applications. A client such as
Claude Code or Claude Desktop connects to an MCP server and lets the model call
its tools.

Questions like "with an 11.8, which computer science degrees in Madrid can I get
into?" need structured, filterable data and simple, exact rules (a grade over 14
compared with last year's cut-off), not a model's memory of numbers that change
every year. Putting that data behind typed tools means the agent searches,
compares and checks against a dataset, and the answer can say which academic
year it used and remind the user that the figures must be checked.

## Quick start

Requires Python 3.12+.

```bash
git clone https://github.com/teferi26/franky-mcp.git
cd franky-mcp
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/franky-mcp --check-data   # validate the bundled dataset and print counts
.venv/bin/franky-mcp                # serve over stdio (what MCP clients launch)
```

### Add to Claude Code

```bash
claude mcp add franky -- franky-mcp
```

(`franky-mcp` must be on your `PATH`; otherwise use the absolute path, e.g.
`claude mcp add franky -- /path/to/franky-mcp/.venv/bin/franky-mcp`.)

### Add to Claude Desktop

Edit `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "franky": {
      "command": "/path/to/franky-mcp/.venv/bin/franky-mcp",
      "args": [],
      "env": { "FRANKY_DATA_DIR": "/path/to/franky-mcp/data/sample" }
    }
  }
}
```

`env` is optional; without it the bundled sample is used.

### Streamable HTTP

```bash
franky-mcp --http --port 8000    # serves http://127.0.0.1:8000/mcp
```

There is no authentication on the HTTP transport. It binds to `127.0.0.1` by
default and is intended for local use only.

## Tools

All tools return JSON with a `data_notice` field. Result sizes are bounded and
invalid input produces an MCP tool error with an actionable message (e.g. an
unknown degree id suggests close matches).

| Tool | Parameters | Returns |
|---|---|---|
| `search_degrees` | `query`, `region?`, `branch?`, `university?`, `max_cutoff?` (5-14), `limit=10` (max 25) | Degrees ranked by BM25 with latest cut-off and academic year |
| `get_degree` | `degree_id` | Degree detail, university, cut-off history by year and trend |
| `compare_degrees` | `degree_ids` (2-5) | Side-by-side history, latest cut-off, trend, highest/lowest/spread |
| `admission_check` | `grade` (0-14), `degree_ids?` **or** `query?`, `limit=10` | Per degree: `above` / `below` / `no_cutoff` / `no_data`, margin, year used, band (`safe` / `match` / `reach` / `long_shot`) and a caveat that cut-offs change yearly |
| `find_scholarships` | `region?`, `level?`, `max_family_income?`, `min_grade?` (over 10), `limit=10` (max 20) | Matching schemes with `likely` / `check` eligibility and reasons, plus excluded schemes with the reason |
| `list_universities` | `region?` | Universities with city, region and number of degree offerings |

**Resources**

- `franky://dataset/metadata`: dataset version, counts, regions, branches and the sample notice.
- `franky://universities/{id}`: a university and all its degree offerings.

**Prompt**

- `plan_applications(grade, interests, region?)`: asks the model to build a
  reach / match / safe application list using `search_degrees`,
  `admission_check`, `get_degree` and `find_scholarships`.

### Domain rules

- Cut-off scores are on the Spanish PAU/EBAU admission scale **over 14** (10 from
  the access phase plus up to 4 from the specific phase); valid values are 5-14.
- Cut-offs are stored per academic year (`year: 2025` = 2025/2026); tools use
  the latest year available and report which one.
- Some degrees have **admission without cut-off** (all eligible applicants were
  admitted); `admission_check` reports them as `no_cutoff`.
- Branches: `ciencias`, `ciencias_salud`, `ingenieria_arquitectura`,
  `artes_humanidades`, `ciencias_sociales_juridicas`.
- Search and filters are accent- and case-insensitive (`informatica` matches
  `Informática`, `Andalucia` matches `Andalucía`).

## Example conversation

> **User:** I got an 11.8 in the PAU. Can I get into computer engineering in Madrid?
>
> **Claude** calls `admission_check({"grade": 11.8, "query": "informatica Madrid", "limit": 3})` and gets:
>
> | degree | 2025/26 cut-off | margin | band |
> |---|---|---|---|
> | `ucm-ingenieria-informatica` | 10.035 | +1.765 | safe |
> | `upm-ingenieria-informatica` | 10.437 | +1.363 | safe |
> | `uc3m-ingenieria-informatica` | 11.096 | +0.704 | safe |
>
> **Claude:** With 11.8 you are above the 2025/2026 cut-off of all three... These
> figures come from an illustrative sample dataset, and cut-offs change every
> year, so check each university's official publication before applying.

(The numbers above are from the sample data and are not real cut-offs.)

## How it works

```
MCP client (Claude Code / Desktop)
        │  stdio or streamable HTTP
        ▼
server.py   FastMCP: tools, resources, prompt; maps ToolInputError -> MCP tool error
        │
service.py  transport-independent tool logic (unit-tested directly), adds data_notice
   │    │
   │    └── bm25.py + normalize.py   in-repo Okapi BM25, accent/case folding, light
   │                                 stemming, Spanish stopwords and synonyms
   ▼
data.py + models.py  load JSON from FRANKY_DATA_DIR (or the bundled sample),
                     validate with pydantic, check ids and references
```

- **Search**: each degree is indexed as its name (weighted x3) plus keywords,
  branch, university name/acronym, city and region. Queries are normalized and
  expanded with a small synonym table (e.g. `informatica` -> `ingenieria
  informatica`, `ade` -> `administracion direccion empresas`, `teleco` ->
  `telecomunicacion`). Filters are applied before ranking.
- **Data**: see [docs/DATA_SCHEMA.md](docs/DATA_SCHEMA.md) for the JSON schema.
  Bad data fails at startup with the file, record path and reason.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FRANKY_DATA_DIR` | bundled `data/sample` | Dataset directory (same as `--data-dir`) |
| `FRANKY_HOST` | `127.0.0.1` | HTTP bind host (same as `--host`) |
| `FRANKY_PORT` | `8000` | HTTP port (same as `--port`) |

See `.env.example`. No secrets are needed.

## Docker

The image (python:3.12-slim, non-root user) runs the streamable HTTP transport.

```bash
docker build -t franky-mcp .
docker run --rm -p 127.0.0.1:8000:8000 franky-mcp
# MCP endpoint: http://127.0.0.1:8000/mcp
```

To use your own dataset:

```bash
docker run --rm -p 127.0.0.1:8000:8000 \
  -v "$PWD/my-data:/data:ro" -e FRANKY_DATA_DIR=/data franky-mcp
```

Publish the port on `127.0.0.1` as shown: there is no authentication.

## Running tests

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/pytest
```

The suite covers data loading and validation errors, normalization, BM25
ranking, each tool's logic, an end-to-end test that runs the server in memory
with the SDK's client session (`list_tools`, `call_tool`, resources, prompt),
and a tool-use eval: `evals/queries.jsonl` holds natural questions with the
degree ids expected in the top 5, and `tests/test_evals.py` reports recall@5 for
`search_degrees` (run `pytest tests/test_evals.py -s` to see it) and fails below
0.85. CI runs the same on Python 3.12 and 3.13.

## Project layout

```
src/franky_mcp/
  cli.py          entry point: stdio (default), --http, --check-data
  server.py       FastMCP tools, resources and prompt
  service.py      tool logic
  bm25.py         BM25 ranker
  normalize.py    accent/case normalization, stemming, stopwords, synonyms
  data.py         dataset loading and validation
  models.py       pydantic models (the schema)
data/sample/      bundled illustrative dataset (20 universities, 120 degrees, 16 schemes)
docs/DATA_SCHEMA.md
evals/queries.jsonl
scripts/generate_sample_data.py   regenerates data/sample deterministically
tests/
Dockerfile
.github/workflows/ci.yml
```

## Limitations

- **Sample data only.** Cut-off scores, scholarship amounts and thresholds are
  illustrative and generated deterministically; they are not official figures
  and must not be used for real decisions. The scholarship schemes are generic
  models of public schemes, not their actual rules.
- **Not connected to Franky's production database**, and not affiliated with
  any university or public body.
- **No authentication on the HTTP transport.** Intended for local use; do not
  expose it to a network.
- Only the latest available cut-off year is used for admission checks, a single
  round ("ordinaria") is modelled, and quotas (cupos), specific-phase weightings
  and access requirements are out of scope.
- Search is lexical (BM25 with a small synonym list), not semantic; unusual
  phrasings may need to be rephrased.

## How this was built

Built agentically with Claude Code under the direction of Teferi Laforga (@teferi26). He asked for a portfolio project tied to his own products and set the constraints (standalone, runnable, no secrets, synthetic or public data only, honest labelling). Claude Code proposed the design, wrote the code, data and tests, and ran an independent agent review; the test suite and GitHub Actions CI verify every commit. The commit history is the record of what was done.

## License

[MIT](LICENSE). Copyright (c) 2026 Teferi Laforga.
