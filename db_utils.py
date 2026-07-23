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
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = sqlite3.Row

    return conn


def add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
):
    columns = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }

    if column not in columns:
        conn.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_db() -> None:
    conn = get_conn()

    # NOTE: the following tables were removed along with their cogs and
    # are no longer created here:
    #   - inventory          (was inventory.py)
    #   - shop_stock         (was shop.py)
    #   - debts              (was loan.py)
    #   - loans              (was loan.py)
    #   - owned_businesses   (was business.py)
    #   - business_status    (was business.py)
    #   - lottery            (was lottery.py)
    #   - lottery_entries    (was lottery.py)
    #   - lottery_channels   (was lottery.py)
    # If any leftover tables exist in an old economy.db file, they are
    # simply ignored (not dropped) — see the DROP TABLE section below if
    # you want this script to clean them up automatically instead.
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
            last_yearly INTEGER NOT NULL DEFAULT 0,

            last_fish INTEGER NOT NULL DEFAULT 0,
            last_mine INTEGER NOT NULL DEFAULT 0,
            last_farm INTEGER NOT NULL DEFAULT 0,
            last_hunt INTEGER NOT NULL DEFAULT 0,
            last_cook INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    user_migrations = {
        "last_sideline": "INTEGER NOT NULL DEFAULT 0",
        "last_daily": "INTEGER NOT NULL DEFAULT 0",
        "last_weekly": "INTEGER NOT NULL DEFAULT 0",
        "last_monthly": "INTEGER NOT NULL DEFAULT 0",
        "last_yearly": "INTEGER NOT NULL DEFAULT 0",
        "last_fish": "INTEGER NOT NULL DEFAULT 0",
        "last_mine": "INTEGER NOT NULL DEFAULT 0",
        "last_farm": "INTEGER NOT NULL DEFAULT 0",
        "last_hunt": "INTEGER NOT NULL DEFAULT 0",
        "last_cook": "INTEGER NOT NULL DEFAULT 0",
    }

    for column, definition in user_migrations.items():
        add_column_if_missing(
            conn,
            "users",
            column,
            definition,
        )

    # Drops tables from old/removed features so they don't linger in
    # existing economy.db files. Safe to run repeatedly (IF EXISTS).
    conn.executescript(
        """
        DROP TABLE IF EXISTS lotteries;
        DROP TABLE IF EXISTS lottery;
        DROP TABLE IF EXISTS lottery_entries;
        DROP TABLE IF EXISTS lottery_channels;
        DROP TABLE IF EXISTS inventory;
        DROP TABLE IF EXISTS shop_stock;
        DROP TABLE IF EXISTS debts;
        DROP TABLE IF EXISTS loans;
        DROP TABLE IF EXISTS owned_businesses;
        DROP TABLE IF EXISTS business_status;
        """
    )

    conn.commit()
    conn.close()
