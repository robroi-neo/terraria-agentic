"""
Configuration and environment variable management for the Terraria Progression Assistant.
Loads secrets and constants from a .env file using python-dotenv.
"""
import os
from dotenv import load_dotenv
from typing import List


# Load environment variables from .env file
load_dotenv()

# Determine environment
ENV = os.getenv("ENV", "development")
IS_DEVELOPMENT = ENV == "development"

# Ollama
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# EMBEDDER MODEL
EMBEDDER_MODEL: str = os.getenv("EMBEDDER_MODEL", "")
EMBEDDER_DEVICE: str = os.getenv("EMBEDDER_DEVICE", "auto").strip().lower()

# Only load API keys if not in development
if not IS_DEVELOPMENT:
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    HUGGINFACE_API_KEY: str = os.getenv("HUGGINFACE_API_KEY", "")
else:
    GROQ_API_KEY: str = None
    HUGGINFACE_API_KEY: str = None

# ChromaDB
CHROMADB_PATH: str = os.getenv("CHROMADB_PATH", "./chromadb")
CHROMADB_COLLECTION: str = os.getenv("CHROMADB_COLLECTION", "terraria_wiki")

# RATE LIMIT
REQUEST_PER_MINUTE: int = int(os.getenv("REQUEST_PER_MINUTE",5))
SCRAPER_MAX_PAGEIDS_PER_REQUEST: int = int(os.getenv("SCRAPER_MAX_PAGEIDS_PER_REQUEST", 50))
SCRAPER_HTML_CONCURRENCY: int = int(os.getenv("SCRAPER_HTML_CONCURRENCY", 2))
SCRAPER_BATCH_DELAY_SECONDS: float = float(os.getenv("SCRAPER_BATCH_DELAY_SECONDS", 0.75))
SCRAPER_MIN_SECTION_CHARS: int = int(os.getenv("SCRAPER_MIN_SECTION_CHARS", 80))
GUIDE_MIN_SECTION_CHARS: int = int(os.getenv("GUIDE_MIN_SECTION_CHARS", 140))

# Scraper curation defaults
SCRAPER_EXCLUDED_SECTION_TITLES: List[str] = [
    "references",
    "notes",
    "external links",
    "see also",
    "history",
    "trivia",
    "gallery",
    "footnotes",
    "additional links",
]

SCRAPER_DROP_SELECTORS: List[str] = [
    ".mw-editsection",
    ".navbox",
    ".metadata",
    "sup.reference",
    ".mw-references-wrap",
    "ol.references",
    ".reflist",
    ".catlinks",
    ".printfooter",
    ".hatnote",
    ".mw-cite-backlink",
    ".reference-text",
]

SCRAPER_BOILERPLATE_PATTERNS: List[str] = [
    r"desktop\s+version\s*console\s+version\s*mobile\s+version",
    r"desktop\s*/\s*console\s*/\s*mobile\s*-?\s*only\s+content\s*:?\s*this\s+information\s+applies\s+only\s+to\s+the\s+desktop\s*,\s*console\s*,\s*and\s+mobile\s+versions\s+of\s+terraria\s*\.?",
    r"this\s+is\s+the\s+main\s+page\s+whose\s+information\s+applies\s+to\s+the\s+desktop\s*,\s*console\s*,\s*and\s+mobile\s+versions\s+of\s+terraria\s*\.?",
    r"for\s+the\s+differences\s+of\s+this\s+information\s+on\s+old\s*-?\s*gen\s+console\s+and\s+3ds\s*,\s*see\s+legacy:[^.]+\.?",
    r"for\s+the\s+differences\s+on\s+old\s*-?\s*gen\s+console\s+and\s+3ds\s*,\s*see\s+legacy:[^.]+\.?",
    r"for\s+the\s+differences\s+of\s+this\s+information\s+on[^.]*legacy:[^.]+\.?",
    r"this\s+is\s+a\s+guide\s+page[^.]*\.?",
]

# Retrieval config, this indicates how many chunks will be retrieved 
RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", 5))
RETRIEVAL_ENABLE_WALKTHROUGH_SPLIT: bool = os.getenv("RETRIEVAL_ENABLE_WALKTHROUGH_SPLIT", "false").strip().lower() == "true"
RETRIEVAL_WALKTHROUGH_ROOT_COLLECTION: str = os.getenv(
    "RETRIEVAL_WALKTHROUGH_ROOT_COLLECTION",
    f"{CHROMADB_COLLECTION}_walkthrough_root",
)
RETRIEVAL_WALKTHROUGH_LINKS_COLLECTION: str = os.getenv(
    "RETRIEVAL_WALKTHROUGH_LINKS_COLLECTION",
    f"{CHROMADB_COLLECTION}_walkthrough_links",
)
RETRIEVAL_WALKTHROUGH_ROOT_TOP_K: int = int(os.getenv("RETRIEVAL_WALKTHROUGH_ROOT_TOP_K", RETRIEVAL_TOP_K))
RETRIEVAL_WALKTHROUGH_LINKS_TOP_K: int = int(os.getenv("RETRIEVAL_WALKTHROUGH_LINKS_TOP_K", RETRIEVAL_TOP_K))
RETRIEVAL_WALKTHROUGH_ROOT_DISTANCE_BONUS: float = float(os.getenv("RETRIEVAL_WALKTHROUGH_ROOT_DISTANCE_BONUS", 0.05))

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
    # Items
    "Tool_items",
    "Weapon_items",
    "Potion_items",
    "Healing_items",
    "Bar_items",
    "Ammunition_items",
    "Armor_items",

    # special case items
    "Boots_items",
    "Gem_items",
    "Souls",
    "Developer_items",
    # includes boss summons
    "Boss_summon_items",
    "Event_summon_items",
    "Mount_summon_items",
    # Events
    "Random_events",
    "Seasonal_events",
    "Summoned_events",
    
    # Mechanics
    "Buffs",
    "Debuffs",
    "Liquids",
    "Modifiers",
    "Buffs",

    # Difficulty Mode
    "Expert_Mode_content",
    "Journey_Mode_content",
    "Master_Mode_content",

    "Crossover_content",
]
# List of specific page titles to scrape (optional, can be empty)
SCRAPE_PAGES: List[str] = [
    "Terraria",
    "Difficulty",

]

# Chunking
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", 512))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", 50))
GUIDE_CHUNK_SIZE: int = int(os.getenv("GUIDE_CHUNK_SIZE", 768))
GUIDE_CHUNK_OVERLAP: int = int(os.getenv("GUIDE_CHUNK_OVERLAP", 120))

# Walkthrough recursive ingestion
WALKTHROUGH_ROOT_PAGE: str = os.getenv("WALKTHROUGH_ROOT_PAGE", "Guide:Walkthrough")
WALKTHROUGH_MAX_DEPTH: int = int(os.getenv("WALKTHROUGH_MAX_DEPTH", 1))
WALKTHROUGH_MAX_PAGES: int = int(os.getenv("WALKTHROUGH_MAX_PAGES", 120))
WALKTHROUGH_INCLUDE_GUIDE_LINKS: bool = os.getenv("WALKTHROUGH_INCLUDE_GUIDE_LINKS", "false").strip().lower() == "true"
WALKTHROUGH_EXCLUDED_NAMESPACES: List[str] = [
    "file",
    "template",
    "talk",
    "category",
    "special",
    "user",
    "legacy",
]

WALKTHROUGH_ROOT_COLLECTION_SUFFIX: str = os.getenv("WALKTHROUGH_ROOT_COLLECTION_SUFFIX", "walkthrough_root")
WALKTHROUGH_LINKS_COLLECTION_SUFFIX: str = os.getenv("WALKTHROUGH_LINKS_COLLECTION_SUFFIX", "walkthrough_links")

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
    