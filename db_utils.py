"""
db_utils.py

Small helper functions wrapping common reads/writes to the SQLite database.
Every cog imports from here instead of touching SQL directly.
"""

import time
from database import get_conn

STARTING_MONEY = 1000

# Field names are only ever supplied by our own code below (never straight
# from user input), so building the UPDATE with an f-string here is safe.
_ALLOWED_COOLDOWN_FIELDS = {
    "last_trabaho",
    "last_tambay",
    "last_budol",
    "last_baon",
    "last_karaoke",
}


def get_user(user_id: str) -> dict:
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (id, balance) VALUES (?, ?)", (user_id, STARTING_MONEY)
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row)


def set_balance(user_id: str, amount) -> int:
    get_user(user_id)  # ensure row exists
    amount = max(0, round(amount))
    conn = get_conn()
    conn.execute("UPDATE users SET balance = ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()
    return amount


def add_balance(user_id: str, delta) -> int:
    user = get_user(user_id)
    return set_balance(user_id, user["balance"] + delta)


def set_job(user_id: str, job: str) -> None:
    get_user(user_id)
    conn = get_conn()
    conn.execute("UPDATE users SET job = ? WHERE id = ?", (job, user_id))
    conn.commit()
    conn.close()


def set_cooldown(user_id: str, field: str, timestamp: int) -> None:
    if field not in _ALLOWED_COOLDOWN_FIELDS:
        raise ValueError(f"Unknown cooldown field: {field}")
    get_user(user_id)
    conn = get_conn()
    conn.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (timestamp, user_id))
    conn.commit()
    conn.close()


def check_cooldown(user_id: str, field: str, cooldown_seconds: int) -> int:
    """Returns remaining seconds on cooldown, or 0 if ready."""
    if field not in _ALLOWED_COOLDOWN_FIELDS:
        raise ValueError(f"Unknown cooldown field: {field}")
    user = get_user(user_id)
    last = user[field] or 0
    now = int(time.time())
    remaining = cooldown_seconds - (now - last)
    return remaining if remaining > 0 else 0


def format_peso(amount) -> str:
    return f"₱{amount:,.0f}"


def format_duration(seconds) -> str:
    seconds = int(seconds)
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if hrs:
        parts.append(f"{hrs}h")
    if mins:
        parts.append(f"{mins}m")
    if secs and not hrs:
        parts.append(f"{secs}s")
    return " ".join(parts) or "0s"


def get_inventory_qty(user_id: str, item: str) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT qty FROM inventory WHERE user_id = ? AND item = ?", (user_id, item)
    ).fetchone()
    conn.close()
    return row["qty"] if row else 0


def add_inventory(user_id: str, item: str, delta: int) -> int:
    current = get_inventory_qty(user_id, item)
    new_qty = max(0, current + delta)
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO inventory (user_id, item, qty) VALUES (?, ?, ?)
        ON CONFLICT(user_id, item) DO UPDATE SET qty = excluded.qty
        """,
        (user_id, item, new_qty),
    )
    conn.commit()
    conn.close()
    return new_qty
