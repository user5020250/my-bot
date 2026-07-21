import random

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

PRIZE = 1_000_000


class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="draw_lottery",
        description="Owner only.",
    )
    async def draw_lottery(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != YOUR_DISCORD_ID:
            await interaction.response.send_message(
                "❌ Owner only.",
                ephemeral=True,
            )
            return

        entries = db.get_lottery_entries()

        if not entries:

            await interaction.response.send_message(
                "❌ No lottery entries.",
                ephemeral=True,
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
            PRIZE,
        )

        db.clear_lottery_entries()

        embed = discord.Embed(
            title="🎉 Lottery Winner",
            color=WHITE,
        )

        embed.add_field(
            name="Winner ID",
            value=f"`{winner_id}`",
            inline=False,
        )

        embed.add_field(
            name="Prize",
            value=f"`{db.format_peso(PRIZE)}`",
            inline=False,
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(
        Lottery(bot)
    )
