import os
import asyncio
from config import EMBEDDER_MODEL
from src.ingestion.scraper import scrape_specific_pages

# Ensure config safety checks pass for local smoke runs.
os.environ.setdefault("EMBEDDER_MODEL", EMBEDDER_MODEL)

def run_scrape_specific_pages_basic():
    async def _run():
        titles = ["Zenith"]
        articles = await scrape_specific_pages(titles=titles)
        assert isinstance(articles, list)
        assert len(articles) > 0
        article = articles[0]
        assert "Zenith" in article["title"]
        assert "cleaned_text" in article
        assert article["cleaned_text"]
        assert "pageid" in article
        assert article["pageid"]
        print("test_scrape_specific_pages_basic PASSED")
    asyncio.run(_run())

def run_scrape_specific_pages_empty():
    async def _run():
        titles = ["ThisPageDoesNotExist1234567890"]
        articles = await scrape_specific_pages(titles=titles)
        assert isinstance(articles, list)
        assert len(articles) == 0
        print("test_scrape_specific_pages_empty PASSED")
    asyncio.run(_run())

if __name__ == "__main__":
    run_scrape_specific_pages_basic()
    run_scrape_specific_pages_empty()
