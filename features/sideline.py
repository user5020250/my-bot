import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

SIDELINE_COOLDOWN_SECONDS = 60

SIDELINE_COOLDOWN_FIELDS = (
    "last_sideline",
)


def ensure_sideline_columns():
    conn = get_conn()

    existing_cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)")
    }

    for field in SIDELINE_COOLDOWN_FIELDS:
        if field not in existing_cols:
            conn.execute(
                f"ALTER TABLE users ADD COLUMN {field} INTEGER NOT NULL DEFAULT 0"
            )

    conn.commit()
    conn.close()


class Sideline(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_sideline_columns()

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        # Without this, an unhandled exception here means Discord
        # never gets a response and shows "The application did not
        # respond" instead of a real error message.
        print(f"[sideline] command error: {error!r}")

        message = "⚠️ Something went wrong. Please try again later."

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # -------------------------------------------------------- /sideline

    @app_commands.command(
        name="sideline",
        description="Do a random side hustle.",
    )
    async def sideline(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_sideline",
            SIDELINE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ You already worked your sideline.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_sideline",
            int(time.time()),
        )

        jobs = [
            ("🛵 You delivered food orders.", 150, 400),
            ("🧼 You washed motorcycles.", 100, 300),
            ("🍿 You sold snacks outside school.", 120, 350),
            ("🏪 You worked at a sari-sari store.", 150, 350),
            ("🧱 You helped a construction worker.", 250, 600),
            ("🐟 You sold fish at the market.", 200, 500),
            ("🌾 You carried sacks of rice.", 250, 700),
        ]

        message, minimum, maximum = random.choice(jobs)

        earnings = random.randint(
            minimum,
            maximum,
        )

        new_balance = db.add_balance(
            user_id,
            earnings,
        )

        embed = discord.Embed(
            title="💼 Sideline",
            description=(
                f"{message}\n\n"
                f"You earned **{db.format_peso(earnings)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Sideline(bot)
    )
