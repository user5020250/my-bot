import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn
from jobs_data import JOBS

WHITE = discord.Color(0xFFFFFF)


def get_protected_until(user_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        """
        SELECT protected_until
        FROM business_status
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return row["protected_until"] if row else 0


def get_business_summary(user_id: str):
    conn = get_conn()

    rows = conn.execute(
        """
        SELECT business_key, level, lifetime_earnings, broken
        FROM owned_businesses
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    count = len(rows)
    broken_count = sum(1 for r in rows if r["broken"])
    total_lifetime = sum(r["lifetime_earnings"] for r in rows)

    return count, broken_count, total_lifetime


def get_loan_summary(user_id: str):
    conn = get_conn()

    borrowed = conn.execute(
        """
        SELECT COALESCE(SUM(remaining), 0) AS total
        FROM loans
        WHERE borrower = ?
        AND status = 'active'
        """,
        (user_id,),
    ).fetchone()

    lent = conn.execute(
        """
        SELECT COALESCE(SUM(remaining), 0) AS total
        FROM loans
        WHERE lender = ?
        AND status = 'active'
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return borrowed["total"], lent["total"]


def get_inventory_item_count(user_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        """
        SELECT COUNT(*) AS count
        FROM inventory
        WHERE user_id = ?
        AND qty > 0
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return row["count"] if row else 0


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

        embed = discord.Embed(
            title=f"👤 {member.display_name}'s Profile",
            color=WHITE,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="💰 Balance",
            value=f"`{db.format_peso(user['balance'])}`",
            inline=True,
        )

        current_job = user["job"]

        if current_job and current_job in JOBS:
            job_label = JOBS[current_job]["label"]
        else:
            job_label = "Unemployed"

        embed.add_field(
            name="👔 Job",
            value=f"`{job_label}`",
            inline=True,
        )

        now = int(time.time())
        protected_until = get_protected_until(user_id)

        if protected_until > now:
            embed.add_field(
                name="🔒 Padlock",
                value=f"`{db.format_duration(protected_until - now)}` remaining",
                inline=True,
            )

        business_count, broken_count, business_lifetime = get_business_summary(user_id)

        business_value = f"`{business_count}` owned"

        if broken_count > 0:
            business_value += f" (`{broken_count}` need repair)"

        embed.add_field(
            name="💼 Businesses",
            value=business_value,
            inline=True,
        )

        if business_count > 0:
            embed.add_field(
                name="📈 Business Lifetime Earnings",
                value=f"`{db.format_peso(business_lifetime)}`",
                inline=True,
            )

        borrowed_total, lent_total = get_loan_summary(user_id)

        if borrowed_total > 0:
            embed.add_field(
                name="📤 Owed by You",
                value=f"`{db.format_peso(borrowed_total)}`",
                inline=True,
            )

        if lent_total > 0:
            embed.add_field(
                name="📥 Owed to You",
                value=f"`{db.format_peso(lent_total)}`",
                inline=True,
            )

        item_count = get_inventory_item_count(user_id)

        embed.add_field(
            name="🎒 Inventory",
            value=f"`{item_count}` item type(s)",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Profile(bot)
    )
