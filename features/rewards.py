import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

# ------------------------------------------------------------------
# These are flat "claim" rewards — separate from business income.
# Each one is a rolling cooldown (same pattern as /budol, /karaoke):
# claiming starts the timer, and you can claim again once that many
# seconds have passed, regardless of real-world calendar days.
# ------------------------------------------------------------------

DAILY_COOLDOWN_SECONDS = 1 * 24 * 60 * 60
WEEKLY_COOLDOWN_SECONDS = 7 * 24 * 60 * 60
MONTHLY_COOLDOWN_SECONDS = 30 * 24 * 60 * 60
YEARLY_COOLDOWN_SECONDS = 365 * 24 * 60 * 60

DAILY_MIN_AMOUNT = 200
DAILY_MAX_AMOUNT = 500

WEEKLY_MIN_AMOUNT = 2000
WEEKLY_MAX_AMOUNT = 4000

MONTHLY_MIN_AMOUNT = 10000
MONTHLY_MAX_AMOUNT = 20000

YEARLY_MIN_AMOUNT = 150000
YEARLY_MAX_AMOUNT = 300000


class Rewards(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /daily

    @app_commands.command(
        name="daily",
        description="Claim your daily allowance.",
    )
    async def daily(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_daily",
            DAILY_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nakuha mo na ang daily mo. "
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_daily",
            int(time.time()),
        )

        amount = random.randint(
            DAILY_MIN_AMOUNT,
            DAILY_MAX_AMOUNT,
        )

        new_balance = db.add_balance(
            user_id,
            amount,
        )

        embed = discord.Embed(
            title="Daily Allowance",
            description=(
                f"Nakakuha ka ng **{db.format_peso(amount)}** "
                f"na baon para ngayong araw."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /weekly

    @app_commands.command(
        name="weekly",
        description="Claim your weekly pay.",
    )
    async def weekly(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_weekly",
            WEEKLY_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nakuha mo na ang weekly mo. "
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_weekly",
            int(time.time()),
        )

        amount = random.randint(
            WEEKLY_MIN_AMOUNT,
            WEEKLY_MAX_AMOUNT,
        )

        new_balance = db.add_balance(
            user_id,
            amount,
        )

        embed = discord.Embed(
            title="Weekly Sahod",
            description=(
                f"Nakakuha ka ng **{db.format_peso(amount)}** "
                f"na weekly sahod."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /monthly

    @app_commands.command(
        name="monthly",
        description="Claim your monthly salary.",
    )
    async def monthly(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_monthly",
            MONTHLY_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nakuha mo na ang monthly mo. "
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_monthly",
            int(time.time()),
        )

        amount = random.randint(
            MONTHLY_MIN_AMOUNT,
            MONTHLY_MAX_AMOUNT,
        )

        new_balance = db.add_balance(
            user_id,
            amount,
        )

        embed = discord.Embed(
            title="Monthly Sweldo",
            description=(
                f"Nakakuha ka ng **{db.format_peso(amount)}** "
                f"na buwanang sweldo."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /yearly

    @app_commands.command(
        name="yearly",
        description="Claim your yearly bonus.",
    )
    async def yearly(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_yearly",
            YEARLY_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nakuha mo na ang yearly mo. "
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_yearly",
            int(time.time()),
        )

        amount = random.randint(
            YEARLY_MIN_AMOUNT,
            YEARLY_MAX_AMOUNT,
        )

        new_balance = db.add_balance(
            user_id,
            amount,
        )

        embed = discord.Embed(
            title="🎉 Yearly Bonus",
            description=(
                f"Nakakuha ka ng **{db.format_peso(amount)}** "
                f"na taunang bonus (parang 13th month pay)!"
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Rewards(bot)
    )
