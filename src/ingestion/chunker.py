"""
Text chunking utility for splitting wiki articles into 512-token chunks with 50-token overlap.
Uses tiktoken for tokenization.
"""
from typing import List, Dict, Any
from tiktoken import get_encoding
from loguru import logger
from config import CHUNK_SIZE, CHUNK_OVERLAP, GUIDE_CHUNK_SIZE, GUIDE_CHUNK_OVERLAP

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP, encoding_name: str = "cl100k_base") -> List[str]:
    """
    Split text into overlapping chunks by token count.
    """
    enc = get_encoding(encoding_name)
    tokens = enc.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk = enc.decode(tokens[start:end])
        chunks.append(chunk)
        if end == len(tokens):
            break
        start += chunk_size - overlap
    logger.info(f"Chunked text into {len(chunks)} chunks (size={chunk_size}, overlap={overlap})")
    return chunks

def chunk_article(article: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk a single article dict into a list of chunk dicts with metadata.
    """
    sections = article.get("sections") or []
    chunk_dicts = []
    is_root_walkthrough = bool(article.get("is_root_walkthrough"))
    chunk_size = GUIDE_CHUNK_SIZE if is_root_walkthrough else CHUNK_SIZE
    overlap = GUIDE_CHUNK_OVERLAP if is_root_walkthrough else CHUNK_OVERLAP

    if sections:
        chunk_idx = 0
        for section_index, section in enumerate(sections):
            section_text = section.get("text", "")
            if not section_text:
                continue
            section_chunks = chunk_text(section_text, chunk_size=chunk_size, overlap=overlap)
            for chunk in section_chunks:
                chunk_dicts.append({
                    "text": chunk,
                    "chunk_index": chunk_idx,
                    "section_index": section_index,
                    "section_title": section.get("title", "Untitled"),
                    "section_path": section.get("path", section.get("title", "Untitled")),
                    "source_url": article.get("source_url", ""),
                    "page_title": article.get("title", ""),
                    "pageid": article.get("pageid"),
                    "category": article.get("category", ""),
                    "last_updated": article.get("last_updated", ""),
                    "bosses": article.get("bosses"),
                    "hardmode": article.get("hardmode"),
                    "pre-hardmode": article.get("pre-hardmode"),
                    "source_partition": article.get("source_partition", "core"),
                    "is_root_walkthrough": article.get("is_root_walkthrough", False),
                    "discovered_from": article.get("discovered_from", ""),
                    "crawl_depth": article.get("crawl_depth", 0),
                    "root_page_title": article.get("root_page_title", ""),
                })
                chunk_idx += 1
    else:
        text = article.get("cleaned_text", "")
        if not text:
            return []
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        for idx, chunk in enumerate(chunks):
            chunk_dicts.append({
                "text": chunk,
                "chunk_index": idx,
                "source_url": article.get("source_url", ""),
                "page_title": article.get("title", ""),
                "pageid": article.get("pageid"),
                "category": article.get("category", ""),
                "last_updated": article.get("last_updated", ""),
                "bosses": article.get("bosses"),
                "hardmode": article.get("hardmode"),
                "pre-hardmode": article.get("pre-hardmode"),
                "source_partition": article.get("source_partition", "core"),
                "is_root_walkthrough": article.get("is_root_walkthrough", False),
                "discovered_from": article.get("discovered_from", ""),
                "crawl_depth": article.get("crawl_depth", 0),
                "root_page_title": article.get("root_page_title", ""),
            })

    logger.info(f"Article '{article.get('title')}' split into {len(chunk_dicts)} chunks")
    return chunk_dicts

def chunk_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Chunk a list of article dicts into a flat list of chunk dicts.
    Skips duplicate chunk IDs and logs a warning if found.
    """
    all_chunks = []
    seen_ids = set()
    duplicates = []
    for article in articles:
        for chunk in chunk_article(article):
            # Build a unique chunk ID (e.g., pageid:section_index:chunk_index)
            pageid = chunk.get("pageid")
            section_index = chunk.get("section_index", 0)
            chunk_index = chunk.get("chunk_index", 0)
            source_partition = chunk.get("source_partition", "core")
            chunk_id = f"{source_partition}:{pageid}:{section_index}:{chunk_index}"
            if chunk_id in seen_ids:
                duplicates.append(chunk_id)
                continue
            seen_ids.add(chunk_id)
            all_chunks.append(chunk)
    if duplicates:
        logger.warning(f"Skipped {len(duplicates)} duplicated chunk IDs: {', '.join(duplicates[:20])}{'...' if len(duplicates) > 20 else ''}")
    logger.info(f"Total chunks generated (deduplicated): {len(all_chunks)}")
    return all_chunks
