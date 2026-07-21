import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

KARAOKE_COOLDOWN_SECONDS = 60

KARAOKE_MIN_REWARD = 100
KARAOKE_MAX_REWARD = 1000


class Karaoke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="karaoke",
        description="Sing karaoke to earn some money.",
    )
    async def karaoke(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_karaoke",
            KARAOKE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"🎤 The mic needs a rest.\n"
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_karaoke",
            int(time.time()),
        )

        reward = random.randint(
            KARAOKE_MIN_REWARD,
            KARAOKE_MAX_REWARD,
        )

        new_balance = db.add_balance(
            user_id,
            reward,
        )

        songs = [
            "Narda",
            "Buwan",
            "Torete",
            "Beer",
            "Huling El Bimbo",
            "Pare Ko",
            "Uhaw",
            "With A Smile",
            "Kitchie Nadal Medley",
            "Harana",
        ]

        song = random.choice(songs)

        embed = discord.Embed(
            title="🎤 Karaoke Night",
            description=(
                f"You sang **{song}**.\n\n"
                f"You earned **{db.format_peso(reward)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(
        Karaoke(bot)
    )
