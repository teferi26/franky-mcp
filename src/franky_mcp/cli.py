"""Command-line entry point: ``franky-mcp`` (stdio) or ``franky-mcp --http``."""

from __future__ import annotations

import argparse
import os
import sys

from .data import ENV_DATA_DIR, DatasetError, load_dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="franky-mcp", description="MCP server for Spanish university admissions data."
    )
    parser.add_argument("--http", action="store_true", help="Serve streamable HTTP instead of stdio.")
    parser.add_argument("--host", default=os.environ.get("FRANKY_HOST", "127.0.0.1"),
                        help="HTTP bind host (default 127.0.0.1; use 0.0.0.0 inside Docker).")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FRANKY_PORT", "8000")),
                        help="HTTP port (default 8000).")
    parser.add_argument(
        "--data-dir", default=None, help=f"Dataset directory (default: ${ENV_DATA_DIR} or bundled sample)."
    )
    parser.add_argument("--check-data", action="store_true", help="Validate the dataset, print counts and exit.")
    args = parser.parse_args(argv)

    try:
        dataset = load_dataset(args.data_dir)
    except DatasetError as exc:
        print(f"franky-mcp: invalid dataset\n{exc}", file=sys.stderr)
        return 2

    if args.check_data:
        print(f"OK {dataset.path}: {dataset.counts} sample={dataset.metadata.sample}")
        return 0

    from .server import build_server

    server = build_server(dataset, host=args.host, port=args.port)
    if args.http:
        print(f"franky-mcp: streamable HTTP on http://{args.host}:{args.port}/mcp", file=sys.stderr)
        server.run(transport="streamable-http")
    else:
        server.run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
