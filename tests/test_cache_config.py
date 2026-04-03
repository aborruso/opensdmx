"""Tests for cache TTL configuration via environment variables."""

from __future__ import annotations

import importlib
import os


def _reload_config(**env_overrides):
    """Reload cache_config module with given env vars set."""
    import opensdmx.cache_config as mod
    old = {}
    for k, v in env_overrides.items():
        old[k] = os.environ.get(k)
        os.environ[k] = str(v)
    try:
        importlib.reload(mod)
        return mod
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_defaults():
    mod = _reload_config()
    assert mod.DATAFLOWS_CACHE_TTL == 604_800.0
    assert mod.METADATA_CACHE_TTL == 2_592_000.0
    assert mod.CONSTRAINTS_CACHE_TTL == 604_800.0


def test_env_override_dataflows():
    mod = _reload_config(OPENSDMX_DATAFLOWS_CACHE_TTL=42)
    assert mod.DATAFLOWS_CACHE_TTL == 42.0


def test_env_override_metadata():
    mod = _reload_config(OPENSDMX_METADATA_CACHE_TTL=100)
    assert mod.METADATA_CACHE_TTL == 100.0


def test_env_override_constraints():
    mod = _reload_config(OPENSDMX_CONSTRAINTS_CACHE_TTL=999)
    assert mod.CONSTRAINTS_CACHE_TTL == 999.0
