"""Tests for opensdmx.discovery – set_filters / reset_filters (pure logic, no HTTP)."""

from __future__ import annotations

import warnings

import pytest
from opensdmx.discovery import reset_filters, set_filters


def _make_dataset(**dims) -> dict:
    """Build a minimal dataset dict for testing filter logic."""
    dimensions = {
        d: {"id": d, "position": i, "codelist_id": None}
        for i, d in enumerate(dims or ["FREQ", "GEO", "AGE"])
    }
    filters = {d: "." for d in dimensions}
    return {
        "df_id": "TEST_DF",
        "version": "1.0",
        "df_description": "Test dataset",
        "df_structure_id": "TEST_DSD",
        "dimensions": dimensions,
        "filters": filters,
    }


# ── set_filters ──────────────────────────────────────────────────────

def test_set_filters_basic():
    ds = _make_dataset(FREQ=0, GEO=1, AGE=2)
    result = set_filters(ds, FREQ="A", GEO="IT")
    assert result["filters"]["FREQ"] == "A"
    assert result["filters"]["GEO"] == "IT"
    assert result["filters"]["AGE"] == "."


def test_set_filters_case_insensitive():
    ds = _make_dataset(FREQ=0, GEO=1)
    result = set_filters(ds, freq="M", geo="DE")
    assert result["filters"]["FREQ"] == "M"
    assert result["filters"]["GEO"] == "DE"


def test_set_filters_returns_copy():
    ds = _make_dataset(FREQ=0, GEO=1)
    result = set_filters(ds, FREQ="A")
    assert result is not ds
    assert ds["filters"]["FREQ"] == "."  # original unchanged


def test_set_filters_list_value():
    ds = _make_dataset(GEO=0)
    result = set_filters(ds, GEO=["IT", "FR", "DE"])
    assert result["filters"]["GEO"] == ["IT", "FR", "DE"]


def test_set_filters_unknown_dimension_warns():
    ds = _make_dataset(FREQ=0)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        result = set_filters(ds, NONEXISTENT="X")
        assert len(w) == 1
        assert "NONEXISTENT" in str(w[0].message)
    assert "NONEXISTENT" not in result["filters"]


# ── reset_filters ────────────────────────────────────────────────────

def test_reset_filters():
    ds = _make_dataset(FREQ=0, GEO=1)
    ds = set_filters(ds, FREQ="A", GEO="IT")
    result = reset_filters(ds)
    assert result["filters"]["FREQ"] == "."
    assert result["filters"]["GEO"] == "."


def test_reset_filters_returns_copy():
    ds = _make_dataset(FREQ=0)
    ds_filtered = set_filters(ds, FREQ="A")
    result = reset_filters(ds_filtered)
    assert result is not ds_filtered
    assert ds_filtered["filters"]["FREQ"] == "A"  # original unchanged
