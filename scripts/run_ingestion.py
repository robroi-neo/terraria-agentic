"""
Run the full ingestion pipeline end-to-end.

Pipeline:
    scrape -> chunk -> embed -> index

Usage examples:
    python -m scripts.run_ingestion
    python -m scripts.run_ingestion --categories Boss_NPCs Weapons --max-articles 50
    python -m scripts.run_ingestion --chroma-path ./test_chromadb --collection terraria_test
"""

import argparse
import asyncio
import os
from typing import List

from config import MEDIAWIKI_CATEGORIES
from src.ingestion.scraper import scrape_category
from src.ingestion.chunker import chunk_articles
from src.ingestion.embedder import BGEEmbedder, embed_and_index
from src.ingestion.indexer import ChromaIndexer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Terraria ingestion pipeline.")
    parser.add_argument(
        "--categories",
        nargs="+",
        default=None,
        help="One or more categories to scrape. If omitted, uses config MEDIAWIKI_CATEGORIES.",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Optional cap on number of scraped articles per category before chunking.",
    )
    parser.add_argument(
        "--chroma-path",
        default=None,
        help="Optional override for ChromaDB persist directory.",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="Optional override for ChromaDB collection name.",
    )
    parser.add_argument(
        "--query-smoke",
        default=None,
        help="Optional query string to run immediately after indexing as a smoke check.",
    )
    return parser


async def _scrape(categories: List[str]) -> List[dict]:
    visited = set()
    all_articles: List[dict] = []
    for category in categories:
        all_articles.extend(await scrape_category(category, visited))
    return all_articles


async def main() -> None:
    args = _build_parser().parse_args()
    categories = args.categories or MEDIAWIKI_CATEGORIES

    print("[1/4] Initializing embedder and indexer...")
    embedder = BGEEmbedder()
    indexer_kwargs = {}
    if args.chroma_path:
        indexer_kwargs["persist_directory"] = args.chroma_path
    if args.collection:
        indexer_kwargs["collection_name"] = args.collection
    indexer = ChromaIndexer(**indexer_kwargs)

    print("[2/4] Processing categories incrementally...")
    print(f"Categories: {categories}")

    visited = set()
    total_articles = 0
    total_chunks = 0
    failed_categories: List[str] = []

    for category in categories:
        print(f"\n--- Category: {category} ---")
        try:
            articles = await scrape_category(category, visited)
            if args.max_articles is not None:
                articles = articles[: args.max_articles]
            print(f"Scraped articles: {len(articles)}")

            if not articles:
                print("No articles found for this category, skipping.")
                continue

            chunks = chunk_articles(articles)
            print(f"Generated chunks: {len(chunks)}")
            if not chunks:
                print("No chunks generated for this category, skipping.")
                continue

            await embed_and_index(chunks, embedder, indexer)
            total_articles += len(articles)
            total_chunks += len(chunks)
            current_count = await indexer.count()
            print(f"Indexed category '{category}'. Collection count now: {current_count}")
        except Exception as exc:
            failed_categories.append(category)
            print(f"Category '{category}' failed: {exc}")

    if total_chunks == 0:
        raise RuntimeError("No chunks were indexed. All categories failed or returned empty data.")

    print("\n[3/4] Final index stats...")
    count = await indexer.count()
    print(f"Indexing complete. Collection count: {count}")
    print(f"Total processed articles: {total_articles}")
    print(f"Total processed chunks: {total_chunks}")
    if failed_categories:
        print(f"Failed categories: {failed_categories}")

    print("[4/4] Optional smoke query...")
    if args.query_smoke:
        print("Running query smoke test...")
        vector = embedder.embed_query(args.query_smoke)
        results = await indexer.query(vector, n_results=3)
        print(f"Query results: {len(results)}")
        if results:
            first = results[0]
            print("Top hit page:", first.get("page_title"))
            print("Top hit section:", first.get("section_title"))


if __name__ == "__main__":
    asyncio.run(main())
