"""
Async embedding utility for chunked documents using OpenAI's text-embedding-3-small model.
"""
from typing import List, Dict, Any
import openai
import asyncio
from tenacity import retry, stop_after_attempt, wait_fixed
from loguru import logger
from ..config import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, tenacity_kwargs

openai.api_key = OPENAI_API_KEY

@retry(stop=stop_after_attempt(tenacity_kwargs["stop"]), wait=wait_fixed(tenacity_kwargs["wait"]))
async def embed_text(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of texts using OpenAI's text-embedding-3-small model.
    """
    logger.info(f"Embedding {len(texts)} texts with OpenAI model '{OPENAI_EMBEDDING_MODEL}'")
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: openai.embeddings.create(
            input=texts,
            model=OPENAI_EMBEDDING_MODEL
        )
    )
    embeddings = [d["embedding"] for d in response["data"]]
    logger.info(f"Generated {len(embeddings)} embeddings")
    return embeddings

def batch_chunks(chunks: List[Dict[str, Any]], batch_size: int = 64) -> List[List[Dict[str, Any]]]:
    """
    Split chunks into batches for efficient embedding.
    """
    return [chunks[i:i+batch_size] for i in range(0, len(chunks), batch_size)]

async def embed_chunks(chunks: List[Dict[str, Any]], batch_size: int = 64) -> List[Dict[str, Any]]:
    """
    Embed all chunk dicts and return with 'embedding' field added.
    """
    all_embedded = []
    for batch in batch_chunks(chunks, batch_size):
        texts = [c["text"] for c in batch]
        embeddings = await embed_text(texts)
        for chunk, emb in zip(batch, embeddings):
            chunk_with_emb = dict(chunk)
            chunk_with_emb["embedding"] = emb
            all_embedded.append(chunk_with_emb)
    logger.info(f"Embedded {len(all_embedded)} chunks total")
    return all_embedded
