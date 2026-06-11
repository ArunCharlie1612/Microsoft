"""Unit tests for the read-only Azure Resource Graph scanner."""
from __future__ import annotations

import pytest

from app.core.azure_scanner import _public_exposure, scan_subscription


@pytest.mark.asyncio
async def test_scan_subscription_returns_none_without_subscription():
    assert await scan_subscription("") is None


def test_public_exposure_storage_public_blob():
    assert _public_exposure(
        "Microsoft.Storage/storageAccounts", {"allowBlobPublicAccess": True}
    ) is True


def test_public_exposure_storage_private():
    assert _public_exposure(
        "Microsoft.Storage/storageAccounts",
        {"allowBlobPublicAccess": False, "networkAcls": {"defaultAction": "Deny"}},
    ) is False


def test_public_exposure_public_ip_always_true():
    assert _public_exposure("Microsoft.Network/publicIPAddresses", {}) is True


def test_public_exposure_sql_public_network():
    assert _public_exposure(
        "Microsoft.Sql/servers", {"publicNetworkAccess": "Enabled"}
    ) is True


def test_public_exposure_unknown_type():
    assert _public_exposure("Microsoft.Foo/bar", {}) is False
