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

# Retrieval config, this indicates how many chunks will be retrieved 
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", 3))

# MediaWiki API
MEDIAWIKI_API_URL: str = os.getenv("MEDIAWIKI_API_URL", "https://terraria.wiki.gg/api.php")

USER_AGENT: str = os.getenv(
    "USER_AGENT",
    "terraria-agentic/1.0 (personal RAG indexing of Terraria wiki pages; contact: your-email@example.com)",
)
REQUEST_FROM_EMAIL: str = os.getenv("REQUEST_FROM_EMAIL", "your-email@example.com")
MEDIAWIKI_CATEGORIES: List[str] = [
    # To have info about bosses
    "Boss_NPCs",
    # To have info about summoned bosses
    "Summoned_events",
    # To have info about tools
    "Tool_items",
    # includes boss summons
    "Summoning_items",

    # Difficulty Mode
    "Expert_Mode_content",
    "Journey_Mode_content",
    "Master_Mode_content",
]
# List of specific page titles to scrape (optional, can be empty)
SCRAPE_PAGES: List[str] = [
    # Example: "Zenith", "Terra Blade", "Moon Lord"
    "Terraria",
    "Buffs",
    "Debuffs",
    "Bosses",
    "Pre-Hardmode",
    "Hardmode",
    "Hardmode_conversion",
    "Difficulty",
    "Game_mechanics"
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