import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

# LLM provider imports `ollama` at module import time; provide a lightweight stub for tests.
sys.modules.setdefault("ollama", SimpleNamespace(chat=lambda *args, **kwargs: {"message": {"content": "{}"}}))

from main import build_initial_state
from src.agent import nodes


class _NoWaitRateLimiter:
    async def wait_for_slot(self):
        return None


def _run(coro):
    return asyncio.run(coro)


def test_clarify_query_handles_first_turn_without_crash():
    state = build_initial_state("best weapon?", [])

    with patch.object(nodes, "rate_limiter", _NoWaitRateLimiter()):
        with patch.object(nodes.llm, "complete", return_value=json.dumps({
            "sufficient": False,
            "clarification_question": "Which class and progression stage are you in?"
        })):
            result = _run(nodes.clarify_query(state))

    assert result["clarification_needed"] is True
    assert result["clarification_retry_count"] == 1
    assert result["clarification_question"] == "Which class and progression stage are you in?"
    assert result["conversation_history"][-2:] == [
        {"role": "user", "content": "best weapon?"},
        {"role": "assistant", "content": "Which class and progression stage are you in?"},
    ]


def test_clarify_query_blocks_near_duplicate_follow_up_question():
    state = build_initial_state(
        "Melee",
        [
            {"role": "user", "content": "best weapon?"},
            {"role": "assistant", "content": "What class are you playing?"},
        ],
    )

    with patch.object(nodes, "rate_limiter", _NoWaitRateLimiter()):
        with patch.object(nodes.llm, "complete", return_value=json.dumps({
            "sufficient": False,
            "clarification_question": "Which class are you playing?"
        })):
            result = _run(nodes.clarify_query(state))

    assert result["clarification_needed"] is False
    assert result["clarification_question"] is None
    assert result["clarification_retry_count"] == 0


def test_clarify_query_max_retry_proceeds_without_llm_call():
    state = build_initial_state(
        "Melee",
        [
            {"role": "user", "content": "best weapon?"},
            {"role": "assistant", "content": "What class are you playing?"},
        ],
    )
    state["clarification_retry_count"] = 1

    with patch.object(nodes, "rate_limiter", _NoWaitRateLimiter()):
        complete_mock = Mock(return_value=json.dumps({"sufficient": False, "clarification_question": "unused"}))
        with patch.object(nodes.llm, "complete", complete_mock):
            result = _run(nodes.clarify_query(state))

    complete_mock.assert_not_called()
    assert result["clarification_needed"] is False
    assert result["clarification_question"] is None
    assert "Additional user context: Melee" in result["query"]
