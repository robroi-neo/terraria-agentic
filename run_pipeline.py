"""
Pipeline: SQLite (cleaned_articles.db) → Chunker → BGEEmbedder → ChromaDB
"""
import asyncio
import sqlite3
from typing import List, Dict, Any

from src.ingestion.chunker import chunk_articles
from src.ingestion.embedder import BGEEmbedder, embed_and_index
from src.ingestion.indexer import ChromaIndexer

DB_PATH = "cleaned_articles.db"


def load_articles_from_db(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Load cleaned articles from SQLite into a list of dicts."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row          # lets us access columns by name
    cursor = conn.cursor()
    cursor.execute("SELECT pageid, title, category, source_url, cleaned_text FROM articles")
    rows = cursor.fetchall()
    conn.close()

    articles = [
        {
            "pageid":       row["pageid"],
            "title":        row["title"],
            "category":     row["category"],
            "source_url":   row["source_url"],
            "cleaned_text": row["cleaned_text"],
            "last_updated": "",     # not stored in DB; ChromaDB metadata requires the field
        }
        for row in rows
    ]
    print(f"Loaded {len(articles)} articles from '{db_path}'")
    return articles


async def main() -> None:
    # ── 1. Load ──────────────────────────────────────────────────────────────
    articles = load_articles_from_db()
    if not articles:
        print("No articles found. Run save_cleaned.py first.")
        return

    # ── 2. Chunk ─────────────────────────────────────────────────────────────
    print("Chunking articles...")
    chunks = chunk_articles(articles)
    print(f"Total chunks: {len(chunks)}")

    # ── 3. Embed + Index ──────────────────────────────────────────────────────
    print("Loading BGE embedder (downloads model on first run)...")
    embedder = BGEEmbedder()        # auto-detects CUDA / CPU

    print("Initialising ChromaDB indexer...")
    indexer = ChromaIndexer()       # uses CHROMADB_PATH + CHROMADB_COLLECTION from config

    print("Embedding and indexing chunks — this may take a while...")
    await embed_and_index(chunks, embedder, indexer)

    # ── 4. Sanity check ───────────────────────────────────────────────────────
    count = await indexer.count()
    print(f"Done. ChromaDB now contains {count} chunks.")


if __name__ == "__main__":
    asyncio.run(main())