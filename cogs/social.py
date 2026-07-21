import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

BUDOL_COOLDOWN_SECONDS = 24 * 60 * 60
KARAOKE_COOLDOWN_SECONDS = 5 * 60
BUDOL_SUCCESS_CHANCE = 0.4


class Social(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------------------------------------------- /utang
    @app_commands.command(name="utang", description="Borrow money from another player.")
    @app_commands.describe(lender="Who you're borrowing from", amount="How much to borrow")
    async def utang(
        self,
        interaction: discord.Interaction,
        lender: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        borrower_id = str(interaction.user.id)
        lender_id = str(lender.id)

        if lender_id == borrower_id:
            await interaction.response.send_message("You can't utang from yourself 💀 make it make sense.")
            return
        if lender.bot:
            await interaction.response.send_message("Bots don't do utang, sorry.")
            return

        lender_user = db.get_user(lender_id)
        if lender_user["balance"] < amount:
            await interaction.response.send_message(
                f"{lender.display_name} is also broke, they can't lend you that. 💀",
            )
            return

        db.add_balance(lender_id, -amount)
        new_borrower_balance = db.add_balance(borrower_id, amount)

        conn = get_conn()
        conn.execute(
            "INSERT INTO debts (lender, borrower, amount, created_at) VALUES (?, ?, ?, ?)",
            (lender_id, borrower_id, amount, int(time.time())),
        )
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="🤝 Utang Approved",
            description=f"{interaction.user.mention} borrowed **{db.format_peso(amount)}** "
            f"from {lender.mention}. Pay it back before it gets awkward — use `/bayad`.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Your balance: {db.format_peso(new_borrower_balance)}")
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /bayad
    @app_commands.command(name="bayad", description="Pay back a debt you owe someone.")
    @app_commands.describe(lender="Who you owe money to", amount="How much to pay back")
    async def bayad(
        self,
        interaction: discord.Interaction,
        lender: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        borrower_id = str(interaction.user.id)
        lender_id = str(lender.id)

        conn = get_conn()
        debts = conn.execute(
            "SELECT * FROM debts WHERE lender = ? AND borrower = ? ORDER BY created_at ASC",
            (lender_id, borrower_id),
        ).fetchall()
        total_owed = sum(d["amount"] for d in debts)

        if total_owed == 0:
            conn.close()
            await interaction.response.send_message(
                f"You don't owe {lender.display_name} anything. You're good.",
            )
            return

        borrower_user = db.get_user(borrower_id)
        pay_amount = min(amount, total_owed, borrower_user["balance"])

        if pay_amount <= 0:
            conn.close()
            await interaction.response.send_message("You don't have enough cash to pay that back rn.")
            return

        remaining_to_clear = pay_amount
        for d in debts:
            if remaining_to_clear <= 0:
                break
            clear = min(d["amount"], remaining_to_clear)
            new_amount = d["amount"] - clear
            if new_amount <= 0:
                conn.execute("DELETE FROM debts WHERE id = ?", (d["id"],))
            else:
                conn.execute("UPDATE debts SET amount = ? WHERE id = ?", (new_amount, d["id"]))
            remaining_to_clear -= clear
        conn.commit()
        conn.close()

        db.add_balance(borrower_id, -pay_amount)
        db.add_balance(lender_id, pay_amount)

        left = total_owed - pay_amount
        desc = f"Paid {lender.mention} **{db.format_peso(pay_amount)}**."
        if left > 0:
            desc += f"\nStill owe **{db.format_peso(left)}** though, keep it up."
        else:
            desc += "\nDebt fully cleared! Certified honorable. 🫡"

        embed = discord.Embed(title="💵 Bayad Utang", description=desc, color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /budol
    @app_commands.command(name="budol", description="Try to scam another player. Risky!")
    @app_commands.describe(target="Who to try to scam")
    async def budol(self, interaction: discord.Interaction, target: discord.Member):
        scammer_id = str(interaction.user.id)
        target_id = str(target.id)

        if target_id == scammer_id:
            await interaction.response.send_message("You can't budol yourself, that's just called losing money 😭")
            return
        if target.bot:
            await interaction.response.send_message("Bots don't fall for budol, nice try.")
            return

        remaining = db.check_cooldown(scammer_id, "last_budol", BUDOL_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Lay low for now, people are onto you. Try again in {db.format_duration(remaining)}.",
            )
            return

        db.set_cooldown(scammer_id, "last_budol", int(time.time()))
        target_user = db.get_user(target_id)
        success = random.random() < BUDOL_SUCCESS_CHANCE

        if success:
            stolen = min(round(target_user["balance"] * random.uniform(0.1, 0.3)), 5000)
            if stolen <= 0:
                embed = discord.Embed(
                    title="🎭 Budol Attempt",
                    description=f"Tried to budol {target.mention} but they're broke too. Nothing to take, L attempt.",
                    color=discord.Color.greyple(),
                )
            else:
                db.add_balance(target_id, -stolen)
                new_balance = db.add_balance(scammer_id, stolen)
                embed = discord.Embed(
                    title="🎭 Budol Success!",
                    description=f"Scammed {target.mention} out of **{db.format_peso(stolen)}**. Menace behavior. 😈",
                    color=discord.Color.green(),
                )
                embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        else:
            penalty = random.randint(100, 1000)
            new_balance = db.add_balance(scammer_id, -penalty)
            embed = discord.Embed(
                title="🎭 Budol Failed — Caught In 4K",
                description=f"{target.mention} clocked the scam instantly and reported you. "
                f"Fined **{db.format_peso(penalty)}**. The audacity, and it didn't even work.",
                color=discord.Color.red(),
            )
            embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------ /karaoke
    @app_commands.command(name="karaoke", description="Sing karaoke for tips (₱50-₱500).")
    async def karaoke(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        remaining = db.check_cooldown(user_id, "last_karaoke", KARAOKE_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Give the mic a break. Try again in {db.format_duration(remaining)}.",
            )
            return

        db.set_cooldown(user_id, "last_karaoke", int(time.time()))
        tip = random.randint(50, 500)
        new_balance = db.add_balance(user_id, tip)

        songs = ["My Way", "Zombie", "Pagbigyan Mo Na", "Tala", "Kisapmata", "Anak"]
        song = random.choice(songs)

        embed = discord.Embed(
            title="🎤 Videoke Time",
            description=f"Belted out **\"{song}\"** and the neighbors actually loved it. "
            f"Got **{db.format_peso(tip)}** in tips. Superstar behavior fr.",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
