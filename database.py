"""
database.py

Sets up a persistent SQLite database. As long as the .db file on disk isn't
deleted, all player balances/jobs/inventory survive bot restarts, crashes,
and code redeploys — pushing new code to GitHub/Railway never touches this
file.

IMPORTANT FOR RAILWAY: Railway's default filesystem is wiped on every
redeploy. To make this survive redeploys, attach a Railway "Volume" and
mount it to /data, then set the environment variable:

    DATA_DIR=/data

If DATA_DIR isn't set, it defaults to a local ./data folder (fine for
running on your own PC, NOT safe on Railway without a volume).
See README.md for the exact steps.
"""

import os
import sqlite3

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "economy.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            balance INTEGER NOT NULL DEFAULT 1000,
            job TEXT DEFAULT NULL,
            last_trabaho INTEGER NOT NULL DEFAULT 0,
            last_tambay INTEGER NOT NULL DEFAULT 0,
            last_budol INTEGER NOT NULL DEFAULT 0,
            last_baon INTEGER NOT NULL DEFAULT 0,
            last_karaoke INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lender TEXT NOT NULL,
            borrower TEXT NOT NULL,
            amount INTEGER NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market (
            item TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            buy_price INTEGER NOT NULL,
            sell_price INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS inventory (
            user_id TEXT NOT NULL,
            item TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item)
        );
        """
    )
    conn.commit()
    conn.close()
