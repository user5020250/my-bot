import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

# Reusing the "last_budol" cooldown column that already exists on the
# users table (it used to back /scam). Rename via a migration later if
# you want the column name to match /steal instead.
STEAL_COOLDOWN_SECONDS = 24 * 60 * 60

STEAL_MIN_PERCENT = 0.20
STEAL_MAX_PERCENT = 0.60

# Don't let people bother stealing from someone who has next to nothing.
STEAL_MIN_TARGET_BALANCE = 1000


def get_protected_until(user_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        "SELECT protected_until FROM business_status WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row["protected_until"] if row else 0


class Steal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="steal",
        description="Attempt to steal money from another player.",
    )
    @app_commands.describe(target="Who to steal from")
    async def steal(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        thief_id = str(interaction.user.id)
        target_id = str(target.id)

        if target_id == thief_id:
            await interaction.response.send_message(
                "🚫 You can't steal from yourself."
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "🤖 Bots can't be robbed."
            )
            return

        remaining = db.check_cooldown(
            thief_id,
            "last_budol",
            STEAL_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"🕒 You need to lay low. "
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        protected_until = get_protected_until(target_id)
        now = int(time.time())

        if protected_until > now:
            await interaction.response.send_message(
                f"🔒 {target.mention} is protected by a padlock for another "
                f"**{db.format_duration(protected_until - now)}**."
            )
            return

        target_user = db.get_user(target_id)

        if target_user["balance"] < STEAL_MIN_TARGET_BALANCE:
            await interaction.response.send_message(
                f"💸 {target.mention} barely has any money. Not worth the risk."
            )
            return

        # Cooldown only gets set once we know the attempt actually goes through.
        db.set_cooldown(
            thief_id,
            "last_budol",
            now,
        )

        stolen = round(
            target_user["balance"]
            * random.uniform(STEAL_MIN_PERCENT, STEAL_MAX_PERCENT)
        )

        db.add_balance(target_id, -stolen)
        new_balance = db.add_balance(thief_id, stolen)

        embed = discord.Embed(
            title="🥷 Robbery Success",
            description=(
                f"You stole **{db.format_peso(stolen)}** from {target.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Steal(bot))
