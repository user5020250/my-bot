import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

TAMBAY_COOLDOWN_SECONDS = 60
BAON_COOLDOWN_SECONDS = 24 * 60 * 60

JOB_CHOICES = [
    app_commands.Choice(name=info["label"], value=key)
    for key, info in JOBS.items()
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /jobs
    @app_commands.command(name="jobs", description="Check all available jobs.")
    async def jobs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Trabaho Menu",
            description="Choose a job with `/trabaho job:[job]` and start the grind.",
            color=WHITE,
        )

        for info in JOBS.values():
            embed.add_field(
                name=info["label"],
                value=(
                    f"{db.format_peso(info['min'])} – "
                    f"{db.format_peso(info['max'])} per shift\n"
                    f"*{info['flavor']}*"
                ),
                inline=False,
            )

        embed.set_footer(text="30-minute cooldown • Secure the bag.")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /trabaho
    @app_commands.command(
        name="trabaho",
        description="Choose a job or work your current shift.",
    )
    @app_commands.describe(job="Pick a job.")
    @app_commands.choices(job=JOB_CHOICES)
    async def trabaho(
        self,
        interaction: discord.Interaction,
        job: app_commands.Choice[str] = None,
    ):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if job is not None:
            db.set_job(user_id, job.value)

            info = JOBS[job.value]

            await interaction.response.send_message(
                f"Locked in. You're now a **{info['label']}**.\n"
                f"Run `/trabaho` again to start working."
            )
            return

        current_job = user["job"]

        if not current_job or current_job not in JOBS:
            await interaction.response.send_message(
                "Wala ka pang trabaho.\n"
                "Use `/trabaho job:[job]` first."
            )
            return

        remaining = db.check_cooldown(
            user_id,
            "last_trabaho",
            TRABAHO_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            info = JOBS[current_job]

            await interaction.response.send_message(
                f"On cooldown ka pa sa **{info['label']}**.\n"
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        info = JOBS[current_job]
        earnings = random.randint(info["min"], info["max"])

        new_balance = db.add_balance(user_id, earnings)

        db.set_cooldown(
            user_id,
            "last_trabaho",
            int(time.time()),
        )

        embed = discord.Embed(
            title="Shift Complete",
            description=(
                f"You worked as a **{info['label']}**.\n\n"
                f"Earned: **{db.format_peso(earnings)}**\n"
                f"*{info['flavor']}*"
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /tambay
    @app_commands.command(
        name="tambay",
        description="Tambay with the barkada and hope for the best.",
    )
    async def tambay(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_tambay",
            TAMBAY_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Kakatambay mo lang.\n"
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_tambay",
            int(time.time()),
        )

        win = random.random() < 0.70

        if win:
            amount = random.randint(50, 300)

            new_balance = db.add_balance(
                user_id,
                amount,
            )

            flavors = [
                "May nahanap kang barya sa daan.",
                "Binigyan ka ng extra baon.",
                "Nanalo ka sa barkada.",
                "May nagbayad sa'yo ng utang.",
            ]

            embed = discord.Embed(
                title="Tambay Session",
                description=(
                    f"{random.choice(flavors)}\n\n"
                    f"You earned **{db.format_peso(amount)}**."
                ),
                color=WHITE,
            )

        else:
            amount = random.randint(20, 150)

            new_balance = db.add_balance(
                user_id,
                -amount,
            )

            flavors = [
                "Ikaw ang pinangbayad ng snacks.",
                "Napagastos ka sa inuman.",
                "Libre mo raw sabi ng tropa.",
                "Minalas ka ngayong tambay session.",
            ]

            embed = discord.Embed(
                title="Tambay Session",
                description=(
                    f"{random.choice(flavors)}\n\n"
                    f"You lost **{db.format_peso(amount)}**."
                ),
                color=WHITE,
            )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /sugal
    @app_commands.command(
        name="sugal",
        description="50/50 gamble.",
    )
    @app_commands.describe(
        amount="How much you want to bet."
    )
    async def sugal(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1],
    ):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if amount > user["balance"]:
            await interaction.response.send_message(
                f"You only have **{db.format_peso(user['balance'])}**."
            )
            return

        win = random.random() < 0.5

        if win:
            new_balance = db.add_balance(
                user_id,
                amount,
            )

            embed = discord.Embed(
                title="You Won",
                description=(
                    f"You earned **{db.format_peso(amount)}**."
                ),
                color=WHITE,
            )

        else:
            new_balance = db.add_balance(
                user_id,
                -amount,
            )

            embed = discord.Embed(
                title="You Lost",
                description=(
                    f"You lost **{db.format_peso(amount)}**."
                ),
                color=WHITE,
            )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /baon
    @app_commands.command(
        name="baon",
        description="Claim your daily baon.",
    )
    async def baon(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_baon",
            BAON_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nakuha mo na ang baon mo today.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        amount = random.randint(50, 100)

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
            title="Baon Claimed",
            description=(
                f"You received **{db.format_peso(amount)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /profile
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

        data = db.get_user(
            str(target.id)
        )

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
            value=db.format_peso(
                data["balance"]
            ),
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
                else db.format_duration(
                    trabaho_cd
                )
            ),
            inline=True,
        )

        embed.add_field(
            name="Tambay",
            value=(
                "Ready"
                if tambay_cd == 0
                else db.format_duration(
                    tambay_cd
                )
            ),
            inline=True,
        )

        embed.add_field(
            name="Baon",
            value=(
                "Ready"
                if baon_cd == 0
                else db.format_duration(
                    baon_cd
                )
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
    await bot.add_cog(Economy(bot))
