"""
Async MediaWiki API scraper for Terraria Wiki articles and categories.
Fetches page lists and article content using the official JSON API.
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional, Union
from loguru import logger
from datetime import datetime
from config import MEDIAWIKI_API_URL, MEDIAWIKI_CATEGORIES, tenacity_kwargs

@retry(stop=stop_after_attempt(tenacity_kwargs["stop"]), wait=wait_fixed(tenacity_kwargs["wait"]))
async def fetch_category_members(category: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch all page members of a given category from the Terraria Wiki.
    """
    logger.info(f"Fetching category members for '{category}'")
    members = []
    cmcontinue = None
    headers = {"User-Agent": "TerrariaAgenticBot/1.0 (school project) (contact: r.dingal.548395@umindanao.edu.ph)"}
    async with httpx.AsyncClient(headers=headers) as client:
        while True:
            params = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": f"Category:{category}",
                "cmlimit": limit,
                "format": "json",
            }
            if cmcontinue:
                params["cmcontinue"] = cmcontinue
            resp = await client.get(MEDIAWIKI_API_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            members.extend(data["query"]["categorymembers"])
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break
    logger.info(f"Fetched {len(members)} members for category '{category}'")
    return members


# MediaWiki API allows up to 50 pageids per request for normal users, 500 for bots. We'll use 50 for safety.
MAX_PAGEIDS_PER_REQUEST = 50

@retry(stop=stop_after_attempt(tenacity_kwargs["stop"]), wait=wait_fixed(tenacity_kwargs["wait"]))
async def fetch_pages_content(pageids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
    """
    Fetch the wikitext and metadata for a batch of page IDs.
    Returns a dict mapping pageid to page data (or None if not found).
    """
    logger.info(f"Fetching content for {len(pageids)} pageids")
    headers = {"User-Agent": "TerrariaAgenticBot/1.0 (contact: youremail@example.com)"}
    async with httpx.AsyncClient(headers=headers) as client:
        params = {
            "action": "query",
            "pageids": "|".join(str(pid) for pid in pageids),
            "prop": "revisions|info",
            "rvprop": "content|timestamp",
            "inprop": "url",
            "format": "json",
        }
        resp = await client.get(MEDIAWIKI_API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        pages = data["query"]["pages"]
        result = {}
        for pid in pageids:
            page = pages.get(str(pid))
            if not page:
                logger.warning(f"No page found for pageid={pid}")
                result[pid] = None
            else:
                result[pid] = page
        return result

# For backward compatibility, keep fetch_page_content for single pageid
async def fetch_page_content(pageid: int) -> Optional[Dict[str, Any]]:
    pages = await fetch_pages_content([pageid])
    return pages.get(pageid)

async def scrape_category(category: str, visited=None) -> List[Dict[str, Any]]:
    """
    Scrape all articles in a given category and its subcategories, returning a list of dicts with article metadata and content.
    """
    if visited is None:
        visited = set()
    if category in visited:
        logger.info(f"Already visited category '{category}', skipping to avoid cycles.")
        return []
    visited.add(category)
    members = await fetch_category_members(category)
    articles = []
    subcategories = []
    pageids = []
    member_map = {}
    for member in members:
        if member.get('ns') == 14:  # Namespace 14 = Category (subcategory)
            subcat_title = member["title"].replace("Category:", "", 1)
            subcategories.append(subcat_title)
        else:
            pageid = member["pageid"]
            pageids.append(pageid)
            member_map[pageid] = member
    # Batch fetch page content
    for i in range(0, len(pageids), MAX_PAGEIDS_PER_REQUEST):
        batch_ids = pageids[i:i+MAX_PAGEIDS_PER_REQUEST]
        pages = await fetch_pages_content(batch_ids)
        for pageid, page in pages.items():
            if not page:
                continue
            article = {
                "pageid": pageid,
                "title": page["title"],
                "category": category,
                "source_url": page.get("fullurl", ""),
                "last_updated": page["revisions"][0]["timestamp"] if page.get("revisions") else None,
                "wikitext": page["revisions"][0]["*"] if page.get("revisions") and "*" in page["revisions"][0] else "",
            }
            articles.append(article)
    # Recursively scrape subcategories
    for subcat in subcategories:
        logger.info(f"Recursively scraping subcategory '{subcat}' of '{category}'")
        articles.extend(await scrape_category(subcat, visited))
    logger.info(f"Scraped {len(articles)} articles from category '{category}' (including subcategories)")
    return articles

async def scrape_all_categories(categories: List[str] = MEDIAWIKI_CATEGORIES) -> List[Dict[str, Any]]:
    """
    Scrape all configured categories (and their subcategories) from the Terraria Wiki.
    """
    all_articles = []
    visited = set()
    for category in categories:
        articles = await scrape_category(category, visited)
        all_articles.extend(articles)
    logger.info(f"Total articles scraped: {len(all_articles)} (including subcategories)")
    return all_articles
