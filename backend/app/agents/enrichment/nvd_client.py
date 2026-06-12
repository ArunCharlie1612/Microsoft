"""Live CVE enrichment via the NVD (National Vulnerability Database) REST API v2.0.

The Planner agent uses this to ground its attack-chain reasoning in real, current
vulnerabilities for the resource types Recon surfaced (e.g. "storage", "keyvault",
"vm"). Network/timeout failures degrade gracefully to an empty list so a run never
hard-fails on NVD being slow or unreachable.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_TIMEOUT_SECONDS = 5.0


def _best_cvss(metrics: dict[str, Any]) -> float:
    """Return the best-available CVSS base score from NVD metrics, or 0.0."""
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if entries:
            return float(entries[0].get("cvssData", {}).get("baseScore", 0.0))
    return 0.0


async def fetch_cves_for_keyword(keyword: str, max_results: int = 5) -> list[dict]:
    """Fetch recent CVEs matching ``keyword`` from the NVD 2.0 API.

    Args:
        keyword: Free-text keyword to search (NVD ``keywordSearch``).
        max_results: Maximum number of CVEs to request (NVD ``resultsPerPage``).

    Returns:
        A list of dicts each with keys ``cve_id``, ``description``, ``cvss_score``
        and ``published``. Returns an empty list if ``keyword`` is blank or the
        request fails/times out (a warning is logged in the failure case).
    """
    if not keyword.strip():
        return []

    params: dict[str, Any] = {"keywordSearch": keyword, "resultsPerPage": max_results}
    # An API key raises NVD's rate limit from 5 to 50 requests / 30s.
    if settings.nvd_api_key:
        params["apiKey"] = settings.nvd_api_key

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(_NVD_API, params=params)
            resp.raise_for_status()
            payload = resp.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("NVD lookup failed for keyword %r; returning no CVEs.", keyword)
        return []

    results: list[dict] = []
    for item in payload.get("vulnerabilities", [])[:max_results]:
        cve = item.get("cve", {})
        descriptions = cve.get("descriptions", [])
        description = next(
            (d["value"] for d in descriptions if d.get("lang") == "en"),
            "No description available",
        )
        results.append(
            {
                "cve_id": cve.get("id", "UNKNOWN"),
                "description": description,
                "cvss_score": _best_cvss(cve.get("metrics", {})),
                "published": cve.get("published", ""),
            }
        )
    return results
