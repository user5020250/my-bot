import os
import sqlite3

DATA_DIR = os.getenv("DATA_DIR", "data")
os.makedirs(DATA_DIR, exist_ok=True)

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
            avg_buy_price INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, item)
        );
        """
    )

    try:
        conn.execute(
            """
            ALTER TABLE inventory
            ADD COLUMN avg_buy_price INTEGER NOT NULL DEFAULT 0
            """
        )
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()
