"""Unit tests for the NVD CVE enrichment client.

Mocks the httpx call so no network access is required and verifies:
- a successful response is mapped to the documented list structure;
- a timeout returns an empty list without raising.
"""

from __future__ import annotations

import httpx

from app.agents.enrichment import nvd_client
from app.agents.enrichment.nvd_client import fetch_cves_for_keyword

_SAMPLE_RESPONSE = {
    "vulnerabilities": [
        {
            "cve": {
                "id": "CVE-2024-12345",
                "published": "2024-03-01T00:00:00.000",
                "descriptions": [
                    {"lang": "en", "value": "A sample storage account misconfiguration."},
                    {"lang": "es", "value": "ignored non-english description"},
                ],
                "metrics": {
                    "cvssMetricV31": [{"cvssData": {"baseScore": 9.8}}],
                },
            }
        }
    ]
}


class _MockResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:  # no-op: simulates a 200 OK
        return None

    def json(self) -> dict:
        return self._payload


class _MockAsyncClient:
    """Stands in for httpx.AsyncClient as an async context manager."""

    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def __aenter__(self) -> _MockAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, *args: object, **kwargs: object) -> _MockResponse:
        return _MockResponse(self._payload)


class _TimeoutAsyncClient:
    """Async client whose GET always times out."""

    async def __aenter__(self) -> _TimeoutAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, *args: object, **kwargs: object) -> _MockResponse:
        raise httpx.ReadTimeout("timed out")


async def test_fetch_cves_success_returns_expected_structure(monkeypatch):
    monkeypatch.setattr(
        nvd_client.httpx,
        "AsyncClient",
        lambda *a, **k: _MockAsyncClient(_SAMPLE_RESPONSE),
    )

    results = await fetch_cves_for_keyword("storage")

    assert results == [
        {
            "cve_id": "CVE-2024-12345",
            "description": "A sample storage account misconfiguration.",
            "cvss_score": 9.8,
            "published": "2024-03-01T00:00:00.000",
        }
    ]


async def test_fetch_cves_timeout_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        nvd_client.httpx,
        "AsyncClient",
        lambda *a, **k: _TimeoutAsyncClient(),
    )

    results = await fetch_cves_for_keyword("keyvault")

    assert results == []


async def test_fetch_cves_blank_keyword_skips_request():
    assert await fetch_cves_for_keyword("   ") == []
