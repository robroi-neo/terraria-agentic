"""
Async ChromaDB indexer for storing and retrieving embedded document chunks.
"""
from typing import List, Dict, Any, Optional
import chromadb
from loguru import logger
from config import CHROMADB_PATH, CHROMADB_COLLECTION


class ChromaIndexer:
    """
    Handles storage and retrieval of embeddings in ChromaDB.
    """
    def __init__(
        self,
        persist_directory: str = CHROMADB_PATH,
        collection_name: str = CHROMADB_COLLECTION
    ):
        # PersistentClient is the correct API for chromadb >= 0.4.x
        # This writes to disk at `persist_directory` automatically.
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(collection_name)
        logger.info(
            f"ChromaDB collection '{collection_name}' initialized at '{persist_directory}'"
        )

    async def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Add embedded chunks to ChromaDB collection.
        """
        ids = [
            f"{c.get('pageid', c['page_title'])}:{c.get('section_index', 0)}:{c['chunk_index']}"
            for c in chunks
        ]
        embeddings = [c["embedding"] for c in chunks]
        metadatas = []
        for c in chunks:
            metadata = {
                "source_url": c.get("source_url", ""),
                "page_title": c.get("page_title", ""),
                "category": c.get("category", ""),
                "chunk_index": c.get("chunk_index", 0),
                "last_updated": c.get("last_updated", ""),
                "section_index": c.get("section_index", 0),
                "section_title": c.get("section_title", ""),
                "biome": c.get("biome"),
                "hardmode": c.get("hardmode"),
                "damage_type": c.get("damage_type"),
            }
            filtered = {
                key: value
                for key, value in metadata.items()
                if value is not None and (not isinstance(value, str) or value != "")
            }
            metadatas.append(filtered)
        documents = [c["text"] for c in chunks]

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=documents
        )
        logger.info(f"Added {len(chunks)} chunks to ChromaDB collection")

    async def query(
        self,
        query_embedding: List[float],
        n_results: int = 3,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Query ChromaDB for the most similar chunks to the given embedding.
        """
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where or {},
            include=["documents", "metadatas", "distances"]
        )
        hits = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            hit = dict(meta)
            hit["text"] = doc
            hit["distance"] = dist
            hits.append(hit)

        logger.info(f"ChromaDB query returned {len(hits)} results")
        return hits

    async def count(self) -> int:
        """
        Return the number of chunks in the collection.
        """
        count = self.collection.count()
        logger.info(f"ChromaDB collection contains {count} chunks")
        return count