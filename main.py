# main.py

import asyncio
from typing import List
from src.agent.graph import terraria_graph
from src.agent.state import AgentState


def print_separator():
    print("\n" + "─" * 50 + "\n")


def build_initial_state(query: str, history: List) -> AgentState:
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
        "conversation_history": history,
    }


async def chat():
    print("─" * 50)
    print("  Terraria Wiki Assistant")
    print("  Type 'quit' or 'exit' to stop")
    print("─" * 50)

    conversation_history = []

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
        state = build_initial_state(user_input, conversation_history)

        try:
            print("\nAssistant: ", end="", flush=True)
            result = await terraria_graph.ainvoke(state)
        except Exception as e:
            print(f"\n[Error] Something went wrong: {e}")
            continue

        print_separator()

        # Handle clarification
        if result.get("clarification_needed"):
            question = result["clarification_question"]
            print(f"Assistant: {question}")

            # Append to history so next turn has context
            conversation_history.append({"role": "user",      "content": user_input})
            conversation_history.append({"role": "assistant", "content": question})
            continue

        # Handle normal answer
        answer = result.get("generation", "I was unable to find an answer.")
        print(f"Assistant: {answer}")

        # Append completed exchange to history
        conversation_history.append({"role": "user",      "content": user_input})
        conversation_history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    asyncio.run(chat())