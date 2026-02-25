"""
Text chunking utility for splitting wiki articles into 512-token chunks with 50-token overlap.
Uses tiktoken for tokenization.
"""
from typing import List, Dict, Any
from tiktoken import get_encoding
from loguru import logger
from ..config import CHUNK_SIZE, CHUNK_OVERLAP

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
    text = article.get("wikitext", "")
    if not text:
        return []
    chunks = chunk_text(text)
    chunk_dicts = []
    for idx, chunk in enumerate(chunks):
        chunk_dicts.append({
            "text": chunk,
            "chunk_index": idx,
            "source_url": article.get("source_url", ""),
            "page_title": article.get("title", ""),
            "category": article.get("category", ""),
            "last_updated": article.get("last_updated", ""),
        })
    logger.info(f"Article '{article.get('title')}' split into {len(chunk_dicts)} chunks")
    return chunk_dicts

def chunk_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Chunk a list of article dicts into a flat list of chunk dicts.
    """
    all_chunks = []
    for article in articles:
        all_chunks.extend(chunk_article(article))
    logger.info(f"Total chunks generated: {len(all_chunks)}")
    return all_chunks
