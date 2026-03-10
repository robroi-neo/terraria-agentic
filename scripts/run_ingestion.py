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

from config import (
    MEDIAWIKI_CATEGORIES,
    SCRAPE_PAGES,
    WALKTHROUGH_ROOT_PAGE,
    WALKTHROUGH_MAX_DEPTH,
    WALKTHROUGH_MAX_PAGES,
    WALKTHROUGH_INCLUDE_GUIDE_LINKS,
    WALKTHROUGH_EXCLUDED_NAMESPACES,
    WALKTHROUGH_ROOT_COLLECTION_SUFFIX,
    WALKTHROUGH_LINKS_COLLECTION_SUFFIX,
)
from src.ingestion.scraper import scrape_category, scrape_specific_pages, scrape_walkthrough_recursive
from src.ingestion.chunker import chunk_articles
from src.ingestion.embedder import BGEEmbedder, embed_and_index
from src.ingestion.indexer import ChromaIndexer


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Terraria ingestion pipeline.")
    parser.add_argument(
        "--mode",
        choices=["standard", "walkthrough_recursive"],
        default="standard",
        help="Ingestion mode. 'standard' uses categories/pages; 'walkthrough_recursive' crawls linked pages from a root walkthrough.",
    )
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
    parser.add_argument(
        "--pages",
        nargs="+",
        default=None,
        help="Specific page titles to scrape (in addition to or instead of categories).",
    )
    parser.add_argument(
        "--root-page",
        default=WALKTHROUGH_ROOT_PAGE,
        help="Root page title for walkthrough_recursive mode.",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=WALKTHROUGH_MAX_DEPTH,
        help="Maximum crawl depth for walkthrough_recursive mode.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=WALKTHROUGH_MAX_PAGES,
        help="Maximum pages to process for walkthrough_recursive mode.",
    )
    parser.add_argument(
        "--include-guide-links",
        action="store_true",
        default=WALKTHROUGH_INCLUDE_GUIDE_LINKS,
        help="Include Guide:* links while crawling walkthrough_recursive mode.",
    )
    parser.add_argument(
        "--exclude-namespaces",
        nargs="+",
        default=None,
        help="Optional namespace denylist for walkthrough_recursive mode (e.g. File Template Talk).",
    )
    parser.add_argument(
        "--root-collection",
        default=None,
        help="Optional explicit root collection name for walkthrough_recursive mode.",
    )
    parser.add_argument(
        "--links-collection",
        default=None,
        help="Optional explicit linked-pages collection name for walkthrough_recursive mode.",
    )
    return parser



async def _scrape(categories: List[str], pages: List[str]) -> List[dict]:
    articles: List[dict] = []
    visited = set()
    if categories:
        for category in categories:
            articles.extend(await scrape_category(category, visited))
    if pages:
        articles.extend(await scrape_specific_pages(titles=pages))
    return articles


async def main() -> None:
    args = _build_parser().parse_args()

    categories = args.categories if args.categories is not None else MEDIAWIKI_CATEGORIES
    pages = args.pages if args.pages is not None else SCRAPE_PAGES

    print("[1/4] Initializing embedder and indexer...")
    embedder = BGEEmbedder()
    base_indexer_kwargs = {}
    if args.chroma_path:
        base_indexer_kwargs["persist_directory"] = args.chroma_path

    indexer = None
    root_indexer = None
    links_indexer = None

    if args.mode == "standard":
        indexer_kwargs = dict(base_indexer_kwargs)
        if args.collection:
            indexer_kwargs["collection_name"] = args.collection
        indexer = ChromaIndexer(**indexer_kwargs)
    else:
        if args.root_collection:
            root_collection = args.root_collection
        elif args.collection:
            root_collection = f"{args.collection}_{WALKTHROUGH_ROOT_COLLECTION_SUFFIX}"
        else:
            root_collection = WALKTHROUGH_ROOT_COLLECTION_SUFFIX

        if args.links_collection:
            links_collection = args.links_collection
        elif args.collection:
            links_collection = f"{args.collection}_{WALKTHROUGH_LINKS_COLLECTION_SUFFIX}"
        else:
            links_collection = WALKTHROUGH_LINKS_COLLECTION_SUFFIX

        root_indexer = ChromaIndexer(collection_name=root_collection, **base_indexer_kwargs)
        links_indexer = ChromaIndexer(collection_name=links_collection, **base_indexer_kwargs)


    print("[2/4] Processing categories and/or specific pages...")
    if args.mode == "standard":
        print(f"Mode: standard")
        print(f"Categories: {categories}")
        print(f"Specific pages: {pages}")
    else:
        print("Mode: walkthrough_recursive")
        print(f"Root page: {args.root_page}")
        print(f"Max depth: {args.max_depth}")
        print(f"Max pages: {args.max_pages}")

    total_articles = 0
    total_chunks = 0
    failed_sources: List[str] = []

    try:
        if args.mode == "standard":
            articles = await _scrape(categories, pages)
            if args.max_articles is not None:
                articles = articles[: args.max_articles]
            print(f"Scraped articles: {len(articles)}")

            if not articles:
                print("No articles found, skipping chunking and indexing.")
                raise RuntimeError("No articles were scraped from the provided categories/pages.")

            chunks = chunk_articles(articles)
            print(f"Generated chunks: {len(chunks)}")
            if not chunks:
                print("No chunks generated, skipping indexing.")
                raise RuntimeError("No chunks were generated from the scraped articles.")

            await embed_and_index(chunks, embedder, indexer)
            total_articles += len(articles)
            total_chunks += len(chunks)
            current_count = await indexer.count()
            print(f"Indexed all articles. Collection count now: {current_count}")
        else:
            excluded_namespaces = args.exclude_namespaces or WALKTHROUGH_EXCLUDED_NAMESPACES
            crawl_result = await scrape_walkthrough_recursive(
                root_title=args.root_page,
                max_depth=args.max_depth,
                max_pages=args.max_pages,
                include_guide_links=args.include_guide_links,
                excluded_namespaces=excluded_namespaces,
            )
            root_articles = crawl_result["root_articles"]
            linked_articles = crawl_result["linked_articles"]

            print(f"Root articles scraped: {len(root_articles)}")
            print(f"Linked articles scraped: {len(linked_articles)}")

            if not root_articles and not linked_articles:
                raise RuntimeError("walkthrough_recursive scraped zero pages.")

            root_chunks = chunk_articles(root_articles) if root_articles else []
            linked_chunks = chunk_articles(linked_articles) if linked_articles else []
            print(f"Root chunks: {len(root_chunks)}")
            print(f"Linked chunks: {len(linked_chunks)}")

            if root_chunks:
                await embed_and_index(root_chunks, embedder, root_indexer)
            if linked_chunks:
                await embed_and_index(linked_chunks, embedder, links_indexer)

            total_articles += len(root_articles) + len(linked_articles)
            total_chunks += len(root_chunks) + len(linked_chunks)
            if root_indexer:
                print(f"Root collection count: {await root_indexer.count()}")
            if links_indexer:
                print(f"Links collection count: {await links_indexer.count()}")
    except Exception as exc:
        failed_sources.append(str(exc))
        print(f"Ingestion failed: {exc}")

    if total_chunks == 0:
        raise RuntimeError("No chunks were indexed. All categories/pages failed or returned empty data.")

    print("\n[3/4] Final index stats...")
    if args.mode == "standard":
        count = await indexer.count()
        print(f"Indexing complete. Collection count: {count}")
    else:
        root_count = await root_indexer.count() if root_indexer else 0
        links_count = await links_indexer.count() if links_indexer else 0
        print(f"Indexing complete. Root collection count: {root_count}")
        print(f"Indexing complete. Linked collection count: {links_count}")
    print(f"Total processed articles: {total_articles}")
    print(f"Total processed chunks: {total_chunks}")
    if failed_sources:
        print(f"Failed sources: {failed_sources}")

    print("[4/4] Optional smoke query...")
    if args.query_smoke:
        print("Running query smoke test...")
        vector = embedder.embed_query(args.query_smoke)
        if args.mode == "standard":
            results = await indexer.query(vector, n_results=3)
            print(f"Query results: {len(results)}")
            if results:
                first = results[0]
                print("Top hit page:", first.get("page_title"))
                print("Top hit section:", first.get("section_title"))
        else:
            root_results = await root_indexer.query(vector, n_results=3) if root_indexer else []
            links_results = await links_indexer.query(vector, n_results=3) if links_indexer else []
            print(f"Root query results: {len(root_results)}")
            print(f"Links query results: {len(links_results)}")
            merged = root_results + links_results
            if merged:
                first = merged[0]
                print("Top hit page:", first.get("page_title"))
                print("Top hit section:", first.get("section_title"))


if __name__ == "__main__":
    asyncio.run(main())
