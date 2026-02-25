"""
Script to clean scraped articles and store them in a local SQLite database.
"""
import sqlite3
from ingestion.scraper import scrape_category
from ingestion.cleaner import clean_mediawiki_text
import asyncio

DB_PATH = "cleaned_articles.db"
TABLE_NAME = "articles"

# Define schema
SCHEMA = f'''
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pageid INTEGER,
    title TEXT,
    category TEXT,
    source_url TEXT,
    cleaned_text TEXT
);
'''

def save_articles_to_db(articles, db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(SCHEMA)
    for article in articles:
        c.execute(f'''
            INSERT INTO {TABLE_NAME} (pageid, title, category, source_url, cleaned_text)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            article.get("pageid"),
            article.get("title"),
            article.get("category"),
            article.get("source_url"),
            article.get("cleaned_text")
        ))
    conn.commit()
    conn.close()

async def main():
    category = "NPCs"  # Change as needed
    print(f"Scraping category: {category}")
    articles = await scrape_category(category)
    print(f"Cleaning {len(articles)} articles...")
    for article in articles:
        raw = article.get("extract") or ""
        article["cleaned_text"] = clean_mediawiki_text(raw)
    save_articles_to_db(articles)
    print(f"Saved {len(articles)} cleaned articles to {DB_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
