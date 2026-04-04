"""SQLite cache for dimensions and codelist data, namespaced per provider."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path


def _get_db_path() -> Path:
    from .base import get_cache_dir
    return get_cache_dir() / "cache.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


from .cache_config import CONSTRAINTS_CACHE_TTL, METADATA_CACHE_TTL


def _ensure_db() -> None:
    """Create tables and apply migrations for the current provider's database."""
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS structure_dims (
                structure_id TEXT NOT NULL,
                dimension_id TEXT NOT NULL,
                position     INTEGER,
                codelist_id  TEXT,
                cached_at    REAL NOT NULL,
                PRIMARY KEY (structure_id, dimension_id)
            );
            CREATE TABLE IF NOT EXISTS codelist_info (
                codelist_id TEXT PRIMARY KEY,
                description TEXT,
                cached_at   REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS codelist_values (
                codelist_id TEXT NOT NULL,
                code_id     TEXT NOT NULL,
                code_name   TEXT,
                cached_at   REAL NOT NULL,
                PRIMARY KEY (codelist_id, code_id)
            );
            CREATE TABLE IF NOT EXISTS invalid_datasets (
                df_id       TEXT PRIMARY KEY,
                marked_at   REAL NOT NULL,
                description TEXT
            );
            CREATE TABLE IF NOT EXISTS available_constraints (
                df_id        TEXT NOT NULL,
                dimension_id TEXT NOT NULL,
                code_id      TEXT NOT NULL,
                cached_at    REAL NOT NULL,
                PRIMARY KEY (df_id, dimension_id, code_id)
            );
        """)


def _get_conn_ready() -> sqlite3.Connection:
    """Return a connection, ensuring the DB schema exists first."""
    _ensure_db()
    return _get_conn()


# --- structure dims ---

def get_cached_dims(structure_id: str) -> dict | None:
    with _get_conn_ready() as conn:
        rows = conn.execute(
            "SELECT * FROM structure_dims WHERE structure_id = ? ORDER BY position",
            (structure_id,),
        ).fetchall()
    if not rows:
        return None
    if time.time() - rows[0]["cached_at"] > METADATA_CACHE_TTL:
        return None
    return {
        row["dimension_id"]: {
            "id": row["dimension_id"],
            "position": row["position"],
            "codelist_id": row["codelist_id"],
        }
        for row in rows
    }


def save_dims(structure_id: str, dims: dict) -> None:
    now = time.time()
    with _get_conn_ready() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO structure_dims VALUES (?, ?, ?, ?, ?)",
            [(structure_id, d["id"], d["position"], d["codelist_id"], now) for d in dims.values()],
        )


# --- codelist info (description) ---

def is_codelist_info_cached(codelist_id: str) -> bool:
    with _get_conn_ready() as conn:
        row = conn.execute(
            "SELECT cached_at FROM codelist_info WHERE codelist_id = ?",
            (codelist_id,),
        ).fetchone()
    if row is None:
        return False
    return time.time() - row["cached_at"] <= METADATA_CACHE_TTL


def get_cached_codelist_info(codelist_id: str) -> str | None:
    with _get_conn_ready() as conn:
        row = conn.execute(
            "SELECT description FROM codelist_info WHERE codelist_id = ?",
            (codelist_id,),
        ).fetchone()
    return row["description"] if row else None


def save_codelist_info(codelist_id: str, description: str | None) -> None:
    with _get_conn_ready() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO codelist_info VALUES (?, ?, ?)",
            (codelist_id, description, time.time()),
        )


# --- codelist values ---

def get_cached_codelist_values(codelist_id: str) -> list | None:
    with _get_conn_ready() as conn:
        rows = conn.execute(
            "SELECT code_id, code_name, cached_at FROM codelist_values WHERE codelist_id = ? ORDER BY code_id",
            (codelist_id,),
        ).fetchall()
    if not rows:
        return None
    if time.time() - rows[0]["cached_at"] > METADATA_CACHE_TTL:
        return None
    return [{"id": r["code_id"], "name": r["code_name"]} for r in rows]


def save_codelist_values(codelist_id: str, values: list) -> None:
    now = time.time()
    with _get_conn_ready() as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO codelist_values VALUES (?, ?, ?, ?)",
            [(codelist_id, v["id"], v["name"], now) for v in values],
        )


# --- available constraints ---

def get_cached_available_constraints(df_id: str) -> dict | None:
    with _get_conn_ready() as conn:
        rows = conn.execute(
            "SELECT dimension_id, code_id, cached_at FROM available_constraints WHERE df_id = ?",
            (df_id,),
        ).fetchall()
    if not rows:
        return None
    if time.time() - rows[0]["cached_at"] > CONSTRAINTS_CACHE_TTL:
        return None
    result: dict = {}
    for row in rows:
        result.setdefault(row["dimension_id"], []).append(row["code_id"])
    return result


def save_available_constraints(df_id: str, constraints: dict) -> None:
    now = time.time()
    rows = [
        (df_id, dim_id, code_id, now)
        for dim_id, codes in constraints.items()
        for code_id in codes
    ]
    with _get_conn_ready() as conn:
        conn.execute("DELETE FROM available_constraints WHERE df_id = ?", (df_id,))
        conn.executemany(
            "INSERT OR REPLACE INTO available_constraints VALUES (?, ?, ?, ?)", rows
        )


# --- invalid datasets ---

def save_invalid_dataset(df_id: str, description: str | None = None) -> None:
    with _get_conn_ready() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO invalid_datasets VALUES (?, ?, ?)",
            (df_id, time.time(), description),
        )


def get_invalid_dataset_ids() -> set:
    with _get_conn_ready() as conn:
        rows = conn.execute("SELECT df_id FROM invalid_datasets").fetchall()
    return {row["df_id"] for row in rows}


def list_invalid_datasets() -> list[dict]:
    with _get_conn_ready() as conn:
        rows = conn.execute(
            "SELECT df_id, description, marked_at FROM invalid_datasets ORDER BY marked_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_invalid_dataset(df_id: str) -> bool:
    """Delete a dataset from the blacklist. Returns True if it existed."""
    with _get_conn_ready() as conn:
        cur = conn.execute("DELETE FROM invalid_datasets WHERE df_id = ?", (df_id,))
        return cur.rowcount > 0
