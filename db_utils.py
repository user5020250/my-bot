"""
db_utils.py

Small helper functions wrapping common reads/writes to the SQLite database.
Every cog imports from here instead of touching SQL directly.
"""

import time

from database import get_conn

STARTING_MONEY = 1000

_ALLOWED_COOLDOWN_FIELDS = {
    "last_trabaho",
    "last_tambay",
    "last_budol",
    "last_baon",
    "last_karaoke",
}


def get_user(user_id: str) -> dict:
    conn = get_conn()

    row = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO users (
                id,
                balance
            )
            VALUES (?, ?)
            """,
            (
                user_id,
                STARTING_MONEY,
            ),
        )

        conn.commit()

        row = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()

    conn.close()

    return dict(row)


def set_balance(
    user_id: str,
    amount,
) -> int:

    get_user(user_id)

    amount = max(
        0,
        round(amount),
    )

    conn = get_conn()

    conn.execute(
        """
        UPDATE users
        SET balance = ?
        WHERE id = ?
        """,
        (
            amount,
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    return amount


def add_balance(
    user_id: str,
    delta,
) -> int:

    user = get_user(user_id)

    return set_balance(
        user_id,
        user["balance"] + delta,
    )


def set_job(
    user_id: str,
    job: str,
) -> None:

    get_user(user_id)

    conn = get_conn()

    conn.execute(
        """
        UPDATE users
        SET job = ?
        WHERE id = ?
        """,
        (
            job,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


def set_cooldown(
    user_id: str,
    field: str,
    timestamp: int,
) -> None:

    if field not in _ALLOWED_COOLDOWN_FIELDS:
        raise ValueError(
            f"Unknown cooldown field: {field}"
        )

    get_user(user_id)

    conn = get_conn()

    conn.execute(
        f"""
        UPDATE users
        SET {field} = ?
        WHERE id = ?
        """,
        (
            timestamp,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


def check_cooldown(
    user_id: str,
    field: str,
    cooldown_seconds: int,
) -> int:

    if field not in _ALLOWED_COOLDOWN_FIELDS:
        raise ValueError(
            f"Unknown cooldown field: {field}"
        )

    user = get_user(user_id)

    last = user[field] or 0

    now = int(
        time.time()
    )

    remaining = cooldown_seconds - (
        now - last
    )

    return (
        remaining
        if remaining > 0
        else 0
    )


def format_peso(amount) -> str:
    return f"₱{amount:,.0f}"


def format_duration(seconds) -> str:
    seconds = int(seconds)

    hrs, rem = divmod(
        seconds,
        3600,
    )

    mins, secs = divmod(
        rem,
        60,
    )

    parts = []

    if hrs:
        parts.append(
            f"{hrs}h"
        )

    if mins:
        parts.append(
            f"{mins}m"
        )

    if secs and not hrs:
        parts.append(
            f"{secs}s"
        )

    return " ".join(parts) or "0s"


def get_inventory_qty(
    user_id: str,
    item: str,
) -> int:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT qty
        FROM inventory
        WHERE user_id = ?
        AND item = ?
        """,
        (
            user_id,
            item,
        ),
    ).fetchone()

    conn.close()

    return (
        row["qty"]
        if row
        else 0
    )


def get_avg_buy_price(
    user_id: str,
    item: str,
) -> int:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT avg_buy_price
        FROM inventory
        WHERE user_id = ?
        AND item = ?
        """,
        (
            user_id,
            item,
        ),
    ).fetchone()

    conn.close()

    return (
        row["avg_buy_price"]
        if row
        else 0
    )


def add_inventory(
    user_id: str,
    item: str,
    delta: int,
    buy_price: int | None = None,
) -> int:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT
            qty,
            avg_buy_price
        FROM inventory
        WHERE user_id = ?
        AND item = ?
        """,
        (
            user_id,
            item,
        ),
    ).fetchone()

    current_qty = (
        row["qty"]
        if row
        else 0
    )

    current_avg = (
        row["avg_buy_price"]
        if row
        else 0
    )

    new_qty = max(
        0,
        current_qty + delta,
    )

    new_avg = current_avg

    if (
        delta > 0
        and buy_price is not None
        and new_qty > 0
    ):
        total_cost = (
            current_qty * current_avg
        ) + (
            delta * buy_price
        )

        new_avg = round(
            total_cost / new_qty
        )

    if new_qty == 0:
        new_avg = 0

    conn.execute(
        """
        INSERT INTO inventory (
            user_id,
            item,
            qty,
            avg_buy_price
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id, item)
        DO UPDATE SET
            qty = excluded.qty,
            avg_buy_price = excluded.avg_buy_price
        """,
        (
            user_id,
            item,
            new_qty,
            new_avg,
        ),
    )

    conn.commit()
    conn.close()

    return new_qty
