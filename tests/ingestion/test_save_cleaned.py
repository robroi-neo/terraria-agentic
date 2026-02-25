"""
Test script for save_cleaner.py: fetches articles using scraper.py, cleans the file, and saves it into cleaned_articles.db
"""
# This shit very basic but fuck guys this is all i need for now
import asyncio
import sqlite3
from src.ingestion.scraper import scrape_category
from src.ingestion.cleaner import clean_mediawiki_text
from src.ingestion.save_cleaned import save_articles_to_db

# Test Database
TEST_DB_PATH = "test_cleaned_articles.db"
TEST_CATEGORY = "Store_pages"

async def main():
    print(f"Scraping TEST_CATEGORY: {TEST_CATEGORY}")
    articles = await scrape_category(TEST_CATEGORY)
    print(f"Cleaning {len(articles)} articles...")
    for article in articles:
        raw = article.get("wikitext") or ""
        article["cleaned_text"] = clean_mediawiki_text(raw)
    save_articles_to_db(articles, db_path=TEST_DB_PATH)
    print(f"Saved {len(articles)} cleaned articles to {TEST_DB_PATH}")

if __name__ == "__main__":
    asyncio.run(main())