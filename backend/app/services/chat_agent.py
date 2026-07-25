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

# 3 hops so a "create category, then categorize" request (create_category ->
# categorize_merchant -> final) fits; single actions/questions still finish in 2.
DEFAULT_MAX_STEPS = 3
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


def _action_confirmation(transcript: list[dict[str, Any]]) -> str | None:
    """Deterministic confirmation for a write-action, composed from the tool result.

    Actions carry counts, not `Rs` figures, so `_verify_figures` can't police them
    and a weak model could misstate "labeled 4" when 40 changed. So for any action
    tool we author the confirmation ourselves from the real result — the model
    never gets to invent the number. Returns None when no action tool ran.
    """
    for entry in reversed(transcript):
        if entry.get("tool") not in chat_tools.ACTION_TOOLS:
            continue
        res = entry.get("result")
        if not isinstance(res, dict):
            continue
        if "error" in res:
            avail = res.get("available_categories")
            tail = f" Existing categories: {', '.join(avail)}." if avail else ""
            return f"I couldn't do that — {res['error']}.{tail}"
        action = res.get("action")
        if action == "categorize_merchant":
            if res.get("needs_confirmation"):
                ms = ", ".join(res.get("matched_merchants", []))
                return (
                    f"“{res.get('merchant_query')}” matches several merchants "
                    f"({ms}). Tell me a more specific name to categorize as "
                    f"{res.get('category')}."
                )
            n = int(res.get("transactions_updated", 0) or 0)
            ms = res.get("matched_merchants", [])
            if not ms or n == 0:
                return f"I couldn't find any payments matching “{res.get('merchant_query')}”."
            return (
                f"Categorized {n} payment{'s' if n != 1 else ''} from "
                f"{', '.join(ms)} as {res.get('category')}. Future imports will match too."
            )
        if action == "create_category":
            name = (res.get("category") or {}).get("name", "")
            return (
                f"Created the category “{name}”."
                if res.get("created")
                else f"The category “{name}” already exists."
            )
        if action == "rename_category":
            return (
                f"Renamed “{res.get('old_name')}” to “{res.get('new_name')}”."
            )
        if action == "set_category_icon":
            return f"Set {res.get('icon')} as the icon for “{res.get('name')}”."
        if action == "delete_category":
            return f"Deleted the category “{res.get('name')}”."
    return None


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
        "You are a personal-finance assistant that answers questions AND makes changes "
        f"to the user's own transaction data by calling tools. Today is {today}.\n\n"
        "Read tools (answer questions):\n"
        f"{chat_tools.TOOL_SPECS}\n\n"
        "Action tools (use ONLY when the user explicitly asks to change/label/categorize "
        "something). After an action, give a final answer confirming exactly what changed:\n"
        f"{chat_tools.ACTION_SPECS}\n\n"
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
        'User: Put all my swiggy orders under Food & Dining\n'
        '{"action":"call_tool","tool":"categorize_merchant","args":{"merchant":"swiggy","category":"Food & Dining"}}\n'
        f"{history}\n\n"
        f"User: {question}\n"
    )


def _answer_prompt(question: str, transcript: list[dict[str, Any]]) -> str:
    return (
        "You are a friendly personal-finance assistant. Using ONLY the tool results "
        "below, answer the user's question in one to three sentences. If the result is an "
        "action (it has an 'action' field), confirm exactly what changed — how many "
        "payments and which category — do not invent numbers. All amounts are in Indian "
        "Rupees: write every amount as 'Rs 1,200' — never use '$', never the rupee sign, "
        "never any other currency. Do NOT invent or recompute any number; use the figures "
        "exactly as given. If the data is empty, say so plainly.\n\n"
        f"Question: {question}\n"
        f"Tool results: {json.dumps(transcript, default=str)[:2000]}\n\n"
        "Answer:"
    )


def _run_tool(name: str, args: dict[str, Any], question: str, user_id: str, db: Client) -> dict[str, Any]:
    tool = chat_tools.TOOLS.get(name) or chat_tools.ACTION_TOOLS.get(name)
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
    question: str, user_id: str, db: Client, max_steps: int = DEFAULT_MAX_STEPS,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    """Answer ``question`` by letting the model drive tool calls over real data.

    Raises ``AgentUnavailable`` when no LLM is configured or the loop produced no
    usable data, so the caller can fall back to the deterministic path.

    If ``trace`` is provided, each executed tool step (tool, args, result) is
    appended to it for observability — the caller persists it to ``chat_traces``.
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
            # If a write-action ran, the confirmation is server-composed from the
            # real result — never the model's (unverifiable) count.
            confirmation = _action_confirmation(transcript)
            if confirmation:
                return _normalize_currency(confirmation)
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
            step = {"tool": name, "args": decision.get("args") or {}, "result": result}
            transcript.append(step)
            if trace is not None:
                trace.append(step)
            continue

        break  # unrecognised action

    if not transcript:
        raise AgentUnavailable("agent produced no tool results")

    # A write-action that never reached an explicit "final" still gets its
    # deterministic, server-composed confirmation (not a model-invented count).
    confirmation = _action_confirmation(transcript)
    if confirmation:
        return _normalize_currency(confirmation)

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
