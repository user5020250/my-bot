"""
db_utils.py

Common helper functions for the economy database.
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
    "last_daily",
    "last_weekly",
    "last_monthly",
    "last_yearly",
}

# ==========================================================
# LOTTERY
# ==========================================================

def create_lottery(
    prize: int,
    ends_at: int,
) -> None:

    conn = get_conn()

    conn.execute(
        """
        DELETE FROM lottery
        """
    )

    conn.execute(
        """
        DELETE FROM lottery_entries
        """
    )

    conn.execute(
        """
        INSERT INTO lottery (
            id,
            prize,
            ends_at,
            active
        )
        VALUES (
            1,
            ?,
            ?,
            1
        )
        """,
        (
            prize,
            ends_at,
        ),
    )

    conn.commit()
    conn.close()


def get_lottery() -> dict | None:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM lottery
        WHERE active = 1
        LIMIT 1
        """
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return dict(row)


def end_lottery() -> None:

    conn = get_conn()

    conn.execute(
        """
        UPDATE lottery
        SET active = 0
        WHERE id = 1
        """
    )

    conn.execute(
        """
        DELETE FROM lottery_entries
        """
    )

    conn.commit()
    conn.close()


def clear_lottery_entries() -> None:

    conn = get_conn()

    conn.execute(
        """
        DELETE FROM lottery_entries
        """
    )

    conn.commit()
    conn.close()


def join_lottery(
    user_id: str,
    tickets: int = 1,
) -> bool:

    lottery = get_lottery()

    if lottery is None:
        return False

    if tickets <= 0:
        return False

    if not has_item(
        user_id,
        "lottery_ticket",
        tickets,
    ):
        return False

    conn = get_conn()

    row = conn.execute(
        """
        SELECT tickets
        FROM lottery_entries
        WHERE user_id = ?
        """,
        (
            user_id,
        ),
    ).fetchone()

    current_tickets = 0

    if row:
        current_tickets = row["tickets"]

    new_total = current_tickets + tickets

    conn.execute(
        """
        INSERT INTO lottery_entries (
            user_id,
            tickets
        )
        VALUES (?, ?)

        ON CONFLICT(user_id)

        DO UPDATE SET
            tickets = excluded.tickets
        """,
        (
            user_id,
            new_total,
        ),
    )

    conn.commit()
    conn.close()

    remove_inventory(
        user_id,
        "lottery_ticket",
        tickets,
    )

    return True


def get_lottery_entries() -> list[dict]:

    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM lottery_entries
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def set_lottery_channel(
    guild_id: str,
    channel_id: str,
) -> None:

    conn = get_conn()

    conn.execute(
        """
        INSERT INTO lottery_channels (
            guild_id,
            channel_id
        )
        VALUES (?, ?)

        ON CONFLICT(guild_id)

        DO UPDATE SET
            channel_id = excluded.channel_id
        """,
        (
            guild_id,
            channel_id,
        ),
    )

    conn.commit()
    conn.close()


def get_lottery_channel(
    guild_id: str,
) -> str | None:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT channel_id
        FROM lottery_channels
        WHERE guild_id = ?
        """,
        (
            guild_id,
        ),
    ).fetchone()

    conn.close()

    if row is None:
        return None

    return row["channel_id"]


def get_all_lottery_channels() -> list[dict]:

    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM lottery_channels
        """
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]
    
# ==========================================================
# USERS
# ==========================================================

def get_user(
    user_id: str,
) -> dict:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (
            user_id,
        ),
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
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,
            (
                user_id,
            ),
        ).fetchone()

    conn.close()

    return dict(row)


def set_balance(
    user_id: str,
    amount: int,
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
    delta: int,
) -> int:

    user = get_user(
        user_id,
    )

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


# ==========================================================
# COOLDOWNS
# ==========================================================

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

    user = get_user(
        user_id,
    )

    last_used = user.get(
        field,
        0,
    ) or 0

    now = int(
        time.time(),
    )

    remaining = cooldown_seconds - (
        now - last_used
    )

    return max(
        0,
        remaining,
    )


# ==========================================================
# INVENTORY
# ==========================================================

def get_inventory(
    user_id: str,
    item: str,
) -> dict:

    conn = get_conn()

    row = conn.execute(
        """
        SELECT *
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

    if row is None:
        return {
            "user_id": user_id,
            "item": item,
            "qty": 0,
            "avg_buy_price": 0,
        }

    return dict(row)


def get_inventory_qty(
    user_id: str,
    item: str,
) -> int:

    inventory = get_inventory(
        user_id,
        item,
    )

    return inventory["qty"]


def get_all_inventory(
    user_id: str,
) -> list[dict]:

    conn = get_conn()

    rows = conn.execute(
        """
        SELECT *
        FROM inventory
        WHERE user_id = ?
        AND qty > 0
        ORDER BY qty DESC, item ASC
        """,
        (
            user_id,
        ),
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def has_item(
    user_id: str,
    item: str,
    amount: int = 1,
) -> bool:

    return (
        get_inventory_qty(
            user_id,
            item,
        )
        >= amount
    )


def add_inventory(
    user_id: str,
    item: str,
    delta: int,
    buy_price: int | None = None,
) -> int:

    inventory = get_inventory(
        user_id,
        item,
    )

    current_qty = inventory[
        "qty"
    ]

    current_avg = inventory[
        "avg_buy_price"
    ]

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
            + delta * buy_price
        )

        new_avg = round(
            total_cost / new_qty
        )

    if new_qty == 0:
        new_avg = 0

    conn = get_conn()

    conn.execute(
        """
        INSERT INTO inventory (
            user_id,
            item,
            qty,
            avg_buy_price
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT (
            user_id,
            item
        )

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


def remove_inventory(
    user_id: str,
    item: str,
    amount: int = 1,
) -> bool:

    current_qty = get_inventory_qty(
        user_id,
        item,
    )

    if current_qty < amount:
        return False

    add_inventory(
        user_id,
        item,
        -amount,
    )

    return True

# ==========================================================
# MONEY PARSER
# ==========================================================

def parse_money(
    text: str,
) -> int:

    text = text.lower().strip()

    multipliers = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
        "t": 1_000_000_000_000,
    }

    try:
        suffix = text[-1]

        if suffix in multipliers:

            number = float(
                text[:-1]
            )

            return int(
                number * multipliers[suffix]
            )

        return int(text)

    except (
        ValueError,
        IndexError,
    ):
        raise ValueError(
            "Invalid amount."
        )

# ==========================================================
# FORMATTING
# ==========================================================

def format_peso(
    amount: int,
) -> str:

    return f"₱{amount:,.0f}"


def format_duration(
    seconds: int,
) -> str:

    seconds = int(
        seconds,
    )

    days, seconds = divmod(
        seconds,
        86400,
    )

    hours, seconds = divmod(
        seconds,
        3600,
    )

    minutes, seconds = divmod(
        seconds,
        60,
    )

    parts = []

    if days:
        parts.append(
            f"{days}d"
        )

    if hours:
        parts.append(
            f"{hours}h"
        )

    if minutes:
        parts.append(
            f"{minutes}m"
        )

    if (
        seconds
        and days == 0
        and hours == 0
    ):
        parts.append(
            f"{seconds}s"
        )

    return (
        " ".join(parts)
        or "0s"
    )
