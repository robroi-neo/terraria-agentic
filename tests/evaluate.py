"""
tests/evaluate.py
-----------------
LLM-as-Judge functional evaluation for the Terraria Wiki Assistant.

Run with:
    python -m tests.evaluate

Each test case has a natural-language query and a list of keyword hints that
represent the "expected" answer.  The judge LLM scores the model response
against the expected answer from 0.0 (completely wrong) to 1.0 (correct).
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import terraria_graph
from src.agent.llm_provider import LLMProvider
from main import build_initial_state

from loguru import logger
logger.remove()
logger.add(sys.stderr, level="WARNING")
# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

tests = [
    {
        "query": "Who is the first boss in Terraria?",
        "keywords": ["Eye of Cthulu"],
    },
    {
        "query": "What does the Eye of Cthulhu drop?",
        "keywords": ["Demonite", "Crimtane", "Lens", "boss"],
    },
    {
        "query": "How do I summon Skeletron?",
        "keywords": ["Old Man", "dungeon", "night"],
    },
    {
        "query": "What is the best weapon to defeat the Eater of Worlds?",
        "keywords": ["Minishark", "bow", "Corruption", "segment"],
    },
    {
        "query": "How many phases does Moon Lord have?",
        "keywords": ["2", "two", "phases", "True Eyes"],
    },
    {
        "query": "What biome does the Queen Bee spawn in?",
        "keywords": ["Jungle", "beehive", "Larva"],
    },
    {
        "query": "How do I unlock Hardmode?",
        "keywords": ["Wall of Flesh", "defeated", "Underworld"],
    },
    {
        "query": "What summoning item is used for the Golem?",
        "keywords": ["Lihzahrd Power Cell", "altar", "Jungle Temple"],
    },
]

# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

JUDGE_SYSTEM = (
    "You are an impartial grader. "
    "Given a question, an expected answer (key concepts), and a model response, "
    "output ONLY a single decimal number between 0 and 1 representing how correct "
    "the model response is. 1.0 = fully correct, 0.0 = completely wrong. "
    "No explanation — output the number only."
)


def build_expected_answer(keywords: list[str]) -> str:
    return "The answer should mention: " + ", ".join(keywords)


def judge_response(llm: LLMProvider, query: str, expected: str, response: str) -> float:
    user_prompt = (
        f"Question: {query}\n"
        f"Expected Answer: {expected}\n"
        f"Model Response: {response}\n\n"
        f"Score from 0–1 if the answer is correct."
    )
    raw = llm.complete(system=JUDGE_SYSTEM, user=user_prompt)
    try:
        return float(raw.strip())
    except ValueError:
        # Attempt to extract a float if extra text slipped through
        import re
        match = re.search(r"[0-1](?:\.\d+)?", raw)
        return float(match.group()) if match else 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

async def run_test(test: dict) -> dict:
    state = build_initial_state(test["query"], [])
    result = await terraria_graph.ainvoke(state)
    generation = result.get("generation") or "No answer generated."
    return {
        "query": test["query"],
        "expected_keywords": test["keywords"],
        "generation": generation,
    }


def print_divider():
    print("\n" + "─" * 60)


def human_judge(query: str, expected: str, model_response: str) -> float:
    """Prompt the user to score the response manually (0–1)."""
    print(f"  Expected keywords : {expected}")
    print(f"  Model response    : {model_response[:300]}{'...' if len(model_response) > 300 else ''}")
    while True:
        raw = input("  Your score (0.0 – 1.0): ").strip()
        try:
            score = float(raw)
            if 0.0 <= score <= 1.0:
                return score
            print("  Please enter a value between 0 and 1.")
        except ValueError:
            print("  Invalid input — enter a decimal like 0.5")


def main(use_judge: bool = True):
    llm = LLMProvider(temperature=0.2) if use_judge else None
    total_score = 0.0
    n = len(tests)
    mode_label = "LLM-as-Judge" if use_judge else "Human-in-the-Loop"

    print("=" * 60)
    print("  Terraria Wiki Assistant — Functional Evaluation")
    print(f"  Running {n} test cases [{mode_label}]")
    print("=" * 60)

    for i, test in enumerate(tests, 1):
        print(f"\n[{i}/{n}] Query: {test['query']}")

        # 1. Get the assistant's answer
        try:
            result = asyncio.run(run_test(test))
            model_response = result["generation"]
        except Exception as e:
            model_response = f"[ERROR] {e}"

        # 2. Build expected description from keywords
        expected = build_expected_answer(test["keywords"])

        # 3. Score — LLM judge OR human
        if use_judge:
            try:
                score = judge_response(llm, test["query"], expected, model_response)
            except Exception as e:
                print(f"  [Judge error] {e}")
                score = 0.0
            print(f"  Expected keywords : {', '.join(test['keywords'])}")
            print(f"  Model response    : {model_response[:200]}{'...' if len(model_response) > 200 else ''}")
            print(f"  Score             : {score:.2f}")
        else:
            score = human_judge(test["query"], ', '.join(test["keywords"]), model_response)
            print(f"  Score             : {score:.2f}")

        total_score += score

    print_divider()
    avg = total_score / n
    print(f"\n  FINAL SCORE: {total_score:.2f} / {n:.2f}  (avg {avg:.2f})")
    print(f"  {'PASS' if avg >= 0.7 else 'FAIL'} (threshold: 0.70)")
    print("─" * 60 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--human",
        action="store_true",
        help="Use human-in-the-loop scoring instead of LLM judge",
    )
    args = parser.parse_args()
    main(use_judge=not args.human)
