import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


def ensure_lottery_table():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lotteries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prize INTEGER NOT NULL,
            ends_at INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lottery_entries (
            user_id TEXT PRIMARY KEY,
            tickets INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    conn.commit()
    conn.close()


class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        ensure_lottery_table()

    lottery_group = app_commands.Group(
        name="lottery",
        description="Lottery commands."
    )

    create_group = app_commands.Group(
        name="create",
        description="Create commands."
    )

    @create_group.command(
        name="lottery",
        description="Create a lottery."
    )
    @app_commands.describe(
        prize="Lottery prize",
        hours="How many hours before it ends"
    )
    async def create_lottery(
        self,
        interaction: discord.Interaction,
        prize: int,
        hours: int,
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Owner only.",
                ephemeral=True
            )
            return

        conn = get_conn()

        existing = conn.execute(
            """
            SELECT *
            FROM lotteries
            WHERE active = 1
            """
        ).fetchone()

        if existing:
            conn.close()

            await interaction.response.send_message(
                "❌ There is already an active lottery.",
                ephemeral=True
            )
            return

        ends_at = int(time.time()) + (hours * 3600)

        cursor = conn.execute(
            """
            INSERT INTO lotteries (
                prize,
                ends_at,
                active
            )
            VALUES (?, ?, 1)
            """,
            (
                prize,
                ends_at,
            ),
        )

        lottery_id = cursor.lastrowid

        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🎟️ Lottery Created",
            description=(
                f"Lottery ID: `{lottery_id}`\n"
                f"Prize: **{db.format_peso(prize)}**\n"
                f"Ends: <t:{ends_at}:R>"
            ),
            color=WHITE,
        )

        await interaction.response.send_message(
            embed=embed
        )

    @lottery_group.command(
        name="draw",
        description="Draw the lottery."
    )
    async def draw_lottery(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Owner only.",
                ephemeral=True
            )
            return

        conn = get_conn()

        lottery = conn.execute(
            """
            SELECT *
            FROM lotteries
            WHERE active = 1
            """
        ).fetchone()

        if lottery is None:
            conn.close()

            await interaction.response.send_message(
                "❌ No active lottery.",
                ephemeral=True
            )
            return

        if lottery["ends_at"] > int(time.time()):
            conn.close()

            await interaction.response.send_message(
                f"⏳ Lottery ends <t:{lottery['ends_at']}:R>.",
                ephemeral=True
            )
            return

        entries = db.get_lottery_entries()

        if not entries:
            conn.execute(
                """
                UPDATE lotteries
                SET active = 0
                WHERE id = ?
                """,
                (lottery["id"],)
            )

            conn.commit()
            conn.close()

            await interaction.response.send_message(
                "❌ Nobody joined the lottery."
            )
            return

        pool = []

        for entry in entries:
            pool.extend(
                [entry["user_id"]] * entry["tickets"]
            )

        winner_id = random.choice(pool)

        db.add_balance(
            winner_id,
            lottery["prize"]
        )

        db.clear_lottery_entries()

        conn.execute(
            """
            UPDATE lotteries
            SET active = 0
            WHERE id = ?
            """,
            (lottery["id"],)
        )

        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🎉 Lottery Winner",
            color=WHITE
        )

        embed.add_field(
            name="Winner",
            value=f"<@{winner_id}>",
            inline=False
        )

        embed.add_field(
            name="Prize",
            value=db.format_peso(
                lottery["prize"]
            ),
            inline=False
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    cog = Lottery(bot)

    await bot.add_cog(cog)

    try:
        bot.tree.add_command(cog.create_group)
    except app_commands.CommandAlreadyRegistered:
        pass

    try:
        bot.tree.add_command(cog.lottery_group)
    except app_commands.CommandAlreadyRegistered:
        pass
