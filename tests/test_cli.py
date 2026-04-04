"""Tests for opensdmx.cli — pure logic and error paths."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from click.exceptions import Exit as ClickExit
from typer.testing import CliRunner

from opensdmx.cli import _apply_provider, _parse_extra_filters, app

runner = CliRunner()


# ── _parse_extra_filters ─────────────────────────────────────────────


def _ctx(args: list[str]):
    """Build a minimal typer.Context stub with .args set."""
    return SimpleNamespace(args=args)


def test_parse_extra_filters_single():
    assert _parse_extra_filters(_ctx(["--geo", "IT"])) == {"geo": "IT"}


def test_parse_extra_filters_inline_plus():
    assert _parse_extra_filters(_ctx(["--geo", "IT+FR"])) == {"geo": "IT+FR"}


def test_parse_extra_filters_repeated_key():
    assert _parse_extra_filters(_ctx(["--geo", "IT", "--geo", "FR"])) == {"geo": "IT+FR"}


def test_parse_extra_filters_multiple_dimensions():
    result = _parse_extra_filters(_ctx(["--geo", "IT", "--freq", "A"]))
    assert result == {"geo": "IT", "freq": "A"}


def test_parse_extra_filters_empty():
    assert _parse_extra_filters(_ctx([])) == {}


def test_parse_extra_filters_unexpected_arg():
    with pytest.raises(ClickExit):
        _parse_extra_filters(_ctx(["badarg"]))


# ── _apply_provider ──────────────────────────────────────────────────


def test_apply_provider_valid_name():
    # Should not raise — istat is a known provider
    _apply_provider("istat")


def test_apply_provider_custom_url():
    # Custom HTTP URLs are accepted without error
    _apply_provider("https://example.com/rest")


def test_apply_provider_unknown_name():
    with pytest.raises(ClickExit):
        _apply_provider("not_a_real_provider_xyz")


def test_apply_provider_none_no_env(monkeypatch):
    monkeypatch.delenv("OPENSDMX_PROVIDER", raising=False)
    # None + no env var → no-op, no error
    _apply_provider(None)


# ── CLI commands via CliRunner ────────────────────────────────────────


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() != ""


def test_search_unknown_provider():
    with patch("opensdmx.cli._check_api_reachable"):
        result = runner.invoke(app, ["search", "unemployment", "--provider", "not_a_real_provider_xyz"])
    assert result.exit_code != 0
