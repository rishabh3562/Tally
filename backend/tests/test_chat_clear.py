"""DELETE /api/chat/messages ("New chat") must scope the delete to the caller.

The backend uses the service-role key (bypasses RLS), so the handler's
``.eq("user_id", ...)`` is the ONLY thing preventing a clear from wiping another
user's messages. This asserts that filter is applied.
"""

from app.api import chat


class _Recorder(dict):
    pass


class _DeleteQuery:
    def __init__(self, rec):
        self.rec = rec

    def delete(self):
        self.rec["deleted"] = True
        return self

    def eq(self, col, val):
        self.rec["eq"] = (col, val)
        return self

    def execute(self):
        self.rec["executed"] = True
        return type("R", (), {"data": []})()


class _FakeDB:
    def __init__(self, rec):
        self.rec = rec

    def table(self, name):
        self.rec["table"] = name
        return _DeleteQuery(self.rec)


async def test_clear_scopes_delete_to_caller():
    rec = _Recorder()
    out = await chat.clear_chat_messages(user_id="A", db=_FakeDB(rec))
    assert out["status"] == "cleared"
    assert rec["table"] == "chat_messages"
    assert rec["deleted"] is True
    assert rec["eq"] == ("user_id", "A")  # never targets another user's rows
    assert rec["executed"] is True
