import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS
import db_utils as db

TAMBAY_COOLDOWN_SECONDS = 60
BAON_COOLDOWN_SECONDS = 24 * 60 * 60

# Build the slash-command choice list once
JOB_CHOICES = [
    app_commands.Choice(name=f"{info['emoji']} {info['label']}", value=key)
    for key, info in JOBS.items()
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /jobs
    @app_commands.command(name="jobs", description="See every available job and its pay range.")
    async def jobs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💼 Trabaho Listings",
            description="Gamitin ang `/trabaho job:<pumili>` para pumili ng trabaho.",
            color=discord.Color.blue(),
        )
        for info in JOBS.values():
            embed.add_field(
                name=f"{info['emoji']} {info['label']}",
                value=f"{db.format_peso(info['min'])} – {db.format_peso(info['max'])} per shift\n*{info['flavor']}*",
                inline=False,
            )
        embed.set_footer(text="Trabaho cooldown: 30 minutes")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /trabaho
    @app_commands.command(
        name="trabaho",
        description="Choose a job, or work your current job to earn money (30 min cooldown).",
    )
    @app_commands.describe(job="Pick this to switch jobs (doesn't use your cooldown).")
    @app_commands.choices(job=JOB_CHOICES)
    async def trabaho(self, interaction: discord.Interaction, job: app_commands.Choice[str] = None):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        # Switching / picking a job is free and instant.
        if job is not None:
            db.set_job(user_id, job.value)
            info = JOBS[job.value]
            await interaction.response.send_message(
                f"{info['emoji']} Ngayon ka nang **{info['label']}**! "
                f"Gamitin ulit ang `/trabaho` (walang job param) para kumita."
            )
            return

        current_job = user["job"]
        if not current_job or current_job not in JOBS:
            await interaction.response.send_message(
                "Wala ka pang trabaho! Gamitin ang `/trabaho job:<pumili>` muna. "
                "Tignan ang `/jobs` para sa listahan.",
                ephemeral=True,
            )
            return

        remaining = db.check_cooldown(user_id, "last_trabaho", TRABAHO_COOLDOWN_SECONDS)
        if remaining > 0:
            info = JOBS[current_job]
            await interaction.response.send_message(
                f"⏳ Pagod ka pa from your last shift as {info['label']}. "
                f"Pwede ka ulit mag-trabaho in {db.format_duration(remaining)}.",
                ephemeral=True,
            )
            return

        info = JOBS[current_job]
        earnings = random.randint(info["min"], info["max"])
        new_balance = db.add_balance(user_id, earnings)
        db.set_cooldown(user_id, "last_trabaho", int(time.time()))

        embed = discord.Embed(
            title=f"{info['emoji']} Shift Complete!",
            description=f"Nagtrabaho ka bilang **{info['label']}** at kumita ka ng "
            f"**{db.format_peso(earnings)}**!",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /tambay
    @app_commands.command(name="tambay", description="Hang out for a small chance at quick cash.")
    async def tambay(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        remaining = db.check_cooldown(user_id, "last_tambay", TAMBAY_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Huminga ka muna. Pwede ka ulit mag-tambay in {db.format_duration(remaining)}.",
                ephemeral=True,
            )
            return

        db.set_cooldown(user_id, "last_tambay", int(time.time()))
        win = random.random() < 0.70

        if win:
            amount = random.randint(50, 300)
            new_balance = db.add_balance(user_id, amount)
            flavors = [
                "May nakitang barya sa kanto!",
                "Binigyan ka ng lola mo ng extra baon.",
                "Nanalo ka sa tong-its kasama ka-tropa.",
                "Na-tip ka ng kapitbahay sa pagbantay ng bahay.",
            ]
            embed = discord.Embed(
                title="🧢 Tambay Time",
                description=f"{random.choice(flavors)} Kumita ka ng **{db.format_peso(amount)}**!",
                color=discord.Color.green(),
            )
        else:
            amount = random.randint(20, 150)
            new_balance = db.add_balance(user_id, -amount)
            flavors = [
                "Bumili ka ng yosi kasama ang mga tropa.",
                "Nag-inuman kayo ng softdrinks sa istorya.",
                "Nagpa-chinelas... treat mo pala ang lahat.",
                "Nasugal ka ng tuktok sa sakla nila kuya.",
            ]
            embed = discord.Embed(
                title="🧢 Tambay Time",
                description=f"{random.choice(flavors)} Nagastos ka ng **{db.format_peso(amount)}**.",
                color=discord.Color.red(),
            )

        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /sugal
    @app_commands.command(name="sugal", description="Bet money on a 50/50 coin flip. No limit, no cooldown.")
    @app_commands.describe(amount="How much to bet")
    async def sugal(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if amount > user["balance"]:
            await interaction.response.send_message(
                f"Kulang ang pera mo! Balance mo ngayon: {db.format_peso(user['balance'])}",
                ephemeral=True,
            )
            return

        win = random.random() < 0.5
        if win:
            new_balance = db.add_balance(user_id, amount)
            embed = discord.Embed(
                title="🎲 Sugal — PANALO!",
                description=f"Nanalo ka ng **{db.format_peso(amount)}**!",
                color=discord.Color.green(),
            )
        else:
            new_balance = db.add_balance(user_id, -amount)
            embed = discord.Embed(
                title="🎲 Sugal — TALO!",
                description=f"Natalo ka ng **{db.format_peso(amount)}**. Sige na lang, susunod na uli.",
                color=discord.Color.red(),
            )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /baon
    @app_commands.command(name="baon", description="Claim your daily allowance (₱50-₱100).")
    async def baon(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        remaining = db.check_cooldown(user_id, "last_baon", BAON_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Na-claim mo na ang baon mo ngayon. Susunod in {db.format_duration(remaining)}.",
                ephemeral=True,
            )
            return

        amount = random.randint(50, 100)
        new_balance = db.add_balance(user_id, amount)
        db.set_cooldown(user_id, "last_baon", int(time.time()))

        embed = discord.Embed(
            title="🎒 Baon Claimed!",
            description=f"Binigyan ka ng magulang mo ng **{db.format_peso(amount)}** na baon.",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
