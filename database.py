import os
import sqlite3

DATA_DIR = os.getenv(
    "DATA_DIR",
    "data",
)

os.makedirs(
    DATA_DIR,
    exist_ok=True,
)

DB_PATH = os.path.join(
    DATA_DIR,
    "economy.db",
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(
        DB_PATH
    )
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
            last_sideline INTEGER NOT NULL DEFAULT 0,
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
        CREATE TABLE IF NOT EXISTS inventory (
            user_id TEXT NOT NULL,
            item TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0,
            avg_buy_price INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (
                user_id,
                item
            )
        );
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lender TEXT NOT NULL,
            borrower TEXT NOT NULL,
            principal INTEGER NOT NULL,
            remaining INTEGER NOT NULL,
            due_date INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at INTEGER NOT NULL
        );
        """
    )

    user_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "last_sideline" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_sideline
            INTEGER NOT NULL DEFAULT 0
            """
        )

    inventory_columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(inventory)"
        ).fetchall()
    ]

    if "avg_buy_price" not in inventory_columns:
        conn.execute(
            """
            ALTER TABLE inventory
            ADD COLUMN avg_buy_price
            INTEGER NOT NULL DEFAULT 0
            """
        )

    conn.commit()
    conn.close()
