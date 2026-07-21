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
            last_karaoke INTEGER NOT NULL DEFAULT 0,

            last_daily INTEGER NOT NULL DEFAULT 0,
            last_weekly INTEGER NOT NULL DEFAULT 0,
            last_monthly INTEGER NOT NULL DEFAULT 0,
            last_yearly INTEGER NOT NULL DEFAULT 0
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

        CREATE TABLE IF NOT EXISTS shop_stock (
            item TEXT PRIMARY KEY,
            stock INTEGER NOT NULL,
            last_refresh INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lottery (
    id INTEGER PRIMARY KEY,
    prize INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS lottery_entries (
    user_id TEXT PRIMARY KEY,
    tickets INTEGER NOT NULL DEFAULT 0
);

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lender TEXT NOT NULL,
            borrower TEXT NOT NULL,
            amount INTEGER NOT NULL,
            created_at INTEGER NOT NULL
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

        CREATE TABLE IF NOT EXISTS owned_businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id TEXT NOT NULL,
            business_key TEXT NOT NULL,

            level INTEGER NOT NULL DEFAULT 1,

            last_collected INTEGER NOT NULL,

            lifetime_earnings INTEGER NOT NULL DEFAULT 0,

            purchased_at INTEGER NOT NULL,

            UNIQUE (
                user_id,
                business_key
            )
        );

        CREATE TABLE IF NOT EXISTS business_status (
            user_id TEXT PRIMARY KEY,

            last_raid INTEGER NOT NULL DEFAULT 0,

            protected_until INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    user_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    }

    inventory_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(inventory)"
        ).fetchall()
    }

    if "last_sideline" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_sideline
            INTEGER NOT NULL DEFAULT 0
            """
        )

    if "last_daily" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_daily
            INTEGER NOT NULL DEFAULT 0
            """
        )

    if "last_weekly" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_weekly
            INTEGER NOT NULL DEFAULT 0
            """
        )

    if "last_monthly" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_monthly
            INTEGER NOT NULL DEFAULT 0
            """
        )

    if "last_yearly" not in user_columns:
        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN last_yearly
            INTEGER NOT NULL DEFAULT 0
            """
        )

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
