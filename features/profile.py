import discord

from discord import app_commands
from discord.ext import commands

import db_utils as db
from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS

WHITE = discord.Color(0xFFFFFF)

TAMBAY_COOLDOWN_SECONDS = 60
BAON_COOLDOWN_SECONDS = 24 * 60 * 60


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="View a profile.",
    )
    @app_commands.describe(
        user="Leave blank to view yourself."
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        target = user or interaction.user

        data = db.get_user(str(target.id))

        job_key = data["job"]

        job_label = (
            JOBS[job_key]["label"]
            if job_key in JOBS
            else "Unemployed"
        )

        trabaho_cd = db.check_cooldown(
            str(target.id),
            "last_trabaho",
            TRABAHO_COOLDOWN_SECONDS,
        )

        tambay_cd = db.check_cooldown(
            str(target.id),
            "last_tambay",
            TAMBAY_COOLDOWN_SECONDS,
        )

        baon_cd = db.check_cooldown(
            str(target.id),
            "last_baon",
            BAON_COOLDOWN_SECONDS,
        )

        embed = discord.Embed(
            title=f"{target.display_name}'s Profile",
            color=WHITE,
        )

        embed.set_thumbnail(
            url=target.display_avatar.url
        )

        embed.add_field(
            name="Balance",
            value=db.format_peso(data["balance"]),
            inline=True,
        )

        embed.add_field(
            name="Job",
            value=job_label,
            inline=True,
        )

        embed.add_field(
            name="\u200b",
            value="\u200b",
            inline=True,
        )

        embed.add_field(
            name="Trabaho",
            value=(
                "Ready"
                if trabaho_cd == 0
                else db.format_duration(trabaho_cd)
            ),
            inline=True,
        )

        embed.add_field(
            name="Tambay",
            value=(
                "Ready"
                if tambay_cd == 0
                else db.format_duration(tambay_cd)
            ),
            inline=True,
        )

        embed.add_field(
            name="Baon",
            value=(
                "Ready"
                if baon_cd == 0
                else db.format_duration(baon_cd)
            ),
            inline=True,
        )

        embed.set_footer(
            text="Keep grinding."
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Profile(bot))
