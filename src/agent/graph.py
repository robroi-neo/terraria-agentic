# src/agent/graph.py

from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import (
    route_query,
    clarify_query,
    rewrite_query,
    retrieve,
    generate_answer,
)


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def decide_after_routing(state: AgentState) -> str:
    """
    After route_query runs:
    - "rag"    → go to clarify_query
    - "direct" → skip everything, go straight to generate_answer
    """
    if state["route"] == "rag":
        return "clarify_query"
    return "generate_answer"


def decide_after_clarification(state: AgentState) -> str:
    """
    After clarify_query runs:
    - query is vague     → END (API returns clarifying question to user)
    - query is specific  → proceed to rewrite_query
    """
    if state["clarification_needed"]:
        return "ask_user"
    return "rewrite_query"


def decide_after_grading(state: AgentState) -> str:
    """
    After grade_documents runs:
    - no relevant chunks + retries remain → loop back to rewrite_query
    - relevant chunks found OR max retries hit → proceed to generate_answer
    """
    no_good_chunks = len(state.get("graded_chunks", [])) == 0
    retries_remaining = state.get("retry_count", 0) < 3

    if no_good_chunks and retries_remaining:
        return "rewrite_query"
    return "generate_answer"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # -----------------------------------------------------------------------
    # 1. Register all nodes
    # -----------------------------------------------------------------------
    graph.add_node("route_query",     route_query)
    graph.add_node("clarify_query",   clarify_query)
    graph.add_node("rewrite_query",   rewrite_query)
    graph.add_node("retrieve",        retrieve)
    graph.add_node("generate_answer", generate_answer)

    # -----------------------------------------------------------------------
    # 2. Set the entry point
    # Every query starts here, no exceptions
    # -----------------------------------------------------------------------
    graph.set_entry_point("route_query")

    # -----------------------------------------------------------------------
    # 3. Wire the edges
    # -----------------------------------------------------------------------

    # route_query → branches based on "rag" or "direct"
    graph.add_conditional_edges(
        "route_query",
        decide_after_routing,
        {
            "clarify_query":   "clarify_query",
            "generate_answer": "generate_answer",
        }
    )

    # clarify_query → branches based on whether query is sufficient
    graph.add_conditional_edges(
        "clarify_query",
        decide_after_clarification,
        {
            "ask_user":      END,            # pauses pipeline, returns question to user
            "rewrite_query": "rewrite_query",
        }
    )

    # rewrite_query → always goes to retrieve
    graph.add_edge("rewrite_query", "retrieve")

    # retrieve → always goes to generate_answer
    graph.add_edge("retrieve", "generate_answer")

    # generate_answer → always ends
    graph.add_edge("generate_answer", END)

    return graph.compile()

terraria_graph = build_graph()