
"""
Async MediaWiki API scraper for Terraria Wiki articles and categories.
Fetches page lists and article content using the official JSON API.
"""
import asyncio
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional
from loguru import logger

from config import MEDIAWIKI_API_URL, MEDIAWIKI_CATEGORIES, tenacity_kwargs
from bs4 import BeautifulSoup

def clean_section_html(section_html: str) -> str:
    """
    Clean section HTML and convert to plain text.
    Removes scripts, styles, and unnecessary tags.
    """
    soup = BeautifulSoup(section_html, "html.parser")
    # Remove scripts and styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Remove edit links, references, and navigation
    for tag in soup.select(".mw-editsection, .navbox, .metadata, sup.reference"):
        tag.decompose()
    # Get plain text
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_infobox_key(key: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", key.lower())).strip()


def _parse_bool(value: str) -> Optional[bool]:
    normalized = value.strip().lower()
    if normalized in {"yes", "true", "y", "1"}:
        return True
    if normalized in {"no", "false", "n", "0"}:
        return False
    return None


def _extract_domain_metadata(infobox: Dict[str, str]) -> Dict[str, Any]:
    """
    Derive domain-specific retrieval metadata from infobox keys.
    """
    normalized_map = {_normalize_infobox_key(key): value for key, value in infobox.items()}

    def find_value(candidates: List[str]) -> Optional[str]:
        for candidate in candidates:
            if candidate in normalized_map and normalized_map[candidate]:
                return normalized_map[candidate]
        return None

    biome = find_value(["biome", "biomes"])
    damage_type = find_value(["damage", "damage type", "class", "type"])
    hardmode_raw = find_value(["hardmode", "hard mode"])
    hardmode = _parse_bool(hardmode_raw) if hardmode_raw else None

    return {
        "biome": biome,
        "damage_type": damage_type,
        "hardmode": hardmode,
    }


def extract_infobox_and_sections(html: str) -> Dict[str, Any]:
    """
    Extract infobox (as dict) and sectioned text (as list of {title, html}) from MediaWiki HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    content_root = soup.select_one("div.mw-parser-output") or soup

    # Extract infobox (first table with class 'infobox')
    infobox = {}
    infobox_table = content_root.find("table", class_="infobox")
    if infobox_table:
        for row in infobox_table.find_all("tr"):
            header = row.find("th")
            value = row.find("td")
            if header and value:
                key = header.get_text(strip=True)
                val = value.get_text(" ", strip=True)
                infobox[key] = val
        infobox_table.decompose()
    # Extract sections: each <h2> and its following siblings until next <h2>
    sections = []
    current_title = "Introduction"
    current_content: List[str] = []

    for child in content_root.children:
        node_name = getattr(child, "name", None)
        if node_name == "h2":
            if current_content:
                sections.append({"title": current_title, "html": "".join(current_content)})
                current_content = []
            headline = child.select_one(".mw-headline")
            current_title = (headline.get_text(" ", strip=True) if headline else child.get_text(" ", strip=True)).replace("[edit]", "").strip()
            continue
        if node_name in {"script", "style"}:
            continue
        if node_name == "div" and "toc" in (child.get("class") or []):
            continue
        current_content.append(str(child))

    if current_content:
        sections.append({"title": current_title, "html": "".join(current_content)})

    return {"infobox": infobox, "sections": sections}

@retry(stop=stop_after_attempt(tenacity_kwargs["stop"]), wait=wait_fixed(tenacity_kwargs["wait"]))
async def fetch_page_html(pageid: int) -> Optional[str]:
    """
    Fetch the parsed HTML for a given pageid using MediaWiki API (action=parse).
    Returns HTML string or None if not found.
    """
    logger.info(f"Fetching parsed HTML for pageid={pageid}")
    headers = {"User-Agent": "TerrariaAgenticBot/1.0 (contact: youremail@example.com)"}
    async with httpx.AsyncClient(headers=headers) as client:
        params = {
            "action": "parse",
            "pageid": pageid,
            "format": "json",
            "prop": "text",
        }
        resp = await client.get(MEDIAWIKI_API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        html = data.get("parse", {}).get("text", {}).get("*", None)
        if not html:
            logger.warning(f"No HTML found for pageid={pageid}")
            return None
        return html


async def fetch_pages_html(pageids: List[int], concurrency: int = 10) -> Dict[int, Optional[str]]:
    """
    Fetch parsed HTML for many pages with bounded concurrency.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _fetch(pageid: int) -> tuple[int, Optional[str]]:
        async with semaphore:
            try:
                return pageid, await fetch_page_html(pageid)
            except Exception as exc:
                logger.warning(f"Failed to fetch HTML for pageid={pageid}: {exc}")
                return pageid, None

    pairs = await asyncio.gather(*(_fetch(pageid) for pageid in pageids))
    return dict(pairs)

@retry(stop=stop_after_attempt(tenacity_kwargs["stop"]), wait=wait_fixed(tenacity_kwargs["wait"]))
async def fetch_category_members(category: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch all page members of a given category from the Terraria Wiki.
    """
    logger.info(f"Fetching category members for '{category}'")
    members = []
    cmcontinue = None
    headers = {"User-Agent": "TerrariaAgenticBot/1.0 (school) (contact: r.dingal.548395@umindanao.edu.ph)"}
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
    # Batch fetch page content and parsed HTML
    for i in range(0, len(pageids), MAX_PAGEIDS_PER_REQUEST):
        batch_ids = pageids[i:i+MAX_PAGEIDS_PER_REQUEST]
        pages = await fetch_pages_content(batch_ids)
        html_by_pageid = await fetch_pages_html(batch_ids)
        for pageid, page in pages.items():
            if not page:
                continue
            page_html = html_by_pageid.get(pageid)
            parsed = extract_infobox_and_sections(page_html) if page_html else {"infobox": {}, "sections": []}
            cleaned_sections = []
            for section in parsed["sections"]:
                cleaned_text = clean_section_html(section["html"])
                if cleaned_text:
                    cleaned_sections.append({
                        "title": section["title"] or "Untitled",
                        "text": cleaned_text,
                    })

            derived_metadata = _extract_domain_metadata(parsed["infobox"])
            article = {
                "pageid": pageid,
                "title": page["title"],
                "category": category,
                "source_url": page.get("fullurl", ""),
                "last_updated": page["revisions"][0]["timestamp"] if page.get("revisions") else None,
                "wikitext": page["revisions"][0]["*"] if page.get("revisions") and "*" in page["revisions"][0] else "",
                "html": page_html or "",
                "infobox": parsed["infobox"],
                "sections": cleaned_sections,
                "cleaned_text": "\n\n".join(section["text"] for section in cleaned_sections),
                "biome": derived_metadata["biome"],
                "hardmode": derived_metadata["hardmode"],
                "damage_type": derived_metadata["damage_type"],
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
