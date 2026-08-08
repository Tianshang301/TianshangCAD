"""Unit tests for server-side Tool Search (tools/list query filtering)."""

from __future__ import annotations

import asyncio

from tianshangcad.mcp.server import (
    ListToolsSearchParams,
    _query_tokens,
    _score_tool,
    build_server,
)


class TestQueryTokens:
    """Query tokenization and stopword filtering."""

    def test_splits_on_whitespace_and_punctuation(self) -> None:
        assert _query_tokens("measure distance") == ["measure", "distance"]
        assert _query_tokens("3d,view") == ["3d", "view"]
        assert _query_tokens("sim.run") == ["sim", "run"]

    def test_drops_stopwords(self) -> None:
        assert _query_tokens("cad tool") == []
        assert _query_tokens("the a an and tool") == []
        assert _query_tokens("list tools") == ["list"]

    def test_empty_and_case(self) -> None:
        assert _query_tokens("") == []
        assert _query_tokens("  Measure  ") == ["measure"]


class TestScoring:
    """Tool ranking against query tokens."""

    def test_name_match_scores(self) -> None:
        assert _score_tool("cad_measure", "measure distances", ["measure"]) > 0
        assert _score_tool("cad_layer", "layer management", ["layer"]) > 0

    def test_name_equals_is_highest(self) -> None:
        equal = _score_tool("measure", "measure distances", ["measure"])
        substring = _score_tool("cad_measure", "measure distances", ["measure"])
        assert equal > substring

    def test_description_match_but_name_miss(self) -> None:
        assert _score_tool("cad_layer", "measure distances here", ["measure"]) > 0

    def test_no_match(self) -> None:
        assert _score_tool("cad_layer", "layer management", ["measure"]) == 0

    def test_all_tokens_must_match(self) -> None:
        assert _score_tool("cad_sim", "simulation run", ["sim", "run"]) > 0
        assert _score_tool("cad_sim", "simulation only", ["sim", "missing"]) == 0


class TestToolSearchHandler:
    """End-to-end filter behavior through the registered tools/list handler."""

    def _names(self, query: str | None) -> list[str]:
        server = build_server()
        entry = server._lowlevel_server.get_request_handler("tools/list")

        async def run() -> list[str]:
            result = await entry.handler(None, ListToolsSearchParams(query=query))
            return [tool.name for tool in result.tools]

        return asyncio.run(run())

    def test_no_query_returns_all(self) -> None:
        names = self._names(None)
        assert len(names) == 19
        assert "cad_object" in names

    def test_measure_filter(self) -> None:
        names = self._names("measure")
        assert names[0] == "cad_measure"
        assert "cad_measure" in names

    def test_layer_matches_layer_and_status(self) -> None:
        names = self._names("layer")
        assert names[0] == "cad_layer"
        assert "cad_layer" in names
        assert "cad_status" in names

    def test_no_match_is_empty(self) -> None:
        assert self._names("zzz_nope") == []

    def test_multiword_all_match(self) -> None:
        assert self._names("sim run") == ["cad_sim"]

    def test_empty_query_is_all(self) -> None:
        assert len(self._names("")) == 19
        assert len(self._names("cad tool")) == 0


def test_build_server_installs_search_handler() -> None:
    server = build_server()
    entry = server._lowlevel_server.get_request_handler("tools/list")
    assert entry is not None
    assert entry.params_type is ListToolsSearchParams
