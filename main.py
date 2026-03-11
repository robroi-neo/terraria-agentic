# main.py

import asyncio
from typing import List
from src.agent.graph import terraria_graph
from src.agent.state import AgentState
from src.agent.gameplay_assumptions import DEFAULT_GAMEPLAY_ASSUMPTIONS


def print_separator():
    print("\n" + "─" * 50 + "\n")


def build_initial_state(query: str, history: List, gameplay_assumptions: dict | None = None) -> AgentState:
    assumptions = dict(gameplay_assumptions or DEFAULT_GAMEPLAY_ASSUMPTIONS)
    return {
        "query": query,
        "rewritten_query": "",
        "retrieved_chunks": [],
        "graded_chunks": [],
        "generation": "",
        "retry_count": 0,
        "route": "rag",
        "clarification_needed": False,
        "clarification_question": None,
        "clarification_retry_count": 0,
        "conversation_history": list(history),
        "gameplay_assumptions": assumptions,
    }

async def chat():
    print("─" * 50)
    print("  Terraria Wiki Assistant")
    print("  Type 'quit' or 'exit' to stop")
    print("─" * 50)

    conversation_history = []
    gameplay_assumptions = dict(DEFAULT_GAMEPLAY_ASSUMPTIONS)

    while True:
        # Get user input
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nGoodbye!")
            break

        # Exit conditions
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("\nGoodbye!")
            break

        # Build state and run graph
        state = build_initial_state(user_input, conversation_history, gameplay_assumptions)

        try:
            print("\nAssistant: ", end="", flush=True)
            result = await terraria_graph.ainvoke(state)
        except Exception as e:
            print(f"\n[Error] Something went wrong: {e}")
            continue

        print_separator()

        # Keep session memory from graph output
        conversation_history = result.get("conversation_history", conversation_history)
        gameplay_assumptions = result.get("gameplay_assumptions", gameplay_assumptions)

        # Handle clarification
        if result.get("clarification_needed"):
            question = result["clarification_question"]
            print(f"Assistant: {question}")
            continue

        # Handle normal answer
        answer = result.get("generation", "I was unable to find an answer.")
        print(f"Assistant: {answer}")


if __name__ == "__main__":
    asyncio.run(chat())