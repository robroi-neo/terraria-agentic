# Terraria Agentic RAG API

This project provides an agentic Retrieval-Augmented Generation (RAG) API for Terraria gameplay advice, weapon comparison, and context-aware chat using Gemini LLM and ChromaDB.

## Features
- FastAPI endpoint for chat and health check
- Agentic workflow with constraint clarification
- RAG pipeline using ChromaDB vector store
- Weapon comparison logic (DPS ranking)
- Configurable system prompt

## Setup
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure environment:**
   - Set API keys and model names in `.env` or `config.py`.
   - Ensure ChromaDB is initialized and contains embedded context chunks.
3. **Run the API server:**
   ```bash
   uvicorn src.api.api:app --reload
   ```

## Usage
- **Health check:**
  ```bash
  curl http://localhost:8000/ping
  ```
- **Chat endpoint:**
  ```bash
  curl -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"user_input": "Compare weapons for my character.", "player_context": {"class": "Warrior", "level": 10}}'
  ```

## Testing
Run unit/integration tests with pytest:
```bash
pytest tests/test_api.py
```

## Customization
- Edit the system prompt in `config.py` to change agent behavior.
- Add more domain logic or context chunking as needed.

## Manual Testing
- Use the `/chat` endpoint with different payloads to test clarification, RAG, and weapon comparison features.
- Inspect responses for structured output and context usage.
