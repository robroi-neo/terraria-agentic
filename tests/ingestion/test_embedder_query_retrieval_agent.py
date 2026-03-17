"""
Integration test/CLI: run retrieval via src.agent.nodes.retrieve (production path).

Usage:
    python -m pytest tests/ingestion/test_embedder_query_retrieval_agent.py -q
    python -m tests.ingestion.test_embedder_query_retrieval_agent

Optional env overrides:
    TEST_RETRIEVAL_QUERY="how to summon eye of cthulhu"
    TEST_RETRIEVAL_TOP_K=5
"""

import asyncio
import os

try:
    from chromadb.errors import InvalidArgumentError  # chromadb >= 0.5 style
except Exception:  # pragma: no cover - fallback for older/newer package layouts
    class InvalidArgumentError(Exception):
        pass

from src.agent.nodes import retrieve
from src.agent.gameplay_assumptions import DEFAULT_GAMEPLAY_ASSUMPTIONS


def _run(coro):
    return asyncio.run(coro)


def _build_state(query: str) -> dict:
    return {
        "query": query,
        "rewritten_query": "",
        "retrieved_chunks": [],
        "graded_chunks": [],
        "generation": "",
        "retry_count": 0,
        "route": "rag",
        "clarification_needed": False,
        "clarification_question": None,
        "clarification_retry_count": 0,
        "conversation_history": [],
        "gameplay_assumptions": dict(DEFAULT_GAMEPLAY_ASSUMPTIONS),
    }


def _retrieve_via_agent(query: str) -> list[dict]:
    state = _build_state(query)
    result_state = _run(retrieve(state))
    return result_state.get("retrieved_chunks", [])


def _print_hits(hits: list[dict], top_k: int) -> None:
    print(f"\nTop {len(hits)} / requested {top_k} results (agent retrieve)")
    for i, hit in enumerate(hits, start=1):
        title = hit.get("page_title", "[No Title]")
        section = hit.get("section_title", "[No Section]")
        distance = hit.get("distance")
        text = (hit.get("text") or "").strip()
        snippet = text
        distance_label = f"{distance:.4f}" if isinstance(distance, (int, float)) else "n/a"
        print(f"\n[{i}] {title} :: {section} (distance={distance_label})")
        print(f"page_title: {title}")
        print(snippet)


def _run_interactive_cli() -> None:
    default_top_k = int(os.getenv("TEST_RETRIEVAL_TOP_K", "5"))

    print("Agent retrieval console (uses src.agent.nodes.retrieve)")
    print("Type a query and press Enter. Type 'quit' or 'exit' to stop.")

    while True:
        raw_query = input("\nQuery: ").strip()
        if not raw_query:
            continue
        if raw_query.lower() in {"quit", "exit"}:
            print("Goodbye")
            break

        raw_k = input(f"Top-k [{default_top_k}]: ").strip()
        top_k = default_top_k if not raw_k else int(raw_k)

        try:
            hits = _retrieve_via_agent(raw_query)
        except InvalidArgumentError as exc:
            if "dimension" in str(exc).lower():
                print(
                    "Embedding dimension mismatch between current EMBEDDER_MODEL and indexed Chroma collection. "
                    "Re-run ingestion with this model or switch EMBEDDER_MODEL to match the existing index."
                )
                break
            raise

        _print_hits(hits[:top_k], top_k)


def test_agent_retrieve_returns_chunks():
    import pytest

    query = os.getenv("TEST_RETRIEVAL_QUERY", "how do i get the space gun")

    try:
        results = _retrieve_via_agent(query)
    except InvalidArgumentError as exc:
        if "dimension" in str(exc).lower():
            pytest.skip(
                "Embedding dimension mismatch between current EMBEDDER_MODEL and indexed Chroma collection. "
                "Re-run ingestion with this model or switch EMBEDDER_MODEL to match the existing index."
            )
        raise

    assert results, "Expected at least one retrieval result"
    assert all((hit.get("text") or "").strip() for hit in results)
    assert all((hit.get("page_title") or "").strip() for hit in results)


if __name__ == "__main__":
    try:
        _run_interactive_cli()
    except InvalidArgumentError as exc:
        if "dimension" in str(exc).lower():
            raise SystemExit(
                "Embedding dimension mismatch between current EMBEDDER_MODEL and indexed Chroma collection. "
                "Re-run ingestion with this model or switch EMBEDDER_MODEL to match the existing index."
            )
        raise
