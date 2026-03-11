'''
Async Functions. Accepts Current State and Returns an Updated State.    
'''

# List of Nodes:
# route_query() # evaluate's if query needs rag or it can be answered directly
# clarify_query() -> evaluates whether the query is specific enough to retrieve //uses llm
# rewrite_query() -> rewrite query into retrieval optimized form
# retrieve() -> calls llm. Embdedds writing, fetches top k //uses llm
# generate_answer() -> final node

# src/agent/nodes.py

# The problem is
# when querying in chroma db, it does not involve the previous question during follow ups.
# add a new node to summarize prev question + follow up.


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
    GENERATOR_SYSTEM_PROMPT,
)
from src.agent.gameplay_assumptions import (
    DEFAULT_GAMEPLAY_ASSUMPTIONS,
    assumptions_block,
    extract_from_text,
    merge_with_defaults,
)
from src.ingestion.embedder import BGEEmbedder
from src.ingestion.indexer import ChromaIndexer
from config import (
    RETRIEVAL_TOP_K,
    RETRIEVAL_ENABLE_WALKTHROUGH_SPLIT,
    RETRIEVAL_WALKTHROUGH_ROOT_COLLECTION,
    RETRIEVAL_WALKTHROUGH_LINKS_COLLECTION,
    RETRIEVAL_WALKTHROUGH_ROOT_TOP_K,
    RETRIEVAL_WALKTHROUGH_LINKS_TOP_K,
    RETRIEVAL_WALKTHROUGH_ROOT_DISTANCE_BONUS,
)

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

# LLM pipeline rate limiter — uses class default (100 req/min).
# REQUEST_PER_MINUTE in config.py is for the scraper only.
rate_limiter = RequestRateLimiter()

llm = LLMProvider()
embedder = BGEEmbedder()
indexer = ChromaIndexer()
walkthrough_root_indexer = None
walkthrough_links_indexer = None

if RETRIEVAL_ENABLE_WALKTHROUGH_SPLIT:
    walkthrough_root_indexer = ChromaIndexer(collection_name=RETRIEVAL_WALKTHROUGH_ROOT_COLLECTION)
    walkthrough_links_indexer = ChromaIndexer(collection_name=RETRIEVAL_WALKTHROUGH_LINKS_COLLECTION)


def _chunk_dedupe_key(chunk: dict[str, Any]) -> tuple[Any, ...]:
    return (
        chunk.get("source_partition", "core"),
        chunk.get("page_title"),
        chunk.get("section_index"),
        chunk.get("chunk_index"),
    )


def _merge_ranked_chunks(root_chunks: list[dict[str, Any]], link_chunks: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for chunk in root_chunks:
        adjusted = dict(chunk)
        adjusted["source_partition"] = adjusted.get("source_partition", "walkthrough_root")
        adjusted["adjusted_distance"] = float(adjusted.get("distance", 0.0)) - RETRIEVAL_WALKTHROUGH_ROOT_DISTANCE_BONUS
        ranked.append(adjusted)

    for chunk in link_chunks:
        adjusted = dict(chunk)
        adjusted["source_partition"] = adjusted.get("source_partition", "walkthrough_links")
        adjusted["adjusted_distance"] = float(adjusted.get("distance", 0.0))
        ranked.append(adjusted)

    ranked.sort(key=lambda c: c.get("adjusted_distance", c.get("distance", 0.0)))

    merged: list[dict[str, Any]] = []
    seen = set()
    for chunk in ranked:
        key = _chunk_dedupe_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        chunk.pop("adjusted_distance", None)
        merged.append(chunk)
        if len(merged) >= limit:
            break
    return merged


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


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _token_set(value: str) -> set[str]:
    return set(_normalize_text(value).split())


def _is_repeated_clarification_question(previous: str, current: str) -> bool:
    prev_norm = _normalize_text(previous)
    curr_norm = _normalize_text(current)
    if prev_norm == curr_norm:
        return True

    prev_tokens = _token_set(previous)
    curr_tokens = _token_set(current)
    if not prev_tokens or not curr_tokens:
        return False

    overlap = len(prev_tokens & curr_tokens) / max(len(prev_tokens), len(curr_tokens))
    return overlap >= 0.8


def _current_assumptions(state: AgentState) -> dict[str, str]:
    return merge_with_defaults(state.get("gameplay_assumptions", DEFAULT_GAMEPLAY_ASSUMPTIONS))


def _get_pending_clarification(history: list[dict[str, str]]) -> tuple[str | None, str | None]:
    """
    Infer whether the last assistant turn was a clarification question.
    If so, return (original_user_query, clarification_question).
    """
    if len(history) < 2:
        return None, None

    last_msg = history[-1]
    prev_msg = history[-2]
    if (
        last_msg.get("role") == "assistant"
        and prev_msg.get("role") == "user"
        and "?" in last_msg.get("content", "")
    ):
        return prev_msg.get("content"), last_msg.get("content")
    return None, None

async def route_query(state: AgentState) -> AgentState:
    """
    Claude reads the query and decides:
    - 'rag'    → needs wiki retrieval (items, bosses, crafting, biomes)
    - 'direct' → general/conversational, no retrieval needed
    """
    logger.info(f"[route_query] Routing query: '{state['query']}'")

    history = state.get("conversation_history", [])
    assumptions = extract_from_text(state["query"], _current_assumptions(state))
    assumptions_context = assumptions_block(assumptions)
    user_message = (
        f"{assumptions_context}\n\nConversation so far:\n{json.dumps(history)}\n\nLatest query: {state['query']}"
        if history
        else f"{assumptions_context}\n\nLatest query: {state['query']}"
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

    return {**state, "route": route, "gameplay_assumptions": assumptions}


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

    history = state.get("conversation_history", [])
    current_query = state["query"].strip()
    assumptions = extract_from_text(current_query, _current_assumptions(state))
    assumptions_context = assumptions_block(assumptions)
    base_query, prior_clarification_question = _get_pending_clarification(history)
    clarification_retry_count = state.get("clarification_retry_count", 0)
    max_clarification_retries = 1

    # If this turn looks like a clarification answer, carry forward original intent.
    effective_query = (
        f"{base_query}. Additional user context: {current_query}"
        if base_query and current_query
        else state["query"]
    )

    if clarification_retry_count >= max_clarification_retries:
        logger.info("[clarify_query] Max clarification retries reached - proceeding.")
        return {
            **state,
            "query": effective_query,
            "clarification_needed": False,
            "clarification_question": None,
            "clarification_retry_count": clarification_retry_count,
            "conversation_history": list(history),
            "gameplay_assumptions": assumptions,
        }

    if base_query and prior_clarification_question:
        user_message = (
            f"{assumptions_context}\n\n"
            "Original user question:\n"
            f"{base_query}\n\n"
            "Previous clarification question from assistant:\n"
            f"{prior_clarification_question}\n\n"
            "User's clarification answer:\n"
            f"{current_query}\n\n"
            "Evaluate whether this now has enough detail to proceed. "
            "If more detail is needed, ask ONE different follow-up question - but only if absolutely necessary. "
            "When in doubt, mark it as sufficient and proceed."
        )
    else:
        user_message = (
            f"{assumptions_context}\n\n"
            "User question:\n"
            f"{current_query}\n\n"
            "Evaluate whether this has enough detail to proceed. "
            "If more detail is needed, ask exactly one concise clarification question. "
            "When in doubt, mark it as sufficient and proceed."
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

    if clarification_needed and not clarification_question:
        logger.warning("[clarify_query] Missing clarification question in insufficient response; proceeding.")
        clarification_needed = False

    # Guard against self-loop where the model repeats the exact same follow-up.
    if (
        clarification_needed
        and prior_clarification_question
        and clarification_question
        and _is_repeated_clarification_question(prior_clarification_question, clarification_question)
    ):
        logger.warning("[clarify_query] Prevented repeated clarification question loop")
        clarification_needed = False
        clarification_question = None

    logger.info(f"[clarify_query] Sufficient: {not clarification_needed}")
    
    # Build updated conversation history
    updated_history = list(history)  # copy existing history
    
    if clarification_needed:
        logger.info(f"[clarify_query] Asking user: '{clarification_question}'")
        # Store the original query and clarification question in history
        updated_history.append({"role": "user", "content": current_query})
        updated_history.append({"role": "assistant", "content": clarification_question})

    return {
        **state,
        "query": effective_query,
        "clarification_needed": clarification_needed,
        "clarification_question": clarification_question,
        "clarification_retry_count": clarification_retry_count + 1 if clarification_needed else 0,
        "conversation_history": updated_history,
        "gameplay_assumptions": assumptions,
    }


# ---------------------------------------------------------------------------
# Node 3: rewrite_query
# Rephrases the query into a retrieval-friendly form
# ---------------------------------------------------------------------------

async def rewrite_query(state: AgentState) -> AgentState:
    """
    Pass-through node: keep the graph shape stable without LLM rewriting.
    """
    rewritten = state["query"].strip()
    logger.info(f"[rewrite_query] Rewriter disabled. Using query unchanged: '{rewritten}'")

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

    # Fetch top-K chunks from ChromaDB.
    if RETRIEVAL_ENABLE_WALKTHROUGH_SPLIT and walkthrough_root_indexer and walkthrough_links_indexer:
        root_chunks = await walkthrough_root_indexer.query(
            query_vector,
            n_results=RETRIEVAL_WALKTHROUGH_ROOT_TOP_K,
        )
        link_chunks = await walkthrough_links_indexer.query(
            query_vector,
            n_results=RETRIEVAL_WALKTHROUGH_LINKS_TOP_K,
        )
        chunks = _merge_ranked_chunks(root_chunks, link_chunks, RETRIEVAL_TOP_K)
        logger.info(
            "[retrieve] Split retrieval enabled. "
            f"root_hits={len(root_chunks)} link_hits={len(link_chunks)} merged={len(chunks)}"
        )

        # Fallback for deployments where ingestion populated only the standard
        # collection but split retrieval is enabled at query time.
        if not chunks:
            logger.warning(
                "[retrieve] Split retrieval returned 0 chunks. "
                "Falling back to standard collection query. "
                "Check retrieval/ingestion collection config if this persists."
            )
            chunks = await indexer.query(query_vector, n_results=RETRIEVAL_TOP_K)
    else:
        chunks = await indexer.query(query_vector, n_results=RETRIEVAL_TOP_K)

    logger.info(f"[retrieve] Retrieved {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        title = chunk.get('page_title', '[No Title]')
        text = chunk.get('text', '[No Text]')
        logger.info(f"[retrieve] Chunk {i+1}: Title: {title}\nText: {text}\n{'-'*40}")

    return {**state, "retrieved_chunks": chunks}


# ---------------------------------------------------------------------------
# Node 5: generate_answer
# Produces the final answer from retrieved context chunks
# ---------------------------------------------------------------------------

async def generate_answer(state: AgentState) -> AgentState:
    """
    Claude generates a grounded answer using only the retrieved chunks as context.
    If no chunks are available (direct route or all filtered), it answers
    from its own knowledge with a disclaimer.
    """
    logger.info("[generate_answer] Generating final answer")

    chunks = state.get("retrieved_chunks") or []
    history = state.get("conversation_history", [])
    assumptions_context = assumptions_block(_current_assumptions(state))

    # Format context block for the prompt
    if chunks:
        context = "\n\n---\n\n".join(
            f"[{c['page_title']}] {c['text']}" for c in chunks
        )
        history_block = f"Conversation so far:\n{json.dumps(history)}\n\n" if history else ""
        user_message = (
            f"{assumptions_context}\n\n{history_block}Context from the Terraria wiki:\n\n{context}"
            f"\n\nQuestion: {state['query']}"
        )
    else:
        # Direct route or no relevant chunks found
        history_block = f"Conversation so far:\n{json.dumps(history)}\n\n" if history else ""
        user_message = (
            f"{assumptions_context}\n\n{history_block}Question: {state['query']}\n\n"
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