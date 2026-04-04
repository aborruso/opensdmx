"""Tests for opensdmx.base — provider management."""

from __future__ import annotations

import pytest
from opensdmx.base import PROVIDERS, get_provider, set_provider


def test_set_provider_preset():
    set_provider("eurostat")
    assert get_provider()["base_url"] == PROVIDERS["eurostat"]["base_url"]


def test_set_provider_custom_url_no_agency():
    """Custom URL should work without agency_id (no longer raises)."""
    set_provider("https://custom.sdmx.org/rest")
    p = get_provider()
    assert p["base_url"] == "https://custom.sdmx.org/rest"
    assert p["agency_id"] == ""


def test_set_provider_custom_url_with_agency():
    set_provider("https://custom.sdmx.org/rest", agency_id="XYZ")
    p = get_provider()
    assert p["agency_id"] == "XYZ"


def test_set_provider_unknown_name_not_url():
    """Unknown non-URL string is treated as custom URL (no agency)."""
    set_provider("not_a_real_provider")
    p = get_provider()
    assert p["base_url"] == "not_a_real_provider"


def test_set_provider_restores():
    """Restore default after custom provider tests."""
    set_provider("eurostat")
    assert get_provider()["agency_id"] == "ESTAT"
