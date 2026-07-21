import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

WORK_COOLDOWN_SECONDS = TRABAHO_COOLDOWN_SECONDS
ALLOWANCE_COOLDOWN_SECONDS = 24 * 60 * 60

JOB_CHOICES = [
    app_commands.Choice(name=info["label"], value=key)
    for key, info in JOBS.items()
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /jobs

    @app_commands.command(
        name="jobs",
        description="Check all available jobs.",
    )
    async def jobs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Job Menu",
            description="Choose a job with `/work job:[job]`.",
            color=WHITE,
        )

        for info in JOBS.values():
            embed.add_field(
                name=info["label"],
                value=(
                    f"{db.format_peso(info['min'])} – "
                    f"{db.format_peso(info['max'])}\n"
                    f"*{info['flavor']}*"
                ),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )

    # ----------------------------------------------------------------- /work

    @app_commands.command(
        name="work",
        description="Choose a job or work your shift.",
    )
    @app_commands.describe(
        job="Pick a job."
    )
    @app_commands.choices(
        job=JOB_CHOICES
    )
    async def work(
        self,
        interaction: discord.Interaction,
        job: app_commands.Choice[str] = None,
    ):
        user_id = str(
            interaction.user.id
        )

        user = db.get_user(
            user_id
        )

        if job is not None:
            db.set_job(
                user_id,
                job.value,
            )

            info = JOBS[
                job.value
            ]

            await interaction.response.send_message(
                f"You are now a "
                f"**{info['label']}**.\n"
                f"Use `/work` to work."
            )
            return

        current_job = user["job"]

        if (
            not current_job
            or current_job not in JOBS
        ):
            await interaction.response.send_message(
                "You don't have a job.\n"
                "Use `/work job:[job]`."
            )
            return

        remaining = db.check_cooldown(
            user_id,
            "last_trabaho",
            WORK_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Try again in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        info = JOBS[
            current_job
        ]

        earnings = random.randint(
            info["min"],
            info["max"],
        )

        new_balance = db.add_balance(
            user_id,
            earnings,
        )

        db.set_cooldown(
            user_id,
            "last_trabaho",
            int(time.time()),
        )

        embed = discord.Embed(
            title="Shift Complete",
            description=(
                f"You worked as a "
                f"**{info['label']}**.\n\n"
                f"Earned "
                f"**{db.format_peso(earnings)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                f"Balance: "
                f"{db.format_peso(new_balance)}"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -------------------------------------------------------------- /scatter

@app_commands.command(
    name="scatter",
    description="50/50 gamble.",
)
@app_commands.describe(
    amount="Examples: 100k, 5m, 2b"
)
async def scatter(
    self,
    interaction: discord.Interaction,
    amount: str,
):
    user_id = str(
        interaction.user.id
    )

    try:
        amount = db.parse_money(
            amount
        )

    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid amount.\n"
            "Examples: `100k`, `5m`, `2b`",
            ephemeral=True,
        )
        return

    if amount <= 0:
        await interaction.response.send_message(
            "❌ Invalid amount.",
            ephemeral=True,
        )
        return

    user = db.get_user(
        user_id
    )

    if amount > user["balance"]:
        await interaction.response.send_message(
            f"You only have "
            f"**{db.format_peso(user['balance'])}**."
        )
        return

    win = random.random() < 0.5

    if win:
        new_balance = db.add_balance(
            user_id,
            amount,
        )

        embed = discord.Embed(
            title="🎉 You Won",
            description=(
                f"You won "
                f"**{db.format_peso(amount)}**."
            ),
            color=WHITE,
        )

    else:
        new_balance = db.add_balance(
            user_id,
            -amount,
        )

        embed = discord.Embed(
            title="💀 You Lost",
            description=(
                f"You lost "
                f"**{db.format_peso(amount)}**."
            ),
            color=WHITE,
        )

    embed.set_footer(
        text=(
            f"Balance: "
            f"{db.format_peso(new_balance)}"
        )
    )

    await interaction.response.send_message(
        embed=embed
    )
    # ------------------------------------------------------------- /allowance

    @app_commands.command(
        name="allowance",
        description="Claim your daily allowance.",
    )
    async def allowance(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(
            interaction.user.id
        )

        remaining = db.check_cooldown(
            user_id,
            "last_baon",
            ALLOWANCE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Come back in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        amount = random.randint(
            50,
            100,
        )

        new_balance = db.add_balance(
            user_id,
            amount,
        )

        db.set_cooldown(
            user_id,
            "last_baon",
            int(time.time()),
        )

        embed = discord.Embed(
            title="Allowance Claimed",
            description=(
                f"You received "
                f"**{db.format_peso(amount)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                f"Balance: "
                f"{db.format_peso(new_balance)}"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Economy(bot)
    )
