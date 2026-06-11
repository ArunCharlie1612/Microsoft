"""Real CVE lookups against the NVD 2.0 API.

Used by the Research Agent when an Azure AI Search CVE index is not configured. This
replaces the previous hard-coded ``CVE-2023-EXAMPLE`` placeholder with live data from
the National Vulnerability Database so findings cite real vulnerabilities. Results are
cached in-process to respect NVD rate limits. Network/permission failures degrade
gracefully to an empty list (the caller then uses a clearly-labelled fallback).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_cache: dict[str, list[dict[str, Any]]] = {}


def _severity(metrics: dict[str, Any]) -> tuple[float, str]:
    """Extract the best-available CVSS base score + severity from NVD metrics."""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if entries:
            data = entries[0].get("cvssData", {})
            score = float(data.get("baseScore", 0.0))
            sev = entries[0].get("baseSeverity") or data.get("baseSeverity") or "UNKNOWN"
            return score, str(sev).lower()
    return 0.0, "unknown"


async def search_cves(query: str, top: int = 3) -> list[dict[str, Any]]:
    """Return up to ``top`` real CVEs matching ``query`` from NVD, or ``[]`` on failure."""
    if not settings.nvd_lookups_enabled or not query.strip():
        return []
    cache_key = f"{query}|{top}"
    if cache_key in _cache:
        return _cache[cache_key]

    headers = {"apiKey": settings.nvd_api_key} if settings.nvd_api_key else {}
    params = {"keywordSearch": query, "resultsPerPage": top}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_NVD_API, params=params, headers=headers)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("NVD lookup failed for query %r; returning no evidence.", query)
        return []

    results: list[dict[str, Any]] = []
    for item in payload.get("vulnerabilities", [])[:top]:
        cve = item.get("cve", {})
        descriptions = cve.get("descriptions", [])
        title = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"),
            "No description available",
        )
        score, sev = _severity(cve.get("metrics", {}))
        results.append(
            {
                "id": cve.get("id", "UNKNOWN"),
                "title": title[:280],
                "cvss": score,
                "severity": sev,
                "source": "NVD",
            }
        )
    _cache[cache_key] = results
    return results
