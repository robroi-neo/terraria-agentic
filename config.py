"""
Configuration and environment variable management for the Terraria Progression Assistant.
Loads secrets and constants from a .env file using python-dotenv.
"""
import os
from dotenv import load_dotenv
from typing import List

# Load environment variables from .env file
load_dotenv()

# Anthropic API
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-3-5")

# OpenAI API
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# ChromaDB
CHROMADB_PATH: str = os.getenv("CHROMADB_PATH", "./chromadb")
CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "terraria_wiki")

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
'''
if not ANTHROPIC_API_KEY:
    raise RuntimeError("ANTHROPIC_API_KEY is required in .env")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required in .env")'''
