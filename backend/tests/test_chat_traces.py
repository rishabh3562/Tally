"""Tests for chat observability — trace collection + recording (no DB/network)."""

from app.services import chat_agent, chat_service
from tests.test_chat_service import _mk_db, _txn
from tests.test_chat_agent import _script_llm
from tests.test_chat_actions import _FakeDB, _store


async def test_run_agent_populates_trace(monkeypatch):
    _script_llm(monkeypatch, [
        {"action": "call_tool", "tool": "get_spending_summary", "args": {}},
        {"action": "final", "answer": "You spent Rs 150."},
    ])
    db = _mk_db(transactions=[_txn(100), _txn(50)])
    trace: list = []
    out = await chat_agent.run_agent("summary", "u", db, trace=trace)
    assert out == "You spent Rs 150."
    assert len(trace) == 1
    assert trace[0]["tool"] == "get_spending_summary"
    assert "result" in trace[0]


def test_record_trace_flags_action_turns():
    store = _store()
    steps = [{
        "tool": "categorize_merchant", "args": {},
        "result": {"action": "categorize_merchant", "transactions_updated": 4},
    }]
    chat_service._record_trace(_FakeDB(store), "u1", "q", steps, "ans", "agent", None, 12)
    ins = next(l for l in store["log"] if l["op"] == "insert" and l["table"] == "chat_traces")
    assert ins["payload"]["action_taken"] is True
    assert ins["payload"]["user_id"] == "u1"
    assert ins["payload"]["source"] == "agent"


def test_record_trace_read_turn_is_not_an_action():
    store = _store()
    steps = [{"tool": "get_spending_summary", "args": {}, "result": {"total_spent": 150}}]
    chat_service._record_trace(_FakeDB(store), "u1", "q", steps, "ans", "agent", None, 5)
    ins = next(l for l in store["log"] if l["op"] == "insert")
    assert ins["payload"]["action_taken"] is False


def test_save_messages_persists_turn_scoped_to_user():
    store = _store()
    chat_service._save_messages(_FakeDB(store), "u1", "my question", "the answer")
    inserts = [l for l in store["log"] if l["op"] == "insert" and l["table"] == "chat_messages"]
    assert len(inserts) == 2
    assert inserts[0]["payload"] == {"user_id": "u1", "role": "user", "content": "my question"}
    assert inserts[1]["payload"] == {"user_id": "u1", "role": "assistant", "content": "the answer"}
