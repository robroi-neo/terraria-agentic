"""
Embedding module using BAAI/bge-base-en-v1.5 for generating dense vector embeddings.
Integrates with the chunker pipeline and stores results in ChromaDB via ChromaIndexer.
"""

import asyncio
from typing import List, Dict, Any


import torch
from transformers import AutoTokenizer, AutoModel
from loguru import logger
from config import EMBEDDER_MODEL, IS_DEVELOPMENT, HUGGINFACE_API_KEY
import requests

BGE_PASSAGE_PREFIX = ""
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class BGEEmbedder:
    def __init__(
        self,
        model_name: str = EMBEDDER_MODEL,
        device: str | None = None,
        batch_size: int = 32,
    ) -> None:
        """
        Parameters
        ----------
        model_name : HuggingFace model identifier.
        device     : 'cuda', 'mps', or 'cpu'. Auto-detected when None.
        batch_size : Number of texts to encode per forward pass.
        """
        self.model_name = model_name
        self.batch_size = batch_size

        self.is_development = IS_DEVELOPMENT
        if self.is_development:
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
            logger.info(f"[DEV] Loading BGE model '{model_name}' on device '{self.device}' ...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            logger.info("[DEV] BGE model loaded successfully.")
        else:
            logger.info("[PROD] Using Hugging Face Inference API for embeddings.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------


    def _mean_pool_cls(self, model_output: Any, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        BGE recommends using the [CLS] token representation (index 0).
        """
        return model_output.last_hidden_state[:, 0]  # (batch, hidden)


    def _encode(self, texts: List[str]) -> List[List[float]]:
        if self.is_development:
            # Local model
            with torch.no_grad():
                all_embeddings: List[torch.Tensor] = []
                for i in range(0, len(texts), self.batch_size):
                    batch = texts[i : i + self.batch_size]
                    encoded = self.tokenizer(
                        batch,
                        padding=True,
                        truncation=True,
                        max_length=512,
                        return_tensors="pt",
                    ).to(self.device)
                    output = self.model(**encoded)
                    embeddings = self._mean_pool_cls(output, encoded["attention_mask"])
                    embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                    all_embeddings.append(embeddings.cpu())
                combined = torch.cat(all_embeddings, dim=0)
                return combined.tolist()
        else:
            # Use Hugging Face Inference API
            api_url = f"https://router.huggingface.co/hf-inference/models/{self.model_name}"
            headers = {"Authorization": f"Bearer {HUGGINFACE_API_KEY}"}
            results = []
            for text in texts:
                response = requests.post(api_url, headers=headers, json={"inputs": text})
                if response.status_code == 200:
                    embedding = response.json()
                    # If the output is nested (batch, seq_len, hidden), take [0][0] or flatten as needed
                    if isinstance(embedding, list) and isinstance(embedding[0], list):
                        # If output is [1, hidden]
                        if len(embedding) == 1:
                            embedding = embedding[0]
                        # If output is [seq_len, hidden], take first token (CLS)
                        elif len(embedding) > 1 and isinstance(embedding[0][0], float):
                            embedding = embedding[0]
                        elif len(embedding) > 1 and isinstance(embedding[0], list):
                            embedding = embedding[0][0]
                    results.append(embedding)
                else:
                    logger.error(f"Hugging Face API error: {response.status_code} {response.text}")
                    results.append([0.0] * 768)  # fallback
            return results

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_passages(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of document passages / chunks.

        Parameters
        ----------
        texts : Raw text strings (already cleaned / chunked).

        Returns
        -------
        List of 768-dimensional float vectors.
        """
        if not texts:
            return []
        prefixed = [BGE_PASSAGE_PREFIX + t for t in texts]
        logger.info(f"Embedding {len(texts)} passage(s) ...")
        vectors = self._encode(prefixed)
        logger.info(f"Finished embedding {len(vectors)} passage(s).")
        return vectors

    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single user query with the BGE query prefix.

        Returns
        -------
        768-dimensional float vector.
        """
        prefixed = BGE_QUERY_PREFIX + query
        if not self.is_development:
            logger.info("Embedding query using Hugging Face Inference API.")
        logger.info(f"Embedding query: '{query[:80]}...'")
        vector = self._encode([prefixed])[0]
        return vector


# ---------------------------------------------------------------------------
# Pipeline: chunks → embed → ChromaDB
# ---------------------------------------------------------------------------

async def embed_and_index(
    chunks: List[Dict[str, Any]],
    embedder: BGEEmbedder,
    indexer: Any,  # ChromaIndexer from indexer.py
) -> None:
    """
    Attach BGE embeddings to chunk dicts and persist them in ChromaDB.

    Parameters
    ----------
    chunks   : Output of chunker.chunk_articles() — list of chunk dicts.
               Each dict must contain at least: 'text', 'page_title',
               'chunk_index', 'source_url', 'category', 'last_updated'.
    embedder : Initialised BGEEmbedder instance.
    indexer  : Initialised ChromaIndexer instance (from indexer.py).
    """
    if not chunks:
        logger.warning("embed_and_index received an empty chunk list — nothing to do.")
        return

    texts = [c["text"] for c in chunks]
    vectors = embedder.embed_passages(texts)

    # Attach embedding in-place
    enriched: List[Dict[str, Any]] = []
    for chunk, vector in zip(chunks, vectors):
        enriched.append({**chunk, "embedding": vector})

    await indexer.add_chunks(enriched)
    logger.info(f"Indexed {len(enriched)} embedded chunks into ChromaDB.")