"""
Configuration and environment variable management for the Terraria Progression Assistant.
Loads secrets and constants from a .env file using python-dotenv.
"""
import os
from dotenv import load_dotenv
from typing import List

# Load environment variables from .env file
load_dotenv()

# Google API
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "")

# EMBEDDER MODEL
EMBEDDER_MODEL: str = os.getenv("EMBEDDER_MODEL", "")

# ChromaDB
CHROMADB_PATH: str = os.getenv("CHROMADB_PATH", "./chromadb")
CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "terraria_wiki")

# RATE LIMIT
REQUEST_PER_MINUTE: int = int(os.getenv("REQUEST_PER_MINUTE",5))

# MediaWiki API
MEDIAWIKI_API_URL: str = os.getenv("MEDIAWIKI_API_URL", "https://terraria.wiki.gg/api.php")
MEDIAWIKI_CATEGORIES: List[str] = [
    "Bosses",
    "Weapons",
    "Armor",
    "Accessories",
    "Enemies",
    "NPCs"
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
    "stop": int(os.getenv("RETRY_STOP", 5)),
}

# Safety checks

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is required in .env")
if not GEMINI_MODEL:
    raise RuntimeError("GEMINI_MODEL is required in .env")
if not EMBEDDER_MODEL:
    raise RuntimeError("EMBEDDER_MODEL is required in .env")