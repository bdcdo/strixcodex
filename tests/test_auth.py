"""Auth tests with a mocked auth.json."""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path

import pytest

from strixcodex import auth


def _make_jwt(exp: int) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


@pytest.fixture
def fake_codex_home(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    return tmp_path


def test_borrow_returns_fresh_token(fake_codex_home: Path):
    token = _make_jwt(int(time.time()) + 3600)
    auth_file = fake_codex_home / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": token,
                    "refresh_token": "rt-xyz",
                    "account_id": "acct-1",
                },
            }
        )
    )
    got_token, got_account = auth.borrow_codex_key()
    assert got_token == token
    assert got_account == "acct-1"


def test_missing_file_raises(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    with pytest.raises(auth.BorrowKeyError):
        auth.borrow_codex_key()


def test_wrong_auth_mode_raises(fake_codex_home: Path):
    (fake_codex_home / "auth.json").write_text(
        json.dumps({"auth_mode": "apikey", "tokens": {"access_token": "x"}})
    )
    with pytest.raises(auth.BorrowKeyError, match="auth_mode"):
        auth.borrow_codex_key()


def test_missing_auth_mode_accepted(fake_codex_home: Path):
    """Some codex builds omit auth_mode; accept if tokens look right."""
    token = _make_jwt(int(time.time()) + 3600)
    (fake_codex_home / "auth.json").write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": token,
                    "refresh_token": "rt",
                    "account_id": "acct-2",
                }
            }
        )
    )
    got_token, got_account = auth.borrow_codex_key()
    assert got_token == token
    assert got_account == "acct-2"


def test_expired_triggers_refresh(fake_codex_home: Path, monkeypatch):
    expired = _make_jwt(int(time.time()) - 60)
    fresh = _make_jwt(int(time.time()) + 3600)
    auth_file = fake_codex_home / "auth.json"
    auth_file.write_text(
        json.dumps(
            {
                "auth_mode": "chatgpt",
                "tokens": {
                    "access_token": expired,
                    "refresh_token": "rt-xyz",
                    "account_id": "acct-1",
                },
            }
        )
    )

    refresh_calls: list = []

    def fake_refresh(refresh_token):
        refresh_calls.append(refresh_token)
        return {"access_token": fresh, "refresh_token": "rt-new"}

    monkeypatch.setattr(auth, "_refresh", fake_refresh)
    got_token, got_account = auth.borrow_codex_key()

    assert got_token == fresh
    assert got_account == "acct-1"
    assert refresh_calls == ["rt-xyz"]
    persisted = json.loads(auth_file.read_text())
    assert persisted["tokens"]["access_token"] == fresh
    assert persisted["tokens"]["refresh_token"] == "rt-new"
