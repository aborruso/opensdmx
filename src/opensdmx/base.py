"""Core HTTP client and provider configuration for SDMX 2.1 REST APIs."""

import json
import sys
import tempfile
import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

# Defaults for fields not specified in portals.json or custom providers
_DEFAULTS: dict = {
    "rate_limit": 0.5,
    "language": "en",
    "dataflow_params": {},
    "constraint_endpoint": "availableconstraint",
    "datastructure_agency": "ALL",
}

# Load portals from bundled JSON
_PORTALS_FILE = Path(__file__).parent / "portals.json"
with open(_PORTALS_FILE) as f:
    _raw_portals = json.load(f)

PROVIDERS: dict[str, dict] = {
    key: {**_DEFAULTS, **entry}
    for key, entry in _raw_portals.items()
}

_active_provider: str | dict = "eurostat"
_timeout: float = 300.0

_rate_limit_context: str = ""


def set_rate_limit_context(msg: str) -> None:
    """Set a human-readable label shown during rate-limit waits."""
    global _rate_limit_context
    _rate_limit_context = msg


def set_provider(
    name_or_url: str,
    agency_id: str | None = None,
    rate_limit: float = 0.5,
    language: str = "en",
) -> None:
    """Set the active SDMX provider.

    Args:
        name_or_url: Preset name (e.g. 'eurostat', 'istat', 'ecb') or a custom base URL.
        agency_id:   Required when name_or_url is a URL. Ignored for presets.
        rate_limit:  Minimum seconds between API calls (custom provider only).
        language:    Preferred language for descriptions (custom provider only).
    """
    global _active_provider
    if name_or_url in PROVIDERS:
        _active_provider = name_or_url
    else:
        if agency_id is None:
            raise ValueError("agency_id is required when using a custom base URL")
        _active_provider = {
            **_DEFAULTS,
            "base_url": name_or_url.rstrip("/"),
            "agency_id": agency_id,
            "rate_limit": rate_limit,
            "language": language,
        }


def get_provider() -> dict:
    """Return the active provider configuration dict."""
    if isinstance(_active_provider, dict):
        return _active_provider
    return PROVIDERS[_active_provider]


def get_base_url() -> str:
    return get_provider()["base_url"]


def get_agency_id() -> str:
    return get_provider()["agency_id"]


def get_cache_dir() -> Path:
    """Return cache directory for the active provider: ~/.cache/opensdmx/{agency_id}/"""
    agency = get_agency_id()
    cache_dir = Path.home() / ".cache" / "opensdmx" / agency
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def set_timeout(seconds: float | None = None) -> float:
    """Get or set the API timeout in seconds (default: 300)."""
    global _timeout
    if seconds is None:
        return _timeout
    old = _timeout
    _timeout = float(seconds)
    return old


def _rate_limit_file() -> Path:
    """Return per-provider rate limit temp file."""
    agency = get_agency_id()
    return Path(tempfile.gettempdir()) / f"opensdmx_{agency}_rate_limit.log"


def _rate_limit_check() -> None:
    """Wait if needed to respect the provider's rate limit.

    Reads the last-call timestamp from /tmp. If less than rate_limit seconds
    have passed since the last HTTP response, sleeps for the remaining time.
    The timestamp is written *after* the HTTP call completes (in sdmx_request),
    so the countdown starts from when the response was received.
    """
    min_interval = get_provider()["rate_limit"]
    rl_file = _rate_limit_file()
    if rl_file.exists():
        try:
            last = float(rl_file.read_text().strip())
            elapsed = time.time() - last
            if elapsed < min_interval:
                wait = min_interval - elapsed
                end_time = time.time() + wait
                label = _rate_limit_context or "Waiting"
                while True:
                    remaining = end_time - time.time()
                    if remaining <= 0:
                        break
                    sys.stderr.write(f"\r{label} ({remaining:.0f}s)...  ")
                    sys.stderr.flush()
                    time.sleep(0.2)
                sys.stderr.write("\n")
                sys.stderr.flush()
        except (ValueError, OSError):
            pass


def sdmx_request(path: str, accept: str = "application/xml", **params) -> httpx.Response:
    """Make a request to the active SDMX provider with retry logic."""
    url = f"{get_base_url()}/{path}"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
    def _do_request() -> httpx.Response:
        _rate_limit_check()
        with httpx.Client(timeout=_timeout) as client:
            resp = client.get(
                url,
                params=params or None,
                headers={
                    "Accept": accept,
                    "User-Agent": "opensdmx Python package",
                },
            )
            resp.raise_for_status()
            _rate_limit_file().write_text(str(time.time()))
            return resp

    return _do_request()


def sdmx_request_xml(path: str, **params):
    """Make a request and return the raw XML bytes."""
    resp = sdmx_request(path, accept="application/xml", **params)
    return resp.content


def sdmx_request_csv(path: str, **params):
    """Make a request and return CSV content as a Polars DataFrame."""
    import io
    import polars as pl

    fmt = get_provider().get("data_format_param")
    if fmt:
        resp = sdmx_request(path, accept="application/xml", format=fmt, **params)
    else:
        resp = sdmx_request(path, accept="text/csv", **params)
    return pl.read_csv(io.BytesIO(resp.content), infer_schema_length=10000)
