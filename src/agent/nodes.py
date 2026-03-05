'''
Async Functions. Accepts Current State and Returns an Updated State.    
'''

# List of Nodes:
# route_query() # evaluate's if query needs rag or it can be answered directly
# clarify_query() -> evaluates whether the query is specific enough to retrieve //uses llm
# rewrite_query() -> rewrite query into retrieval optimized form
# retrieve() -> calls llm. Embdedds writing, fetches top k //uses llm
# grade_documents() -> top k chunks is actually made here? so is this called betwwen retrieve?
# generate_answer() -> final node

# src/agent/nodes.py

import json
from typing import Any
from loguru import logger

from src.agent.state import AgentState
from src.agent.llm_provider import LLMProvider
import asyncio
import time
from src.agent.prompts import (
    ROUTER_SYSTEM_PROMPT,
    CLARIFIER_SYSTEM_PROMPT,
    REWRITER_SYSTEM_PROMPT,
    GRADER_SYSTEM_PROMPT,
    GENERATOR_SYSTEM_PROMPT,
)
from src.ingestion.embedder import BGEEmbedder
from src.ingestion.indexer import ChromaIndexer
from config import REQUEST_PER_MINUTE, RETRIEVAL_TOP_K



# ---------------------------------------------------------------------------
# Rate Limiter for LLM requests
# ---------------------------------------------------------------------------
class RequestRateLimiter:
    def __init__(self, max_REQUEST_PER_MINUTE=100):
        self.max_requests = max_REQUEST_PER_MINUTE
        self.request_times = []
        self.lock = asyncio.Lock()

    async def wait_for_slot(self):
        async with self.lock:
            now = time.monotonic()
            # Remove timestamps older than 60 seconds
            self.request_times = [t for t in self.request_times if now - t < 60]
            if len(self.request_times) >= self.max_requests:
                sleep_time = 60 - (now - self.request_times[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
            # After waiting, update timestamps
            now = time.monotonic()
            self.request_times = [t for t in self.request_times if now - t < 60]
            self.request_times.append(now)

# Configurable rate limit (default: 5 requests/minute)
rate_limiter = RequestRateLimiter(max_REQUEST_PER_MINUTE=REQUEST_PER_MINUTE)

llm = LLMProvider()
embedder = BGEEmbedder()
indexer = ChromaIndexer()


# ---------------------------------------------------------------------------
# Node 1: route_query
# Decides whether the query needs RAG or can be answered directly
# ---------------------------------------------------------------------------

def _parse_json(response: str, node_name: str) -> dict:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.error(f"[{node_name}] Failed to parse JSON. Raw response was:\n{response}")
        raise

async def route_query(state: AgentState) -> AgentState:
    """
    Claude reads the query and decides:
    - 'rag'    → needs wiki retrieval (items, bosses, crafting, biomes)
    - 'direct' → general/conversational, no retrieval needed
    """
    logger.info(f"[route_query] Routing query: '{state['query']}'")

    history = state.get("conversation_history", [])
    user_message = (
        f"Conversation so far:\n{json.dumps(history)}\n\nLatest query: {state['query']}"
        if history
        else state["query"]
    )

    await rate_limiter.wait_for_slot()
    response = llm.complete(
        system=ROUTER_SYSTEM_PROMPT,
        user=user_message
    )

    # Guard against non-JSON output
    parsed = _parse_json(response, "route_query")
    route = parsed.get("route", "rag")

    logger.info(f"[route_query] Route decision: '{route}'")

    return {**state, "route": route}


# ---------------------------------------------------------------------------
# Node 2: clarify_query
# Checks if the query has enough context to retrieve a useful answer
# ---------------------------------------------------------------------------

async def clarify_query(state: AgentState) -> AgentState:
    """
    Claude evaluates whether the query is specific enough.
    If not, it generates a clarifying question for the user.

    Example:
        "what's the best weapon?" → insufficient
        "what's the best weapon for early hardmode melee?" → sufficient
    """
    logger.info(f"[clarify_query] Evaluating query sufficiency: '{state['query']}'")

    # Build user message — include conversation history if this is a retry
    history = state.get("conversation_history", [])
    user_message = (
        f"Conversation so far:\n{json.dumps(history)}\n\nLatest query: {state['query']}"
        if history
        else state["query"]
    )

    await rate_limiter.wait_for_slot()
    response = llm.complete(
        system=CLARIFIER_SYSTEM_PROMPT,
        user=user_message
    )

    # Guard against non-JSON output
    parsed = _parse_json(response, "clarify_query")
    clarification_needed = not parsed.get("sufficient", True)
    clarification_question = parsed.get("clarification_question")

    logger.info(f"[clarify_query] Sufficient: {not clarification_needed}")
    
    # Build updated conversation history
    updated_history = list(history)  # copy existing history
    
    if clarification_needed:
        logger.info(f"[clarify_query] Asking user: '{clarification_question}'")
        # Store the original query and clarification question in history
        updated_history.append({"role": "user", "content": state["query"]})
        updated_history.append({"role": "assistant", "content": clarification_question})

    return {
        **state,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question,
        "conversation_history": updated_history,
    }


# ---------------------------------------------------------------------------
# Node 3: rewrite_query
# Rephrases the query into a retrieval-friendly form
# ---------------------------------------------------------------------------

async def rewrite_query(state: AgentState) -> AgentState:
    """
    Claude rephrases the raw user query for better semantic search.

    Example:
        "how do i kill skeletron" 
        → "Skeletron boss fight strategy, recommended weapons and armor"
    """
    logger.info(f"[rewrite_query] Rewriting query: '{state['query']}'")

    # Include conversation history for full context (e.g., after clarification)
    history = state.get("conversation_history", [])
    if history:
        # Combine history + latest query so rewriter has full context
        user_message = (
            f"Conversation so far:\n{json.dumps(history)}\n\n"
            f"Latest query: {state['query']}"
        )
    else:
        user_message = state["query"]

    await rate_limiter.wait_for_slot()
    response = llm.complete(
        system=REWRITER_SYSTEM_PROMPT,
        user=user_message
    )

    # Expects plain text back — just the rewritten query string
    rewritten = response.strip()
    logger.info(f"[rewrite_query] Rewritten: '{rewritten}'")

    return {**state, "rewritten_query": rewritten}


# ---------------------------------------------------------------------------
# Node 4: retrieve
# Embeds the rewritten query and fetches top-K chunks from ChromaDB
# ---------------------------------------------------------------------------

async def retrieve(state: AgentState) -> AgentState:
    """
    Uses BGEEmbedder to embed the rewritten query, then queries ChromaDB
    for the most semantically similar chunks.

    Falls back to original query if rewritten_query is empty.
    """
    query_text = state.get("rewritten_query") or state["query"]
    logger.info(f"[retrieve] Retrieving chunks for: '{query_text}'")

    # Embed the query using your existing BGEEmbedder
    query_vector = embedder.embed_query(query_text)

    # Fetch top-K chunks from ChromaDB (configurable)
    chunks = await indexer.query(query_vector, n_results=RETRIEVAL_TOP_K)

    logger.info(f"[retrieve] Retrieved {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        title = chunk.get('page_title', '[No Title]')
        text = chunk.get('text', '[No Text]')
        logger.info(f"[retrieve] Chunk {i+1}: Title: {title}\nText: {text}\n{'-'*40}")

    return {**state, "retrieved_chunks": chunks}


# ---------------------------------------------------------------------------
# Node 5: grade_documents
# Filters out chunks that aren't actually relevant to the query
# ---------------------------------------------------------------------------

async def grade_documents(state: AgentState) -> AgentState:
    """
    Claude scores each retrieved chunk as relevant or not.
    Only chunks that pass are kept in graded_chunks.

    If nothing passes, clarification_needed is set to True
    to trigger a rewrite loop or fallback.
    """
    logger.info(f"[grade_documents] Grading {len(state['retrieved_chunks'])} chunks")

    chunks = state["retrieved_chunks"]
    logger.info(f"[grade_documents] Grading {len(chunks)} chunks in one LLM call")

    # Prepare a single grading request
    user_payload = json.dumps({
        "query": state["query"],
        "chunks": [chunk["text"] for chunk in chunks]
    })

    await rate_limiter.wait_for_slot()
    response = llm.complete(
        system=GRADER_SYSTEM_PROMPT,
        user=user_payload
    )

    # Expect JSON: {"relevant": [true/false, ...]}
    parsed = _parse_json(response, "grade_documents")
    relevant_list = parsed.get("relevant", [])
    if not isinstance(relevant_list, list):
        logger.error(f"[grade_documents] Expected a list for 'relevant', got: {relevant_list}")
        relevant_list = []

    graded = [chunk for chunk, is_relevant in zip(chunks, relevant_list) if is_relevant]
    logger.info(f"[grade_documents] {len(graded)} chunks passed grading")

    needs_retry = len(graded) == 0 and state.get("retry_count", 0) < 3

    return {
        **state,
        "graded_chunks": graded,
        "clarification_needed": needs_retry,
        "retry_count": state.get("retry_count", 0) + 1,
    }


# ---------------------------------------------------------------------------
# Node 6: generate_answer
# Produces the final answer from graded context chunks
# ---------------------------------------------------------------------------

async def generate_answer(state: AgentState) -> AgentState:
    """
    Claude generates a grounded answer using only the graded chunks as context.
    If no chunks are available (direct route or all filtered), it answers
    from its own knowledge with a disclaimer.
    """
    logger.info("[generate_answer] Generating final answer")

    chunks = state.get("graded_chunks") or []
    history = state.get("conversation_history", [])

    # Format context block for the prompt
    if chunks:
        context = "\n\n---\n\n".join(
            f"[{c['page_title']}] {c['text']}" for c in chunks
        )
        history_block = f"Conversation so far:\n{json.dumps(history)}\n\n" if history else ""
        user_message = (
            f"{history_block}Context from the Terraria wiki:\n\n{context}"
            f"\n\nQuestion: {state['query']}"
        )
    else:
        # Direct route or no relevant chunks found
        history_block = f"Conversation so far:\n{json.dumps(history)}\n\n" if history else ""
        user_message = (
            f"{history_block}Question: {state['query']}\n\n"
            "(No wiki context available — answer from general knowledge if possible.)"
        )

    await rate_limiter.wait_for_slot()
    response = llm.complete(
        system=GENERATOR_SYSTEM_PROMPT,
        user=user_message
    )

    answer = response.strip()
    logger.info("[generate_answer] Answer generated successfully")

    updated_history = list(history)
    updated_history.append({"role": "user", "content": state["query"]})
    updated_history.append({"role": "assistant", "content": answer})

    return {
        **state,
        "generation": answer,
        "conversation_history": updated_history,
    }