"""End-to-end: run the real MCP server in memory and talk to it with the SDK client."""

from __future__ import annotations

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from franky_mcp.server import build_server

EXPECTED_TOOLS = {
    "search_degrees", "get_degree", "compare_degrees", "admission_check", "find_scholarships", "list_universities",
}


def _payload(result) -> dict:
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(result.content[0].text)


@pytest.mark.anyio
async def test_list_and_call_tools(dataset):
    server = build_server(dataset)
    async with create_connected_server_and_client_session(server) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools.tools}
        assert names == EXPECTED_TOOLS
        for tool in tools.tools:
            assert tool.description and len(tool.description) > 30
        search = next(t for t in tools.tools if t.name == "search_degrees")
        assert "query" in search.inputSchema["properties"]

        result = await client.call_tool("search_degrees", {"query": "informática Madrid", "limit": 3})
        assert not result.isError
        data = _payload(result)
        assert len(data["results"]) == 3
        assert "illustrative" in data["data_notice"].lower()

        result = await client.call_tool("admission_check", {"grade": 12.5, "degree_ids": ["ucm-medicina"]})
        assert not result.isError
        assert _payload(result)["results"][0]["status"] in {"above", "below"}

        for name, args in [
            ("get_degree", {"degree_id": "us-medicina"}),
            ("compare_degrees", {"degree_ids": ["us-medicina", "ugr-medicina"]}),
            ("find_scholarships", {"region": "Andalucía", "level": "grado"}),
            ("list_universities", {}),
        ]:
            result = await client.call_tool(name, args)
            assert not result.isError, name
            assert "data_notice" in _payload(result), name


@pytest.mark.anyio
async def test_tool_errors_are_reported(dataset):
    server = build_server(dataset)
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool("get_degree", {"degree_id": "ucm-medicin"})
        assert result.isError
        assert "Did you mean" in result.content[0].text

        result = await client.call_tool("compare_degrees", {"degree_ids": ["ucm-medicina"]})
        assert result.isError


@pytest.mark.anyio
async def test_resources_and_prompt(dataset):
    server = build_server(dataset)
    async with create_connected_server_and_client_session(server) as client:
        resources = await client.list_resources()
        assert "franky://dataset/metadata" in {str(r.uri) for r in resources.resources}
        templates = await client.list_resource_templates()
        assert "franky://universities/{university_id}" in {t.uriTemplate for t in templates.resourceTemplates}

        meta = json.loads((await client.read_resource("franky://dataset/metadata")).contents[0].text)
        assert meta["sample"] is True and meta["counts"]["universities"] == len(dataset.universities)

        uni = json.loads((await client.read_resource("franky://universities/usal")).contents[0].text)
        assert uni["university"]["city"] == "Salamanca"

        prompts = await client.list_prompts()
        assert "plan_applications" in {p.name for p in prompts.prompts}
        prompt = await client.get_prompt("plan_applications", {"grade": "11.2", "interests": "biología, química"})
        text = prompt.messages[0].content.text
        assert "11.2" in text and "admission_check" in text
