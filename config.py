"""
Configuration and environment variable management for the Terraria Progression Assistant.
Loads secrets and constants from a .env file using python-dotenv.
"""
import os
from dotenv import load_dotenv
from typing import List

# Load environment variables from .env file
load_dotenv()

# Ollama
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# EMBEDDER MODEL
EMBEDDER_MODEL: str = os.getenv("EMBEDDER_MODEL", "")

# ChromaDB
CHROMADB_PATH: str = os.getenv("CHROMADB_PATH", "./chromadb")
CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "terraria_wiki")

# RATE LIMIT
REQUEST_PER_MINUTE: int = int(os.getenv("REQUEST_PER_MINUTE",5))
SCRAPER_MAX_PAGEIDS_PER_REQUEST: int = int(os.getenv("SCRAPER_MAX_PAGEIDS_PER_REQUEST", 50))
SCRAPER_HTML_CONCURRENCY: int = int(os.getenv("SCRAPER_HTML_CONCURRENCY", 2))
SCRAPER_BATCH_DELAY_SECONDS: float = float(os.getenv("SCRAPER_BATCH_DELAY_SECONDS", 0.75))

# MediaWiki API
MEDIAWIKI_API_URL: str = os.getenv("MEDIAWIKI_API_URL", "https://terraria.wiki.gg/api.php")

USER_AGENT: str = os.getenv(
    "USER_AGENT",
    "terraria-agentic/1.0 (personal RAG indexing of Terraria wiki pages; contact: your-email@example.com)",
)
REQUEST_FROM_EMAIL: str = os.getenv("REQUEST_FROM_EMAIL", "your-email@example.com")
MEDIAWIKI_CATEGORIES: List[str] = [
    "Crafting_material_items",
    "Acquired_through",
    "Ammunition_items",
    "Armor_items",
    "Hardmode-only_items",
    "Healing_items",
    "Informational_items",
    "Miscellaneous_items",
    "Consumable_items",
    "Set_items",
    "Storage_items",
    "Summoning_items",
    "Tool_items",
    "Weapon_items",
    "Key_items",
    "Mechanism_items",
    "Game_mechanics",
    "Events",
    "Crossover_content",
    "Environments",
    "Events",
    "NPCs",
]

# Chunking
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 512))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 50))

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# FastAPI
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", 8000))

# Retry settings
tenacity_kwargs = {
    "wait": int(os.getenv("RETRY_WAIT", 2)),
    "stop": int(os.getenv("RETRY_STOP", 8)),
}

# Safety checks

if not EMBEDDER_MODEL:
    raise RuntimeError("EMBEDDER_MODEL is required in .env")