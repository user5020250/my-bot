import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS
import db_utils as db

TAMBAY_COOLDOWN_SECONDS = 60
BAON_COOLDOWN_SECONDS = 24 * 60 * 60

JOB_CHOICES = [
    app_commands.Choice(name=f"{info['emoji']} {info['label']}", value=key)
    for key, info in JOBS.items()
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------- /jobs
    @app_commands.command(name="jobs", description="Peep every job and how much it pays.")
    async def jobs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💼 Trabaho Menu",
            description="Pick your grind with `/trabaho job:<choose>`. No pressure, sana all magka-work naman.",
            color=discord.Color.blue(),
        )
        for info in JOBS.values():
            embed.add_field(
                name=f"{info['emoji']} {info['label']}",
                value=f"{db.format_peso(info['min'])} – {db.format_peso(info['max'])} per shift\n*{info['flavor']}*",
                inline=False,
            )
        embed.set_footer(text="Trabaho cooldown: 30 min. Grind responsibly bestie.")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /trabaho
    @app_commands.command(
        name="trabaho",
        description="Pick a job, or clock in to your current one and get that bag.",
    )
    @app_commands.describe(job="Switch to this job (free, no cooldown eaten).")
    @app_commands.choices(job=JOB_CHOICES)
    async def trabaho(self, interaction: discord.Interaction, job: app_commands.Choice[str] = None):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if job is not None:
            db.set_job(user_id, job.value)
            info = JOBS[job.value]
            await interaction.response.send_message(
                f"{info['emoji']} Bet — you're now a **{info['label']}**! "
                f"Run `/trabaho` again (no job param) to actually clock in and secure the bag."
            )
            return

        current_job = user["job"]
        if not current_job or current_job not in JOBS:
            await interaction.response.send_message(
                "Bro you don't even have a job yet 💀 Use `/trabaho job:<choose>` first. "
                "Check `/jobs` kung ano meron.",
            )
            return

        remaining = db.check_cooldown(user_id, "last_trabaho", TRABAHO_COOLDOWN_SECONDS)
        if remaining > 0:
            info = JOBS[current_job]
            await interaction.response.send_message(
                f"⏳ Chill, you're still on break from your {info['label']} shift. "
                f"Next clock-in in {db.format_duration(remaining)}.",
            )
            return

        info = JOBS[current_job]
        earnings = random.randint(info["min"], info["max"])
        new_balance = db.add_balance(user_id, earnings)
        db.set_cooldown(user_id, "last_trabaho", int(time.time()))

        embed = discord.Embed(
            title=f"{info['emoji']} Shift Complete, Sheesh!",
            description=f"You clocked in as a **{info['label']}** and secured "
            f"**{db.format_peso(earnings)}**! Let's get this bread.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /tambay
    @app_commands.command(name="tambay", description="Touch grass with the barkada for a chance at quick cash.")
    async def tambay(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        remaining = db.check_cooldown(user_id, "last_tambay", TAMBAY_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ You literally just tambay'd. Try again in {db.format_duration(remaining)}.",
            )
            return

        db.set_cooldown(user_id, "last_tambay", int(time.time()))
        win = random.random() < 0.70

        if win:
            amount = random.randint(50, 300)
            new_balance = db.add_balance(user_id, amount)
            flavors = [
                "Found loose change on the ground, it's giving lucky day.",
                "Lola hooked you up with extra baon, no cap.",
                "Won a round of tong-its vs the barkada, ez.",
                "Kapitbahay tipped you for house-sitting, we love to see it.",
            ]
            embed = discord.Embed(
                title="🧢 Tambay Session",
                description=f"{random.choice(flavors)} You secured **{db.format_peso(amount)}**!",
                color=discord.Color.green(),
            )
        else:
            amount = random.randint(20, 150)
            new_balance = db.add_balance(user_id, -amount)
            flavors = [
                "Bought yosi for the whole squad, rip your wallet.",
                "Softdrinks run turned into you treating everyone.",
                "Got peer pressured into pakain-tayo mode.",
                "Lost sa sakla, tuktok pa. Ouch.",
            ]
            embed = discord.Embed(
                title="🧢 Tambay Session",
                description=f"{random.choice(flavors)} You're down **{db.format_peso(amount)}**. Rough.",
                color=discord.Color.red(),
            )

        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------------- /sugal
    @app_commands.command(name="sugal", description="50/50 coinflip bet. No cap, no limit, no cooldown.")
    @app_commands.describe(amount="How much you're throwing in")
    async def sugal(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1]):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if amount > user["balance"]:
            await interaction.response.send_message(
                f"Bro you're broke 💀 You only have {db.format_peso(user['balance'])}.",
            )
            return

        win = random.random() < 0.5
        if win:
            new_balance = db.add_balance(user_id, amount)
            embed = discord.Embed(
                title="🎲 SUGAL — W!",
                description=f"Let's gooo, you won **{db.format_peso(amount)}**! Certified sigma moment.",
                color=discord.Color.green(),
            )
        else:
            new_balance = db.add_balance(user_id, -amount)
            embed = discord.Embed(
                title="🎲 SUGAL — L",
                description=f"Down **{db.format_peso(amount)}**. It's giving bankruptcy arc. Run it back?",
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
                f"⏳ Already claimed your baon today, greedy 😭 Come back in {db.format_duration(remaining)}.",
            )
            return

        amount = random.randint(50, 100)
        new_balance = db.add_balance(user_id, amount)
        db.set_cooldown(user_id, "last_baon", int(time.time()))

        embed = discord.Embed(
            title="🎒 Baon Secured",
            description=f"Parents came through with **{db.format_peso(amount)}**. Bet.",
            color=discord.Color.gold(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------- /profile
    @app_commands.command(name="profile", description="Check out your (or someone else's) profile.")
    @app_commands.describe(user="Whose profile to view — leave blank to see your own")
    async def profile(self, interaction: discord.Interaction, user: discord.Member = None):
        target = user or interaction.user
        data = db.get_user(str(target.id))

        job_key = data["job"]
        job_label = JOBS[job_key]["label"] if job_key in JOBS else "Unemployed 💀"
        job_emoji = JOBS[job_key]["emoji"] if job_key in JOBS else "🚫"

        trabaho_cd = db.check_cooldown(str(target.id), "last_trabaho", TRABAHO_COOLDOWN_SECONDS)
        tambay_cd = db.check_cooldown(str(target.id), "last_tambay", TAMBAY_COOLDOWN_SECONDS)
        baon_cd = db.check_cooldown(str(target.id), "last_baon", BAON_COOLDOWN_SECONDS)

        embed = discord.Embed(
            title=f"{target.display_name}'s Profile",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="💰 Balance", value=db.format_peso(data["balance"]), inline=True)
        embed.add_field(name=f"{job_emoji} Job", value=job_label, inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)  # spacer for clean grid
        embed.add_field(
            name="⏳ Trabaho",
            value="Ready ✅" if trabaho_cd == 0 else db.format_duration(trabaho_cd),
            inline=True,
        )
        embed.add_field(
            name="⏳ Tambay",
            value="Ready ✅" if tambay_cd == 0 else db.format_duration(tambay_cd),
            inline=True,
        )
        embed.add_field(
            name="⏳ Baon",
            value="Ready ✅" if baon_cd == 0 else db.format_duration(baon_cd),
            inline=True,
        )
        embed.set_footer(text="It's giving financial stability... or not 💅")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
