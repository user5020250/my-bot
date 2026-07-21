import random

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    lottery_group = app_commands.Group(
        name="lottery",
        description="Lottery commands.",
    )

    create_group = app_commands.Group(
        name="create",
        description="Create commands.",
    )

    @create_group.command(
        name="lottery",
        description="Create a lottery.",
    )
    @app_commands.describe(
        prize="Lottery prize (500k, 1m, 2b)",
    )
    async def create_lottery(
        self,
        interaction: discord.Interaction,
        prize: str,
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Owner only.",
                ephemeral=True,
            )
            return

        try:
            prize = db.parse_money(prize)

        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid amount.\n"
                "Examples: `500k`, `2m`, `1b`.",
                ephemeral=True,
            )
            return

        current = db.get_lottery()

        if current is not None:
            await interaction.response.send_message(
                "❌ There is already an active lottery.",
                ephemeral=True,
            )
            return

        db.create_lottery(prize)

        embed = discord.Embed(
            title="🎟️ Lottery Created",
            description=(
                f"Prize: **{db.format_peso(prize)}**\n\n"
                f"Players can now join using lottery tickets."
            ),
            color=WHITE,
        )

        await interaction.response.send_message(
            embed=embed
        )

    @lottery_group.command(
        name="draw",
        description="Draw the lottery.",
    )
    async def draw_lottery(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ Owner only.",
                ephemeral=True,
            )
            return

        lottery = db.get_lottery()

        if lottery is None:
            await interaction.response.send_message(
                "❌ No active lottery.",
                ephemeral=True,
            )
            return

        entries = db.get_lottery_entries()

        if not entries:
            db.end_lottery()

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
            lottery["prize"],
        )

        db.end_lottery()

        embed = discord.Embed(
            title="🎉 Lottery Winner",
            color=WHITE,
        )

        embed.add_field(
            name="Winner",
            value=f"<@{winner_id}>",
            inline=False,
        )

        embed.add_field(
            name="Prize",
            value=db.format_peso(
                lottery["prize"]
            ),
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    cog = Lottery(bot)

    await bot.add_cog(cog)

    try:
        bot.tree.add_command(
            cog.create_group
        )
    except app_commands.CommandAlreadyRegistered:
        pass

    try:
        bot.tree.add_command(
            cog.lottery_group
        )
    except app_commands.CommandAlreadyRegistered:
        pass
