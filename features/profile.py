import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn
from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS

from features.shop import SHOP_ITEMS
from features.business import BUSINESSES, SELL_RETURN_RATE
from features.economy import ALLOWANCE_COOLDOWN_SECONDS
from features.rewards import (
    DAILY_COOLDOWN_SECONDS,
    WEEKLY_COOLDOWN_SECONDS,
    MONTHLY_COOLDOWN_SECONDS,
    YEARLY_COOLDOWN_SECONDS,
)
from features.sideline import (
    SIDELINE_COOLDOWN_SECONDS,
    FISH_COOLDOWN_SECONDS,
    MINE_COOLDOWN_SECONDS,
    FARM_COOLDOWN_SECONDS,
    HUNT_COOLDOWN_SECONDS,
    COOK_COOLDOWN_SECONDS,
)

WHITE = discord.Color(0xFFFFFF)

# Confirmed against db_utils.py (last_karaoke is an allowed cooldown
# field) and help.py's listed "Cooldown: 1 minute" for /karaoke.
KARAOKE_COOLDOWN_FIELD = "last_karaoke"
KARAOKE_COOLDOWN_SECONDS = 60

WORK_COOLDOWN_FIELD = "last_trabaho"
ALLOWANCE_COOLDOWN_FIELD = "last_baon"


def fmt_cooldown(user_id: str, field: str, duration: int) -> str:
    try:
        remaining = db.check_cooldown(user_id, field, duration)
    except Exception:
        return "Unknown"

    if remaining <= 0:
        return "Ready"

    return db.format_duration(remaining)


def get_protected_until(user_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        "SELECT protected_until FROM business_status WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row["protected_until"] if row else 0


def get_inventory_stats(user_id: str):
    rows = db.get_all_inventory(user_id)

    unique = len(rows)
    total = sum(row["qty"] for row in rows)

    value = 0

    for row in rows:
        info = SHOP_ITEMS.get(row["item"])

        if info is None:
            continue

        sell_price = info.get("sell_price", info.get("cost", 0) // 2)
        value += sell_price * row["qty"]

    return unique, total, value


def get_business_rows(user_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT business_key, level, lifetime_earnings, broken, repair_cost
        FROM owned_businesses
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    return rows


def get_business_stats(user_id: str):
    rows = get_business_rows(user_id)

    count = len(rows)
    broken_count = sum(1 for r in rows if r["broken"])
    lifetime_total = sum(r["lifetime_earnings"] for r in rows)

    resale_value = 0

    for row in rows:
        info = BUSINESSES.get(row["business_key"])

        if info is None:
            continue

        value = round(info["price"] * SELL_RETURN_RATE * row["level"])

        if row["broken"]:
            value = max(0, value - row["repair_cost"])

        resale_value += value

    return count, broken_count, lifetime_total, resale_value


def get_loan_stats(user_id: str):
    conn = get_conn()

    borrowed_rows = conn.execute(
        """
        SELECT id, remaining, due_date, overdue_count
        FROM loans
        WHERE borrower = ? AND status = 'active'
        """,
        (user_id,),
    ).fetchall()

    lent_rows = conn.execute(
        """
        SELECT id, remaining
        FROM loans
        WHERE lender = ? AND status = 'active'
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    owed_by_you = sum(r["remaining"] for r in borrowed_rows)
    owed_to_you = sum(r["remaining"] for r in lent_rows)
    overdue_count = sum(1 for r in borrowed_rows if r["overdue_count"] > 0)

    return owed_by_you, owed_to_you, len(borrowed_rows), len(lent_rows), overdue_count


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="View a player's profile.",
    )
    @app_commands.describe(
        member="Whose profile to view (defaults to you)",
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user
        user_id = str(member.id)

        user = db.get_user(user_id)
        balance = user["balance"]

        unique_items, total_items, inventory_value = get_inventory_stats(user_id)
        biz_count, biz_broken, biz_lifetime, biz_resale = get_business_stats(user_id)
        owed_by_you, owed_to_you, borrowed_count, lent_count, overdue_count = get_loan_stats(user_id)

        net_worth = balance + inventory_value + biz_resale - owed_by_you

        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Profile",
            color=WHITE,
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        # ---------------- Money ----------------
        embed.add_field(
            name="💰 Money",
            value=(
                f"Wallet: `{db.format_peso(balance)}`\n"
                f"Net Worth:\n`{db.format_peso(net_worth)}`"
            ),
            inline=True,
        )

        # ---------------- Job ----------------
        current_job = user["job"]

        if current_job and current_job in JOBS:
            job_info = JOBS[current_job]
            job_range = f"`{db.format_peso(job_info['min'])} - {db.format_peso(job_info['max'])}`"
        else:
            job_info = None
            job_range = "`Unemployed`"

        embed.add_field(
            name="💼 Job",
            value=(
                f"Current: `{job_info['label'] if job_info else 'None'}`\n"
                f"{job_range}"
            ),
            inline=True,
        )

        # ---------------- Inventory ----------------
        embed.add_field(
            name="🎒 Inventory",
            value=(
                f"Unique: `{unique_items}`\n"
                f"Total: `{total_items}`\n"
                f"Value: `{db.format_peso(inventory_value)}`"
            ),
            inline=True,
        )

        # ---------------- Cooldowns ----------------
        embed.add_field(
            name="⚡ Cooldowns",
            value=(
                f"Work: `{fmt_cooldown(user_id, WORK_COOLDOWN_FIELD, TRABAHO_COOLDOWN_SECONDS)}`\n"
                f"Allowance: `{fmt_cooldown(user_id, ALLOWANCE_COOLDOWN_FIELD, ALLOWANCE_COOLDOWN_SECONDS)}`\n"
                f"Daily: `{fmt_cooldown(user_id, 'last_daily', DAILY_COOLDOWN_SECONDS)}`\n"
                f"Weekly: `{fmt_cooldown(user_id, 'last_weekly', WEEKLY_COOLDOWN_SECONDS)}`\n"
                f"Monthly: `{fmt_cooldown(user_id, 'last_monthly', MONTHLY_COOLDOWN_SECONDS)}`\n"
                f"Yearly: `{fmt_cooldown(user_id, 'last_yearly', YEARLY_COOLDOWN_SECONDS)}`"
            ),
            inline=True,
        )

        # ---------------- Activities ----------------
        embed.add_field(
            name="🎮 Activities",
            value=(
                f"Karaoke: `{fmt_cooldown(user_id, KARAOKE_COOLDOWN_FIELD, KARAOKE_COOLDOWN_SECONDS)}`\n"
                f"Sideline: `{fmt_cooldown(user_id, 'last_sideline', SIDELINE_COOLDOWN_SECONDS)}`\n"
                f"Fish: `{fmt_cooldown(user_id, 'last_fish', FISH_COOLDOWN_SECONDS)}`\n"
                f"Mine: `{fmt_cooldown(user_id, 'last_mine', MINE_COOLDOWN_SECONDS)}`\n"
                f"Farm: `{fmt_cooldown(user_id, 'last_farm', FARM_COOLDOWN_SECONDS)}`\n"
                f"Hunt: `{fmt_cooldown(user_id, 'last_hunt', HUNT_COOLDOWN_SECONDS)}`\n"
                f"Cook: `{fmt_cooldown(user_id, 'last_cook', COOK_COOLDOWN_SECONDS)}`"
            ),
            inline=True,
        )

        # ---------------- Businesses ----------------
        now = int(time.time())
        protected_until = get_protected_until(user_id)

        business_lines = [
            f"Owned: `{biz_count}`",
            f"Lifetime Income: `{db.format_peso(biz_lifetime)}`",
        ]

        if biz_broken > 0:
            business_lines.append(f"⚠️ Needs Repair: `{biz_broken}`")

        if protected_until > now:
            business_lines.append(
                f"🛡️ Defended: `{db.format_duration(protected_until - now)}`"
            )

        embed.add_field(
            name="🏪 Businesses",
            value="\n".join(business_lines),
            inline=True,
        )

        # ---------------- Loans ----------------
        loan_lines = [
            f"You Owe: `{db.format_peso(owed_by_you)}` (`{borrowed_count}`)",
            f"Owed to You: `{db.format_peso(owed_to_you)}` (`{lent_count}`)",
        ]

        if overdue_count > 0:
            loan_lines.append(f"⚠️ Overdue: `{overdue_count}`")

        embed.add_field(
            name="🏦 Loans",
            value="\n".join(loan_lines),
            inline=True,
        )

        # ---------------- Information ----------------
        embed.add_field(
            name="📋 Information",
            value=f"User ID:\n`{member.id}`",
            inline=True,
        )

        embed.set_footer(text="Keep grinding 💸")

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Profile(bot)
    )
