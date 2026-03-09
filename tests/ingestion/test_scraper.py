"""
Test script for scraper.py: fetches articles using scraper.py 
"""
import asyncio
from src.ingestion.scraper import scrape_category, scrape_all_categories, fetch_page_content

async def test_single_category():
    category = "Boss_NPCs"  # pick a known Terraria Wiki category
    articles = await scrape_category(category)
    print(f"Scraped {len(articles)} articles from category '{category}'\n")
    # Print sample
    for article in articles[:25]:
        print("Title:", article["title"])
        print("PageID:", article["pageid"])
        print("Last Updated:", article["last_updated"])
        print("Sections:", len(article.get("sections", [])))
        print("Cleaned snippet:", (article.get("cleaned_text") or ""))
        print("-" * 40)
        
async def test_single_page():
    pageid = 15899  # Replace with a valid page ID
    page = await fetch_page_content(pageid)
    if page:
        print("Title:", page.get("title"))
        print("PageID:", pageid)
        print("Last Updated:", page.get("revisions")[0]["timestamp"] if page.get("revisions") else None)
        print("Wikitext snippet:", (page.get("revisions")[0].get("*") if page.get("revisions") and "*" in page.get("revisions")[0] else ""))
    else:
        print("Page not found.")

async def test_all_categories():
    # This will scrape all categories in MEDIAWIKI_CATEGORIES (you can limit if needed)
    all_articles = await scrape_all_categories(categories=["Bosses"])
    print(f"Total articles scraped: {len(all_articles)}")

if __name__ == "__main__":
    asyncio.run(test_single_category())