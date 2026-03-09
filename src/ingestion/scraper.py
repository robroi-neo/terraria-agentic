
"""
Async MediaWiki API scraper for Terraria Wiki articles and categories.
Fetches page lists and article content using the official JSON API.
"""
import asyncio
import re
import random

import httpx
from typing import List, Dict, Any, Optional
from loguru import logger

from config import (
    MEDIAWIKI_API_URL,
    MEDIAWIKI_CATEGORIES,
    USER_AGENT,
    REQUEST_FROM_EMAIL,
    tenacity_kwargs,
    SCRAPER_MAX_PAGEIDS_PER_REQUEST,
    SCRAPER_HTML_CONCURRENCY,
    SCRAPER_BATCH_DELAY_SECONDS,
    SCRAPER_DROP_SELECTORS,
    SCRAPER_EXCLUDED_SECTION_TITLES,
    SCRAPER_BOILERPLATE_PATTERNS,
    SCRAPER_MIN_SECTION_CHARS,
)
from bs4 import BeautifulSoup


def _request_headers() -> Dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "From": REQUEST_FROM_EMAIL,
        "Accept": "application/json",
    }

def clean_section_html(section_html: str) -> str:
    """
    Clean section HTML and convert to plain text.
    Removes scripts, styles, and unnecessary tags.
    """
    soup = BeautifulSoup(section_html, "html.parser")
    # Remove scripts and styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    # Remove wiki chrome, references, and nav/footer UI blocks.
    for selector in SCRAPER_DROP_SELECTORS:
        for tag in soup.select(selector):
            tag.decompose()

    # Get plain text
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\[\d+\]", " ", text)
    for pattern in SCRAPER_BOILERPLATE_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


_EXCLUDED_TITLES_NORMALIZED = {
    _normalize_title(title)
    for title in SCRAPER_EXCLUDED_SECTION_TITLES
}


def _is_excluded_section_title(title: str) -> bool:
    normalized = _normalize_title(title)
    if not normalized:
        return False
    for excluded in _EXCLUDED_TITLES_NORMALIZED:
        if normalized == excluded or normalized.startswith(f"{excluded} "):
            return True
    return False


def _normalized_body_key(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _build_cleaned_sections(sections: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    cleaned_sections: List[Dict[str, str]] = []
    seen_bodies = set()

    for section in sections:
        title = section.get("title") or "Untitled"
        if _is_excluded_section_title(title):
            continue

        cleaned_text = clean_section_html(section.get("html", ""))
        if len(cleaned_text) < SCRAPER_MIN_SECTION_CHARS:
            continue

        body_key = _normalized_body_key(cleaned_text)
        if not body_key or body_key in seen_bodies:
            continue
        seen_bodies.add(body_key)

        cleaned_sections.append({
            "title": title,
            "text": cleaned_text,
        })

    return cleaned_sections


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

    type_value = find_value(["type", "class", "damage type", "damage"])
    hardmode_raw = find_value(["hardmode", "hard mode"])
    hardmode = _parse_bool(hardmode_raw) if hardmode_raw else False
    bosses = bool(type_value and "boss" in type_value.lower())
    pre_hardmode = not hardmode

    return {
        "bosses": bosses,
        "hardmode": hardmode,
        "pre-hardmode": pre_hardmode,
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

async def _get_json_with_backoff(
    client: httpx.AsyncClient,
    params: Dict[str, Any],
    context: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """
    GET with 429-aware retry/backoff.
    Honors Retry-After when present, otherwise uses exponential backoff.
    """
    attempts = tenacity_kwargs["stop"]
    base_wait = max(1, tenacity_kwargs["wait"])
    last_error: Optional[Exception] = None

    for attempt in range(attempts):
        try:
            resp = await client.get(MEDIAWIKI_API_URL, params=params, timeout=timeout)
        except httpx.RequestError as exc:
            wait_seconds = int(base_wait * (2 ** attempt) + random.uniform(0, 1))
            logger.warning(
                f"Network error during {context}: {exc}. "
                f"Attempt {attempt + 1}/{attempts}. Retrying in {wait_seconds}s."
            )
            await asyncio.sleep(wait_seconds)
            last_error = exc
            continue

        if resp.status_code != 429:
            resp.raise_for_status()
            return resp.json()

        retry_after = resp.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            wait_seconds = int(retry_after)
        else:
            wait_seconds = int(base_wait * (2 ** attempt) + random.uniform(0, 1))

        logger.warning(
            f"Rate limited (429) during {context}. "
            f"Attempt {attempt + 1}/{attempts}. Waiting {wait_seconds}s before retry."
        )
        await asyncio.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise httpx.HTTPStatusError(
        f"Exceeded retry attempts due to 429 during {context}",
        request=resp.request,
        response=resp,
    )


async def fetch_page_html(pageid: int) -> Optional[str]:
    """
    Fetch the parsed HTML for a given pageid using MediaWiki API (action=parse).
    Returns HTML string or None if not found.
    """
    logger.info(f"Fetching parsed HTML for pageid={pageid}")
    async with httpx.AsyncClient(headers=_request_headers()) as client:
        params = {
            "action": "parse",
            "pageid": pageid,
            "format": "json",
            "prop": "text",
        }
        data = await _get_json_with_backoff(client, params, f"fetch_page_html(pageid={pageid})")
        html = data.get("parse", {}).get("text", {}).get("*", None)
        if not html:
            logger.warning(f"No HTML found for pageid={pageid}")
            return None
        return html


async def fetch_pages_html(
    pageids: List[int],
    concurrency: int = SCRAPER_HTML_CONCURRENCY,
) -> Dict[int, Optional[str]]:
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

async def fetch_category_members(category: str, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Fetch all page members of a given category from the Terraria Wiki.
    """
    logger.info(f"Fetching category members for '{category}'")
    members = []
    cmcontinue = None
    async with httpx.AsyncClient(headers=_request_headers()) as client:
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
            data = await _get_json_with_backoff(client, params, f"fetch_category_members(category={category})")
            members.extend(data["query"]["categorymembers"])
            cmcontinue = data.get("continue", {}).get("cmcontinue")
            if not cmcontinue:
                break
    logger.info(f"Fetched {len(members)} members for category '{category}'")
    return members


# MediaWiki API allows up to 50 pageids per request for normal users, 500 for bots. We'll use 50 for safety.
MAX_PAGEIDS_PER_REQUEST = SCRAPER_MAX_PAGEIDS_PER_REQUEST

async def fetch_pages_content(pageids: List[int]) -> Dict[int, Optional[Dict[str, Any]]]:
    """
    Fetch the wikitext and metadata for a batch of page IDs.
    Returns a dict mapping pageid to page data (or None if not found).
    """
    logger.info(f"Fetching content for {len(pageids)} pageids")
    async with httpx.AsyncClient(headers=_request_headers()) as client:
        params = {
            "action": "query",
            "pageids": "|".join(str(pid) for pid in pageids),
            "prop": "revisions|info",
            "rvprop": "content|timestamp",
            "inprop": "url",
            "format": "json",
        }
        data = await _get_json_with_backoff(client, params, f"fetch_pages_content(pageids={len(pageids)})")
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
            cleaned_sections = _build_cleaned_sections(parsed["sections"])

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
                "bosses": derived_metadata["bosses"],
                "hardmode": derived_metadata["hardmode"],
                "pre-hardmode": derived_metadata["pre-hardmode"],
            }
            articles.append(article)
        if SCRAPER_BATCH_DELAY_SECONDS > 0:
            await asyncio.sleep(SCRAPER_BATCH_DELAY_SECONDS)
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


async def fetch_pageids_by_titles(titles: List[str]) -> Dict[str, int]:
    """
    Resolve page titles to their page IDs using the MediaWiki API.
    Returns a dict mapping title -> pageid (only for pages that exist).
    """
    logger.info(f"Resolving {len(titles)} page titles to pageids")
    result = {}
    async with httpx.AsyncClient(headers=_request_headers()) as client:
        # MediaWiki API accepts up to 50 titles per request
        for i in range(0, len(titles), 50):
            batch_titles = titles[i:i+50]
            params = {
                "action": "query",
                "titles": "|".join(batch_titles),
                "format": "json",
            }
            data = await _get_json_with_backoff(client, params, f"fetch_pageids_by_titles(batch {i//50 + 1})")
            pages = data.get("query", {}).get("pages", {})
            for page in pages.values():
                if "missing" not in page and "pageid" in page:
                    result[page["title"]] = page["pageid"]
                elif "missing" in page:
                    logger.warning(f"Page not found: {page.get('title', 'Unknown')}")
    logger.info(f"Resolved {len(result)} page titles to pageids")
    return result


async def scrape_specific_pages(
    titles: Optional[List[str]] = None,
    pageids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Scrape specific pages by their titles or page IDs.
    
    Args:
        titles: List of page titles to scrape (e.g., ["Zenith", "Terra Blade", "Moon Lord"])
        pageids: List of page IDs to scrape directly
        
    Returns:
        List of article dicts with metadata and content.
    """
    if not titles and not pageids:
        logger.warning("No titles or pageids provided to scrape_specific_pages")
        return []
    
    # Resolve titles to pageids if provided
    all_pageids = list(pageids) if pageids else []
    if titles:
        title_to_pageid = await fetch_pageids_by_titles(titles)
        all_pageids.extend(title_to_pageid.values())
    
    if not all_pageids:
        logger.warning("No valid pageids found to scrape")
        return []
    
    # Deduplicate pageids
    all_pageids = list(set(all_pageids))
    logger.info(f"Scraping {len(all_pageids)} specific pages")
    
    articles = []
    for i in range(0, len(all_pageids), MAX_PAGEIDS_PER_REQUEST):
        batch_ids = all_pageids[i:i+MAX_PAGEIDS_PER_REQUEST]
        pages = await fetch_pages_content(batch_ids)
        html_by_pageid = await fetch_pages_html(batch_ids)
        
        for pageid, page in pages.items():
            if not page:
                continue
            page_html = html_by_pageid.get(pageid)
            parsed = extract_infobox_and_sections(page_html) if page_html else {"infobox": {}, "sections": []}
            cleaned_sections = _build_cleaned_sections(parsed["sections"])

            derived_metadata = _extract_domain_metadata(parsed["infobox"])
            article = {
                "pageid": pageid,
                "title": page["title"],
                "category": "specific",  # Mark as manually specified
                "source_url": page.get("fullurl", ""),
                "last_updated": page["revisions"][0]["timestamp"] if page.get("revisions") else None,
                "wikitext": page["revisions"][0]["*"] if page.get("revisions") and "*" in page["revisions"][0] else "",
                "html": page_html or "",
                "infobox": parsed["infobox"],
                "sections": cleaned_sections,
                "cleaned_text": "\n\n".join(section["text"] for section in cleaned_sections),
                "bosses": derived_metadata["bosses"],
                "hardmode": derived_metadata["hardmode"],
                "pre-hardmode": derived_metadata["pre-hardmode"],
            }
            articles.append(article)
        
        if SCRAPER_BATCH_DELAY_SECONDS > 0:
            await asyncio.sleep(SCRAPER_BATCH_DELAY_SECONDS)
    
    logger.info(f"Scraped {len(articles)} specific pages")
    return articles
