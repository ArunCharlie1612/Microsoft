"""Unit tests for security guardrails: scope, consent, and rate limiting."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.ratelimit import RateLimiter
from app.core.security import enforce_consent, enforce_scope


def test_enforce_consent_passes_when_attested():
    # Should not raise.
    enforce_consent(acknowledged=True, authorized_by="Jane Owner")


def test_enforce_consent_rejects_missing_attestation(monkeypatch):
    monkeypatch.setattr(settings, "breachsim_require_consent", True)
    with pytest.raises(HTTPException) as exc:
        enforce_consent(acknowledged=False, authorized_by="")
    assert exc.value.status_code == 403


def test_enforce_consent_rejects_blank_authorizer(monkeypatch):
    monkeypatch.setattr(settings, "breachsim_require_consent", True)
    with pytest.raises(HTTPException) as exc:
        enforce_consent(acknowledged=True, authorized_by="   ")
    assert exc.value.status_code == 403


def test_enforce_consent_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "breachsim_require_consent", False)
    enforce_consent(acknowledged=False, authorized_by="")


def test_enforce_scope_rejects_non_sandbox(monkeypatch):
    monkeypatch.setattr(settings, "breachsim_sandbox_only", True)
    with pytest.raises(HTTPException) as exc:
        enforce_scope("00000000-0000-0000-0000-000000000000", sandbox_only=False)
    assert exc.value.status_code == 403


def test_enforce_scope_rejects_out_of_allowlist(monkeypatch):
    monkeypatch.setattr(settings, "breachsim_sandbox_only", False)
    monkeypatch.setattr(settings, "breachsim_allowed_subscriptions", "allowed-sub")
    with pytest.raises(HTTPException) as exc:
        enforce_scope("other-sub", sandbox_only=True)
    assert exc.value.status_code == 403


def test_rate_limiter_blocks_after_burst(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_runs_per_minute", 3)
    limiter = RateLimiter()
    # Burst capacity == rate; the (rate+1)-th call within the window is rejected.
    limiter.check("caller")
    limiter.check("caller")
    limiter.check("caller")
    with pytest.raises(HTTPException) as exc:
        limiter.check("caller")
    assert exc.value.status_code == 429


def test_rate_limiter_is_per_key(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_runs_per_minute", 1)
    limiter = RateLimiter()
    limiter.check("a")
    limiter.check("b")  # different key, should not raise
    with pytest.raises(HTTPException):
        limiter.check("a")
