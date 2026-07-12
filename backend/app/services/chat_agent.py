"""Agentic chat: let the LLM plan tool calls to answer questions over real data.

A bounded ReAct-style loop on top of the shared ``llm_client`` (Gemini rotation →
OpenRouter fallback). The model is shown a set of tools (``chat_tools.TOOLS``) and,
step by step, emits a JSON decision to either call a tool or give a final answer.
Tools return real computed numbers, so the model answers over actual data and
cannot fabricate figures.

The loop is deliberately shallow (``max_steps`` defaults to 2): almost every
finance question is one tool call, and free-tier models get less reliable with
each extra hop. If the LLM is unavailable or the loop cannot produce an answer,
the caller falls back to the deterministic ``chat_service.answer_question``.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from supabase import Client

from app.services import chat_tools, llm_client

logger = logging.getLogger("tally.chat.agent")

DEFAULT_MAX_STEPS = 2
_TOOL_MAX_TOKENS = 700
_ANSWER_MAX_TOKENS = 300


class AgentUnavailable(Exception):
    """Raised when the agent cannot produce an answer (caller should fall back)."""


def _collect_numbers(obj: Any, acc: set[int]) -> None:
    """Recursively gather every numeric value (as whole-rupee absolute ints) that
    the tools actually returned, so we can check the model didn't invent figures."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        acc.add(round(abs(float(obj))))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numbers(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect_numbers(v, acc)


def _verify_figures(answer: str, transcript: list[dict[str, Any]]) -> bool:
    """Reject an answer that states an `Rs` figure not present in the tool results.

    The tools compute the numbers; the model only renders/selects/compares them —
    which is exactly where a weak model can misstate a figure. Every `Rs` amount in
    the answer must match (±1 rupee, sign-insensitive) a value the tools returned.
    Comparison is numeric (tools emit raw floats like 1800.0; the model writes
    'Rs 1,800.00'). No figures in the answer -> nothing to verify -> allowed.
    """
    figures = re.findall(r"Rs\s*(-?[\d,]+(?:\.\d+)?)", answer)
    if not figures:
        return True
    tool_values: set[int] = set()
    _collect_numbers(transcript, tool_values)
    for raw in figures:
        try:
            val = round(abs(float(raw.replace(",", ""))))
        except ValueError:
            continue
        if not any(abs(val - tv) <= 1 for tv in tool_values):
            return False
    return True


def _normalize_currency(text: str) -> str:
    """Force INR presentation. Weak free-tier models often ignore the 'use Rs'
    instruction and emit '$' or the rupee sign, which is misleading in this
    rupee-only app — so we rewrite currency symbols deterministically.
    """
    text = re.sub(r"[$₹]\s*", "Rs ", text)   # $ / ₹  ->  Rs
    text = re.sub(r"\bRs\s+Rs\b", "Rs", text)     # collapse any doubled prefix
    return text


def _selection_prompt(question: str, transcript: list[dict[str, Any]]) -> str:
    today = date.today().isoformat()
    history = ""
    if transcript:
        history = "\n\nTool results so far (use these; do not re-call the same tool):\n" + json.dumps(
            transcript, default=str
        )[:1500]
    return (
        "You are a personal-finance assistant that answers by calling tools over the "
        f"user's own transaction data. Today is {today}.\n\n"
        "Available tools:\n"
        f"{chat_tools.TOOL_SPECS}\n\n"
        "CRITICAL: Output ONLY one JSON object and nothing else. No reasoning, no prose. "
        "Your reply MUST start with '{'. Use exactly one of these shapes:\n"
        '{"action":"call_tool","tool":"<name>","args":{...}}\n'
        '{"action":"final","answer":"<one to three sentences>"}\n\n'
        "Pick the single best tool for the question. Give a final answer once you have "
        "enough data. Examples:\n"
        'User: How much did I spend on food last month?\n'
        '{"action":"call_tool","tool":"get_spending_by_category","args":{"start":"2026-06-01","end":"2026-06-30","category":"food"}}\n'
        'User: Did I spend more this month than last?\n'
        '{"action":"call_tool","tool":"compare_periods","args":{"period_a_start":"2026-07-01","period_a_end":"2026-07-12","period_b_start":"2026-06-01","period_b_end":"2026-06-30"}}\n'
        f"{history}\n\n"
        f"User: {question}\n"
    )


def _answer_prompt(question: str, transcript: list[dict[str, Any]]) -> str:
    return (
        "You are a friendly personal-finance assistant. Using ONLY the tool results "
        "below, answer the user's question in one to three sentences. All amounts are "
        "in Indian Rupees: write every amount as 'Rs 1,200' — never use '$', never use "
        "the rupee sign, never any other currency. Do NOT invent or recompute any "
        "number; use the figures exactly as given. If the data is empty, say so plainly.\n\n"
        f"Question: {question}\n"
        f"Tool results: {json.dumps(transcript, default=str)[:2000]}\n\n"
        "Answer:"
    )


def _run_tool(name: str, args: dict[str, Any], question: str, user_id: str, db: Client) -> dict[str, Any]:
    tool = chat_tools.TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool '{name}'"}
    if not isinstance(args, dict):
        args = {}
    # Strip any attempt by the model to pass identity/privileged or server-owned
    # args (user_id/db are injected; question is passed positionally below).
    for reserved in ("user_id", "db", "question"):
        args.pop(reserved, None)
    try:
        return tool(db, user_id, question=question, **args)
    except TypeError as e:  # bad/unexpected args from the model
        logger.warning("tool %s rejected args %s: %s", name, args, e)
        return {"error": f"invalid arguments for {name}"}
    except Exception as e:
        logger.warning("tool %s failed: %s", name, e)
        return {"error": str(e)}


async def run_agent(
    question: str, user_id: str, db: Client, max_steps: int = DEFAULT_MAX_STEPS
) -> str:
    """Answer ``question`` by letting the model drive tool calls over real data.

    Raises ``AgentUnavailable`` when no LLM is configured or the loop produced no
    usable data, so the caller can fall back to the deterministic path.
    """
    if not llm_client.is_available():
        raise AgentUnavailable("no LLM provider configured")

    transcript: list[dict[str, Any]] = []
    for step in range(max_steps):
        try:
            decision = await llm_client.acomplete_json(
                _selection_prompt(question, transcript), max_tokens=_TOOL_MAX_TOKENS
            )
        except Exception as e:
            logger.warning("agent selection step %d failed: %s", step, e)
            break

        if not isinstance(decision, dict):
            break

        action = decision.get("action")
        if action == "final":
            answer = str(decision.get("answer", "")).strip()
            if answer and _verify_figures(answer, transcript):
                return _normalize_currency(answer)
            if answer:
                logger.warning("agent final answer stated unverified figures; falling back")
                raise AgentUnavailable("final answer figures not backed by tool results")
            break

        if action == "call_tool":
            name = str(decision.get("tool", ""))
            result = _run_tool(name, decision.get("args") or {}, question, user_id, db)
            transcript.append({"tool": name, "args": decision.get("args") or {}, "result": result})
            continue

        break  # unrecognised action

    if not transcript:
        raise AgentUnavailable("agent produced no tool results")

    # Turn the collected tool data into a natural-language answer.
    try:
        answer = (await llm_client.acomplete(_answer_prompt(question, transcript), max_tokens=_ANSWER_MAX_TOKENS)).strip()
    except Exception as e:
        logger.warning("agent finalize failed: %s", e)
        raise AgentUnavailable("could not finalize answer") from e

    if not answer:
        raise AgentUnavailable("empty final answer")
    if not _verify_figures(answer, transcript):
        logger.warning("agent finalize stated unverified figures; falling back")
        raise AgentUnavailable("finalized answer figures not backed by tool results")
    return _normalize_currency(answer)
