"""
Integration test: embed a query and retrieve top-k chunks from ChromaDB.

Usage:
    python -m pytest tests/ingestion/test_embedder_query_retrieval.py -q
    python -m tests.ingestion.test_embedder_query_retrieval

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

from src.ingestion.embedder import BGEEmbedder
from src.ingestion.indexer import ChromaIndexer


def _run(coro):
    return asyncio.run(coro)


def _create_clients() -> tuple[ChromaIndexer, BGEEmbedder, int]:
    indexer = ChromaIndexer()
    total_chunks = _run(indexer.count())
    if total_chunks == 0:
        raise RuntimeError("ChromaDB collection is empty. Run ingestion first.")

    embedder = BGEEmbedder()
    return indexer, embedder, total_chunks


def _retrieve_top_k(indexer: ChromaIndexer, embedder: BGEEmbedder, query: str, top_k: int, total_chunks: int) -> tuple[list[dict], int]:
    if top_k <= 0:
        raise ValueError("top_k must be > 0")

    query_vector = embedder.embed_query(query)
    n_results = min(top_k, total_chunks)
    results = _run(indexer.query(query_vector, n_results=n_results))
    return results, n_results


def _retrieve_top_k_for_test() -> tuple[list[dict], int, str, int]:
    query = os.getenv("TEST_RETRIEVAL_QUERY", "how do i get the space gun")
    top_k = int(os.getenv("TEST_RETRIEVAL_TOP_K", "5"))
    indexer, embedder, total_chunks = _create_clients()
    results, n_results = _retrieve_top_k(indexer, embedder, query, top_k, total_chunks)
    return results, n_results, query, total_chunks


def _print_hits(hits: list[dict], top_k: int) -> None:
    print(f"\nTop {len(hits)} / requested {top_k} results")
    for i, hit in enumerate(hits, start=1):
        title = hit.get("page_title", "[No Title]")
        section = hit.get("section_title", "[No Section]")
        distance = hit.get("distance")
        text = (hit.get("text") or "").strip()
        snippet = text if len(text) <= 600 else text[:600] + "..."
        distance_label = f"{distance:.4f}" if isinstance(distance, (int, float)) else "n/a"
        print(f"\n[{i}] {title} :: {section} (distance={distance_label})")
        print(snippet)


def _run_interactive_cli() -> None:
    default_top_k = int(os.getenv("TEST_RETRIEVAL_TOP_K", "5"))
    indexer, embedder, total_chunks = _create_clients()

    print("Embedder retrieval console")
    print(f"Collection size: {total_chunks}")
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
            hits, _ = _retrieve_top_k(indexer, embedder, raw_query, top_k, total_chunks)
        except InvalidArgumentError as exc:
            if "dimension" in str(exc).lower():
                print(
                    "Embedding dimension mismatch between current EMBEDDER_MODEL and indexed Chroma collection. "
                    "Re-run ingestion with this model or switch EMBEDDER_MODEL to match the existing index."
                )
                break
            raise

        _print_hits(hits, top_k)


def test_embedder_query_returns_top_k_chunks():
    import pytest

    try:
        results, n_results, _, _ = _retrieve_top_k_for_test()
    except InvalidArgumentError as exc:
        if "dimension" in str(exc).lower():
            pytest.skip(
                "Embedding dimension mismatch between current EMBEDDER_MODEL and indexed Chroma collection. "
                "Re-run ingestion with this model or switch EMBEDDER_MODEL to match the existing index."
            )
        raise
    except RuntimeError as exc:
        if "empty" in str(exc).lower():
            pytest.skip(str(exc))
        raise

    assert results, "Expected at least one retrieval result"
    assert len(results) == n_results
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
