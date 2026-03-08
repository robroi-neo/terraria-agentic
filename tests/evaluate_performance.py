"""
tests/evaluate_performance.py
------------------------------
Performance evaluation for the Terraria Wiki Assistant.

Measures per-query response time, estimates token usage, and (when running
in production mode against the Groq API) calculates approximate API cost.

Run with:
    python -m tests.evaluate_performance

Pricing reference (Groq – llama-3.1-8b-instant, as of March 2026):
    Input  : $0.05  per 1 000 000 tokens
    Output : $0.08  per 1 000 000 tokens
"""

import asyncio
import sys
import os
import time
import statistics

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import terraria_graph
from src.agent.state import AgentState
from config import IS_DEVELOPMENT, OLLAMA_MODEL
from main import build_initial_state

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")

# ---------------------------------------------------------------------------
# Groq pricing for llama-3.1-8b-instant (USD per token)
# ---------------------------------------------------------------------------
GROQ_INPUT_COST_PER_TOKEN  = 0.05  / 1_000_000   # $0.05  / 1M tokens
GROQ_OUTPUT_COST_PER_TOKEN = 0.08  / 1_000_000   # $0.08  / 1M tokens

# ---------------------------------------------------------------------------
# Queries (same suite used in functional evaluation)
# ---------------------------------------------------------------------------
QUERIES = [
    "Who is the first boss in Terraria?",   
]

# ---------------------------------------------------------------------------
# Token estimation
# Approximation: 1 token ≈ 4 characters (consistent with OpenAI guidance).
# This avoids a hard dependency on tiktoken or the model's tokeniser.
# ---------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost. Returns 0 in development (local Ollama)."""
    if IS_DEVELOPMENT:
        return 0.0
    return (input_tokens * GROQ_INPUT_COST_PER_TOKEN +
            output_tokens * GROQ_OUTPUT_COST_PER_TOKEN)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
async def run_query(query: str) -> dict:
    """Invoke the agent graph and return timing + generation."""
    state: AgentState = build_initial_state(query, [])

    start = time.perf_counter()
    result = await terraria_graph.ainvoke(state)
    elapsed = time.perf_counter() - start

    generation = result.get("generation") or ""
    return {
        "query": query,
        "generation": generation,
        "response_time_s": elapsed,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    model_label = OLLAMA_MODEL if IS_DEVELOPMENT else "llama-3.1-8b-instant (Groq)"
    env_label   = "Development (Ollama – local)" if IS_DEVELOPMENT else "Production (Groq API)"

    print("=" * 65)
    print("  Terraria Wiki Assistant — Performance Evaluation")
    print(f"  Environment : {env_label}")
    print(f"  Model       : {model_label}")
    print(f"  Queries     : {len(QUERIES)}")
    print("=" * 65)

    results = []

    for i, query in enumerate(QUERIES, 1):
        print(f"\n[{i}/{len(QUERIES)}] {query}")
        try:
            r = asyncio.run(run_query(query))
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append({
                "query": query,
                "response_time_s": None,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "cost_usd": None,
                "error": str(exc),
            })
            continue

        # Token estimation
        input_tokens  = estimate_tokens(query)
        output_tokens = estimate_tokens(r["generation"])
        total_tokens  = input_tokens + output_tokens
        cost          = estimate_cost(input_tokens, output_tokens)

        print(f"  Response time : {r['response_time_s']:.3f}s")
        print(f"  Input tokens  : ~{input_tokens}")
        print(f"  Output tokens : ~{output_tokens}")
        print(f"  Total tokens  : ~{total_tokens}")
        if IS_DEVELOPMENT:
            print(f"  Cost          : $0.00 (local model)")
        else:
            print(f"  Cost          : ${cost:.6f} USD")
        print(f"  Response      : {r['generation'][:120]}{'...' if len(r['generation']) > 120 else ''}")

        results.append({
            "query": query,
            "response_time_s": r["response_time_s"],
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost,
        })

    # -----------------------------------------------------------------------
    # Aggregate statistics
    # -----------------------------------------------------------------------
    valid = [r for r in results if r.get("response_time_s") is not None]

    if not valid:
        print("\nNo valid results to summarise.")
        return

    times         = [r["response_time_s"] for r in valid]
    total_in_tok  = sum(r["input_tokens"]  for r in valid)
    total_out_tok = sum(r["output_tokens"] for r in valid)
    total_tok     = sum(r["total_tokens"]  for r in valid)
    total_cost    = sum(r["cost_usd"]      for r in valid)

    print("\n" + "─" * 65)
    print("  PERFORMANCE SUMMARY")
    print("─" * 65)
    print(f"  Queries completed     : {len(valid)} / {len(QUERIES)}")
    print()
    print("  Response Time (seconds)")
    print(f"    Min     : {min(times):.3f}s")
    print(f"    Max     : {max(times):.3f}s")
    print(f"    Mean    : {statistics.mean(times):.3f}s")
    if len(times) > 1:
        print(f"    Std Dev : {statistics.stdev(times):.3f}s")
    print(f"    Total   : {sum(times):.3f}s")
    print()
    print("  Token Usage (estimated)")
    print(f"    Total input tokens   : ~{total_in_tok}")
    print(f"    Total output tokens  : ~{total_out_tok}")
    print(f"    Total tokens         : ~{total_tok}")
    print(f"    Avg tokens / query   : ~{total_tok // len(valid)}")
    print()
    if IS_DEVELOPMENT:
        print("  Cost Analysis")
        print("    Running locally via Ollama — no API cost incurred.")
    else:
        print("  Cost Analysis  (Groq – llama-3.1-8b-instant)")
        print(f"    Input  rate  : $0.05  / 1M tokens")
        print(f"    Output rate  : $0.08  / 1M tokens")
        print(f"    Total cost   : ${total_cost:.6f} USD")
        print(f"    Avg cost/query: ${total_cost / len(valid):.6f} USD")
    print("─" * 65 + "\n")


if __name__ == "__main__":
    main()
