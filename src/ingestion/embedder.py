"""
Embedding module using BAAI/bge-base-en-v1.5 for generating dense vector embeddings.
Integrates with the chunker pipeline and stores results in ChromaDB via ChromaIndexer.
"""

import asyncio
from typing import List, Dict, Any

import torch
from transformers import AutoTokenizer, AutoModel
from loguru import logger
from config import EMBEDDER_MODEL

# ---------------------------------------------------------------------------
# BGE Embedder
# ---------------------------------------------------------------------------

# BGE models perform best with this instruction prefix for passage embedding.
# For queries, a different prefix ("Represent this sentence: ...") is used.
BGE_PASSAGE_PREFIX = ""          # passages: no prefix needed for bge-base
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class BGEEmbedder:
    """
    Wraps BAAI/bge-base-en-v1.5 for generating 768-dimensional embeddings.

    Usage
    -----
    embedder = BGEEmbedder()
    vectors  = embedder.embed_passages(["text one", "text two"])
    query_v  = embedder.embed_query("what is a sword?")
    """

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
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = batch_size

        logger.info(f"Loading BGE model '{model_name}' on device '{self.device}' ...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        logger.info("BGE model loaded successfully.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mean_pool_cls(self, model_output: Any, attention_mask: torch.Tensor) -> torch.Tensor:
        """
        BGE recommends using the [CLS] token representation (index 0).
        """
        return model_output.last_hidden_state[:, 0]  # (batch, hidden)

    @torch.no_grad()
    def _encode(self, texts: List[str]) -> List[List[float]]:
        """
        Tokenise, forward-pass, and L2-normalise a list of texts.
        Returns a list of plain Python float lists (ChromaDB-compatible).
        """
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

            # L2 normalisation (required by BGE for cosine similarity)
            embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            all_embeddings.append(embeddings.cpu())

        combined = torch.cat(all_embeddings, dim=0)  # (N, 768)
        return combined.tolist()

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


# ---------------------------------------------------------------------------
# Standalone smoke-test / entry-point
# ---------------------------------------------------------------------------

async def _demo() -> None:
    """
    Quick smoke-test: embed two dummy chunks and query them back.
    Run with:  python embedder.py
    """
    from src.ingestion.indexer import ChromaIndexer  # adjust import path as needed

    embedder = BGEEmbedder()
    indexer = ChromaIndexer()  # uses defaults from config

    dummy_chunks: List[Dict[str, Any]] = [
        {
            "text": "The Iron Sword is a melee weapon crafted from Iron Bars.",
            "chunk_index": 0,
            "source_url": "https://terraria.wiki.gg/Iron_Sword",
            "page_title": "Iron Sword",
            "category": "Weapons",
            "last_updated": "2024-01-01T00:00:00Z",
        },
        {
            "text": "Terraria is a 2D sandbox adventure game developed by Re-Logic.",
            "chunk_index": 0,
            "source_url": "https://terraria.wiki.gg/Terraria",
            "page_title": "Terraria",
            "category": "General",
            "last_updated": "2024-01-01T00:00:00Z",
        },
    ]

    await embed_and_index(dummy_chunks, embedder, indexer)

    # Query
    query_vec = embedder.embed_query("rawr")
    results = await indexer.query(query_vec, n_results=2)
    for r in results:
        print(f"[{r['page_title']}] dist={r['distance']:.4f} — {r['text'][:80]}")


if __name__ == "__main__":
    asyncio.run(_demo())