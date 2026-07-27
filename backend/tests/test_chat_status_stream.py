"""Progress events on the chat stream.

The live free model takes ~5s typically and was measured at 68s once. Three
bouncing dots for that long reads as broken, so the stream now carries
`event: status` progress alongside the answer. These tests pin the wire format
AND reassemble it the way the browser does, so a status line can never end up
inside the answer text.
"""

import asyncio

import pytest

from app.services import chat_service as cs


class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def gte(self, *a, **k):
        return self

    def lte(self, *a, **k):
        return self

    def insert(self, *a, **k):
        return self

    def execute(self):
        return _Res([])


class _DB:
    def table(self, _n):
        return _Q()


def _collect(question: str, db=None) -> list[str]:
    async def run():
        return [e async for e in cs.stream_chat_response(question, "u1", db or _DB())]

    return asyncio.run(run())


def _as_browser(events: list[str]) -> tuple[str, list[str]]:
    """Reassemble exactly like useChat.ts: track the current event name, route
    status payloads to a list and everything else into the answer."""
    answer, statuses, event_name = "", [], ""
    for chunk in events:
        for line in chunk.split("\n"):
            if line.startswith("event: "):
                event_name = line[7:].strip()
            elif line.startswith("data: "):
                payload = line[6:]
                if event_name == "status":
                    statuses.append(payload)
                else:
                    answer += payload.replace("\\n", "\n")
            elif line == "":
                event_name = ""
    return answer, statuses


def test_every_event_is_correctly_framed():
    events = _collect("help")
    for e in events:
        assert e.endswith("\n\n")
        for line in e.split("\n")[:-2]:
            assert line == "" or line.startswith(("data: ", "event: ")), line


def test_a_slow_answer_reports_progress_before_the_answer(monkeypatch):
    async def slow(*a, **k):
        await asyncio.sleep(3.2)
        return "Done."

    monkeypatch.setattr(cs, "_resolve_answer", slow)
    monkeypatch.setattr(cs, "_PROGRESS_STEPS", [(0.0, "First…"), (0.2, "Second…")])

    events = _collect("anything")
    answer, statuses = _as_browser(events)
    assert statuses == ["First…", "Second…"]
    assert answer.strip() == "Done."
    # Progress must arrive before any answer token, or it's not progress.
    assert events.index("event: status\ndata: First…\n\n") < len(statuses) + 1


def test_status_text_never_leaks_into_the_answer(monkeypatch):
    async def slow(*a, **k):
        await asyncio.sleep(0.3)
        return "Top merchants:\n• Amazon — Rs 100"

    monkeypatch.setattr(cs, "_resolve_answer", slow)
    monkeypatch.setattr(cs, "_PROGRESS_STEPS", [(0.0, "Reading your transactions…")])

    answer, statuses = _as_browser(_collect("anything"))
    assert statuses == ["Reading your transactions…"]
    assert "Reading" not in answer
    # The listing's line break still survives the same stream.
    assert answer.split("\n")[0].strip() == "Top merchants:"


def test_a_fast_answer_wastes_no_progress_events(monkeypatch):
    async def instant(*a, **k):
        return "Instant."

    monkeypatch.setattr(cs, "_resolve_answer", instant)
    answer, statuses = _as_browser(_collect("help"))
    assert statuses == []
    assert answer.strip() == "Instant."


def test_a_failing_resolve_still_answers_and_stops_progress(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(cs, "_resolve_answer", boom)
    answer, _ = _as_browser(_collect("anything"))
    assert "couldn't answer that right now" in answer
