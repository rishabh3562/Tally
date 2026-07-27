"""Guards that have to hold before this app gets a public URL.

Everything here was found by auditing for deployment: an unauthenticated endpoint
that leaked another user's email, a form field that was trusted as an account id,
writes that proved ownership and then didn't scope the write, and a subject claim
interpolated into PostgREST filter grammar without validation.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.core import auth
from app.main import app


# --- the signup route must stay deleted -------------------------------------

def test_there_is_no_signup_route():
    """It was unauthenticated and returned any user's email + preferences given
    only their UUID; provisioning happens in auth._ensure_user_provisioned."""
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert not any("signup" in p for p in paths), paths


def test_signup_path_404s():
    with TestClient(app) as c:
        r = c.post("/api/users/signup", json={"email": "a@b.c", "user_id": "x"})
    assert r.status_code == 404


# --- the subject claim must be a UUID ---------------------------------------

def _token_payload(monkeypatch, sub):
    """Drive get_current_user with a fixed decoded payload."""
    monkeypatch.setattr(auth.jwt, "get_unverified_header", lambda t: {"alg": "ES256"})
    monkeypatch.setattr(auth, "_get_jwks_client", lambda: _FakeJWKS())
    monkeypatch.setattr(auth.jwt, "decode", lambda *a, **k: {"sub": sub, "email": "e@x.y"})
    monkeypatch.setattr(auth, "_ensure_user_provisioned", lambda *a, **k: None)


class _FakeJWKS:
    def get_signing_key_from_jwt(self, token):
        class _K:
            key = "k"
        return _K()


def test_a_uuid_subject_is_accepted(monkeypatch):
    uid = "a1a99587-4efe-4e12-bbdc-5838cac429c3"
    _token_payload(monkeypatch, uid)
    assert asyncio.run(auth.get_current_user("Bearer x")) == uid


@pytest.mark.parametrize("sub", [
    # `,` and `()` are operators in a PostgREST or-expression, which several
    # routers build by interpolating this value.
    "abc,def",
    "x)or(1.eq.1",
    "not-a-uuid",
])
def test_a_non_uuid_subject_is_rejected(monkeypatch, sub):
    from fastapi import HTTPException

    _token_payload(monkeypatch, sub)
    with pytest.raises(HTTPException) as e:
        asyncio.run(auth.get_current_user("Bearer x"))
    assert e.value.status_code == 401


# --- upload must prove the account belongs to the caller --------------------

class _Res:
    def __init__(self, data):
        self.data = data


class _Q:
    def __init__(self, rows, log):
        self._rows, self._log = rows, log
        self._eq = {}

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._eq[col] = val
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        self._log.append(dict(self._eq))
        rows = [
            r for r in self._rows
            if all(r.get(k) == v for k, v in self._eq.items())
        ]
        return _Res(rows)


class _DB:
    """Only the accounts table matters here — the handler must 404 before it
    touches anything else."""

    def __init__(self, accounts):
        self._accounts = accounts
        self.log: list[dict] = []

    def table(self, name):
        return _Q(self._accounts if name == "accounts" else [], self.log)


class _Upload:
    filename = "statement.pdf"

    async def read(self):
        return b"%PDF-1.4 fake"


class _Settings:
    allowed_extensions = {"pdf", "csv", "xlsx"}
    allowed_file_types = "pdf,csv,xlsx"


ACCOUNTS = [
    {"id": "acct-a", "user_id": "A"},
    {"id": "acct-b", "user_id": "B"},
]


def _upload(account_id, user_id, db):
    from app.api import uploads
    from fastapi import HTTPException

    try:
        return asyncio.run(uploads.upload_statement(
            file=_Upload(), account_id=account_id, bank_code="HDFC",
            user_id=user_id, db=db, settings=_Settings(),
        )), None
    except HTTPException as e:
        return None, e


def test_uploading_into_someone_elses_account_is_refused():
    """It used to be accepted: account_id came from a form field and was never
    checked, so the dedup read below it became an oracle over B's fingerprints."""
    db = _DB(ACCOUNTS)
    out, err = _upload("acct-b", "A", db)
    assert out is None
    assert err is not None and err.status_code == 404
    # 404, not 403 — don't confirm that another user's account id exists.
    assert "not found" in str(err.detail).lower()


def test_the_ownership_check_is_scoped_to_both_id_and_user():
    db = _DB(ACCOUNTS)
    _upload("acct-b", "A", db)
    assert db.log and db.log[0] == {"id": "acct-b", "user_id": "A"}


def test_an_unknown_account_is_refused_too():
    db = _DB(ACCOUNTS)
    out, err = _upload("acct-nope", "A", db)
    assert out is None and err.status_code == 404


# --- production posture -----------------------------------------------------

@pytest.mark.parametrize("env,expected", [
    ("production", True), ("PRODUCTION", True), ("prod", True),
    ("development", False), ("staging", False), ("", False),
])
def test_is_production_detection(env, expected):
    from app.core.config import Settings

    s = Settings(environment=env, supabase_url="https://x.supabase.co", supabase_key="k")
    assert s.is_production is expected


def test_cors_origins_ignores_blank_entries():
    """A trailing comma in the env var used to produce an empty allowed origin."""
    from app.core.config import Settings

    s = Settings(
        supabase_url="https://x.supabase.co", supabase_key="k",
        cors_origins="https://a.vercel.app, ,https://b.vercel.app,",
    )
    assert s.cors_origins_list == ["https://a.vercel.app", "https://b.vercel.app"]
