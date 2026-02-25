"""
Test script for cleaner.py: fetches articles using scraper.py and prints cleaned text.
"""
import asyncio
from ingestion.scraper import scrape_category
from ingestion.cleaner import clean_mediawiki_text

async def test_cleaner():
    category = "Boss_NPCs"  # Change as needed
    print(f"Scraping category: {category}")
    articles = await scrape_category(category)
    print(f"Fetched {len(articles)} articles. Printing cleaned text for first 10:")
    for i, article in enumerate(articles[:10]):
        raw = article.get("wikitext") or ""
        cleaned = clean_mediawiki_text(raw)
        print(f"--- Article {i+1}: {article.get('title')} ---")
        print(cleaned)
        print("\n" + "="*60 + "\n")

if __name__ == "__main__":
    asyncio.run(test_cleaner())
