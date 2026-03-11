# Terraria Agentic RAG

An agentic Retrieval-Augmented Generation (RAG) assistant for Terraria gameplay advice. It scrapes and indexes the Terraria wiki, then answers questions about bosses, progression, items, and strategies using a multi-step LangGraph pipeline grounded in retrieved wiki context.

**Live demo:** https://terraria-assistant.streamlit.app/

---

## Architecture

### Ingestion Pipeline

The ingestion pipeline prepares the knowledge base that the agent queries at runtime.

```
scrape → chunk → embed → index (ChromaDB)
```

1. **Scraper** (`src/ingestion/scraper.py`): Fetches wiki pages via the MediaWiki API and HTML scraping. Supports two modes:
   - `standard`: scrapes pages by category or explicit title list.
   - `walkthrough_recursive`: starts from a root guide page (e.g. `Guide:Walkthrough`) and recursively follows in-domain links up to a configurable depth and page cap.
   Boilerplate, navboxes, footnotes, and low-value sections are stripped during scraping.

2. **Chunker** (`src/ingestion/chunker.py`): Splits article text into overlapping token-based chunks while preserving section hierarchy metadata (`section_path`, `section_title`, `page_title`, `source_url`, etc.).

3. **Embedder** (`src/ingestion/embedder.py`): Produces dense vector embeddings using a BGE model (e.g. `BAAI/bge-base-en-v1.5`) loaded locally via HuggingFace.

4. **Indexer** (`src/ingestion/indexer.py`): Stores embeddings and metadata in ChromaDB. The walkthrough mode creates two separate collections: one for the root walkthrough page and one for recursively discovered linked pages.

### Query Pipeline

The query pipeline is an agentic LangGraph graph executed for every user message.

```
route_query → clarify_query → rewrite_query → retrieve → grade_documents → generate_answer
```

1. **route_query** (`src/agent/nodes.py`): Decides whether the question needs wiki retrieval (`rag`) or can be answered directly (`direct`).
2. **clarify_query**: Checks if the query has enough specificity. If not, returns a clarifying question to the user instead of proceeding.
3. **rewrite_query**: Normalises the query for optimal retrieval.
4. **retrieve**: Embeds the query and fetches the top-k most similar chunks from ChromaDB. If walkthrough split retrieval is enabled, queries both collections and merges results with root-page priority.
5. **grade_documents**: Scores each retrieved chunk for relevance. Irrelevant chunks are dropped. If none pass, the pipeline loops back to rewrite and retry.
6. **generate_answer**: Produces a grounded answer from the surviving chunks using the configured LLM.

The graph state (`src/agent/state.py`) carries the query, retrieved chunks, graded chunks, final answer, conversation history, and gameplay assumptions (difficulty, class, character) across nodes.

---

## Setup

### 1. Install dependencies

```
pip install -r requirements.txt
```

> **Note:** `torch` and `transformers` are large (~1–2 GB). A GPU is not required but will speed up embedding significantly.

### 2. Configure environment

Copy `.env.example` to `.env` and fill in the required values:

```
cp .env.example .env
```

See [Development vs Production](#development-vs-production) below for which keys are required in each mode.

### 3. Run ingestion

Before querying, you must populate the ChromaDB database. Run one of the ingestion modes below.

---

## Running the Ingestion Pipeline

### Standard mode

Scrapes pages by MediaWiki category and/or explicit title list as configured in `config.py`:

```
python -m scripts.run_ingestion
```

With overrides:

```
python -m scripts.run_ingestion --categories Boss_NPCs Weapons --max-articles 50
```

### Walkthrough recursive mode

Starts from `Guide:Walkthrough` and recursively crawls all in-domain linked wiki pages up to the specified depth:

```
python -m scripts.run_ingestion --mode walkthrough_recursive --root-page "Guide:Walkthrough" --max-depth 1 --max-pages 120 --collection terraria_walkthrough
```

Key options:

| Option | Default | Description |
|---|---|---|
| `--root-page` | `Guide:Walkthrough` | Root page to start crawling from |
| `--max-depth` | `1` | How many link hops to follow |
| `--max-pages` | `120` | Maximum pages to process |
| `--collection` | (config) | Base name for ChromaDB collections |
| `--chroma-path` | (config) | Override ChromaDB storage directory |
| `--query-smoke` | (none) | Optional query to run after indexing as a sanity check |

The walkthrough mode creates two collections: `<collection>_walkthrough_root` and `<collection>_walkthrough_links`.

---

## Running the Streamlit App

```
streamlit run app_streamlit.py
```

Opens a chat UI at `http://localhost:8501`. Type any Terraria question to query the agent.

---

## Running the CLI Chat

```
python main.py
```

Interactive terminal chat using the same agentic pipeline as the Streamlit app. Type `quit` or `exit` to stop.

---

## Development vs Production

The `ENV` variable controls whether API keys are loaded from `.env`. Set it in your `.env` file.

### Development (default)

```
ENV=development
```

- API keys (`GROQ_API_KEY`, `HUGGINFACE_API_KEY`) are **not** loaded.
- Uses a local Ollama model specified by `OLLAMA_MODEL`.
- Suitable for local testing without any external API access.

### Production

```
ENV=production
```

- API keys **are** loaded from `.env` and required for the LLM provider.
- Set `GROQ_API_KEY` if using Groq-hosted models (e.g. `llama-3.3-70b-versatile`).
- The `OLLAMA_MODEL` variable is ignored when a Groq key is active.

---

## Testing

Run a specific test file:

```
python -m pytest tests/ingestion/test_pipeline_integration.py
python -m pytest tests/ingestion/test_walkthrough_recursive.py
```

Run evaluation tests (requires a populated ChromaDB):

```
python -m tests.evaluate
python -m tests.evaluate_performance
```

> **Note:** Tests require all dependencies from `requirements.txt` to be installed, including `loguru` and `python-dotenv`.

---

## Project Structure

> **Note:** The `chromadb/` folder is committed to this repository so the Streamlit app works out of the box without running ingestion first. It contains a pre-built index from `Guide:Walkthrough`. To rebuild or update it, run the ingestion pipeline.

```
chromadb/       # Pre-built ChromaDB index (Guide:Walkthrough) — committed for Streamlit use
src/
  agent/         # LangGraph nodes, graph wiring, state, prompts, LLM provider
  ingestion/     # Scraper, chunker, embedder, indexer
  api/           # (reserved for future HTTP API)
  utils/         # DB loader and shared utilities
scripts/
  run_ingestion.py   # CLI entrypoint for ingestion pipeline
tests/
  ingestion/         # Scraper and pipeline integration tests
  evaluate.py        # Retrieval quality evaluation
  evaluate_performance.py
config.py            # All configuration constants loaded from .env
main.py              # CLI chat entrypoint
app_streamlit.py     # Streamlit chat UI
```
