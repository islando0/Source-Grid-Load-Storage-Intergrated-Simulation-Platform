"""轻量持久化：SQLite 记录仿真/优化运行。

原始时序仍放在 data/raw 与 data/output，数据库只存运行摘要与结果。
本机默认 SQLite；服务器若换 MySQL/PostgreSQL，需要把本模块替换为
SQLAlchemy 实现（当前版本未接入 MySQL，接口层不需要改）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR

DB_PATH = DATA_DIR / "platform.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                scenario TEXT NOT NULL,
                algorithm TEXT NOT NULL,
                c_w REAL NOT NULL,
                c_pv REAL NOT NULL,
                c_b REAL NOT NULL,
                e_b REAL NOT NULL,
                annual_cost REAL NOT NULL,
                lcoe REAL NOT NULL,
                curtail_rate REAL NOT NULL,
                soc_in_band_ratio REAL NOT NULL,
                ens_mwh REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )


def save_run(
    scenario: str,
    algorithm: str,
    x: list[float],
    metrics: dict[str, Any],
    payload: dict[str, Any],
) -> int:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO runs (
                created_at, scenario, algorithm, c_w, c_pv, c_b, e_b,
                annual_cost, lcoe, curtail_rate, soc_in_band_ratio, ens_mwh, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                scenario,
                algorithm,
                float(x[0]),
                float(x[1]),
                float(x[2]),
                float(x[3]),
                float(metrics.get("annual_cost", 0.0)),
                float(metrics.get("lcoe", 0.0)),
                float(metrics.get("curtail_rate", 0.0)),
                float(metrics.get("soc_in_band_ratio", 0.0)),
                float(metrics.get("ens_mwh", 0.0)),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, scenario, algorithm, c_w, c_pv, c_b, e_b,
                   annual_cost, lcoe, curtail_rate, soc_in_band_ratio, ens_mwh
            FROM runs ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def db_path() -> Path:
    return DB_PATH
