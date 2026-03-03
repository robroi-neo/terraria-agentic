"""
End-to-end ingestion pipeline smoke test.

Flow:
scraper -> chunker -> embedder -> indexer -> query

Writes vectors to an isolated test ChromaDB directory by default:
    ./test_chromadb

Run:
    python -m tests.ingestion.test_pipeline_integration
"""

import os
import time
import asyncio
from typing import List, Dict, Any


# Ensure config safety checks pass for local smoke runs.
os.environ.setdefault("EMBEDDER_MODEL", "BAAI/bge-base-en-v1.5")

from src.ingestion.scraper import scrape_category
from src.ingestion.chunker import chunk_articles
from src.ingestion.embedder import BGEEmbedder, embed_and_index
from src.ingestion.indexer import ChromaIndexer


TEST_CATEGORIES = ["Boss_NPCs", "Bosses", "Weapons", "NPCs", "Terraria"]
MAX_ARTICLES = 2
TEST_CHROMA_PATH = "./tests/test_chromadb"


def _select_articles_for_test(articles: List[Dict[str, Any]], max_articles: int) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for article in articles:
        has_sections = bool(article.get("sections"))
        has_text = bool(article.get("cleaned_text"))
        if has_sections or has_text:
            selected.append(article)
        if len(selected) >= max_articles:
            break
    return selected


async def run_pipeline_test() -> None:
    print("[1/5] Scraping category...")
    articles = []
    selected_category = None
    for category in TEST_CATEGORIES:
        print(f"Trying category: {category}")
        scraped = await scrape_category(category)
        if scraped:
            articles = scraped
            selected_category = category
            break

    if not articles:
        raise RuntimeError(f"No articles returned by scraper for categories: {TEST_CATEGORIES}")
    print(f"Using category '{selected_category}' with {len(articles)} scraped article(s).")

    selected = _select_articles_for_test(articles, MAX_ARTICLES)
    if not selected:
        raise RuntimeError("No usable articles (sections/cleaned_text) for pipeline test.")
    print(f"Selected {len(selected)} article(s) for smoke test.")

    print("[2/5] Chunking selected articles...")
    chunks = chunk_articles(selected)
    if not chunks:
        raise RuntimeError("Chunker produced no chunks.")
    print(f"Generated {len(chunks)} chunk(s).")

    print("[3/5] Initializing embedder + test indexer...")
    collection_name = f"terraria_pipeline_test_{int(time.time())}"
    indexer = ChromaIndexer(
        persist_directory=TEST_CHROMA_PATH,
        collection_name=collection_name,
    )
    embedder = BGEEmbedder()

    print("[4/5] Embedding and indexing chunks...")
    await embed_and_index(chunks, embedder, indexer)
    indexed_count = await indexer.count()
    if indexed_count <= 0:
        raise RuntimeError("Indexer count is 0 after embed_and_index.")
    print(f"Indexed chunks in test collection '{collection_name}': {indexed_count}")

    print("[5/5] Querying indexed test data...")
    query_vector = embedder.embed_query("hardmode melee weapon in corruption biome")
    results = await indexer.query(query_vector, n_results=min(3, indexed_count))
    if not results:
        raise RuntimeError("Query returned no results from test collection.")

    first = results[0]
    print("Pipeline smoke test PASSED")
    print("First hit keys:", sorted(first.keys()))
    print("First hit page:", first.get("page_title"))
    print("First hit section:", first.get("section_title"))
    print("Test ChromaDB path:", TEST_CHROMA_PATH)
    print("Test collection:", collection_name)


if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
