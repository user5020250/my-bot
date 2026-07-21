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
            await interaction.response.send_message("Hindi ka pwedeng mangutang sa sarili mo. 😅", ephemeral=True)
            return
        if lender.bot:
            await interaction.response.send_message("Hindi pwedeng mangutang sa bot.", ephemeral=True)
            return

        lender_user = db.get_user(lender_id)
        if lender_user["balance"] < amount:
            await interaction.response.send_message(
                f"Wala pang sapat pera si {lender.display_name} para pautangin ka.",
                ephemeral=True,
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
            description=f"{interaction.user.mention} nangutang ng **{db.format_peso(amount)}** "
            f"kay {lender.mention}. Bayaran mo agad ha! Gamitin ang `/bayad`.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Balance mo ngayon: {db.format_peso(new_borrower_balance)}")
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
                f"Wala kang utang kay {lender.display_name}.", ephemeral=True
            )
            return

        borrower_user = db.get_user(borrower_id)
        pay_amount = min(amount, total_owed, borrower_user["balance"])

        if pay_amount <= 0:
            conn.close()
            await interaction.response.send_message("Wala kang sapat na pera para magbayad.", ephemeral=True)
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
        desc = f"Binayaran mo si {lender.mention} ng **{db.format_peso(pay_amount)}**."
        if left > 0:
            desc += f"\nNatitira ka pang utang na **{db.format_peso(left)}**."
        else:
            desc += "\nWala ka nang utang sa kanya! 🎉"

        embed = discord.Embed(title="💵 Bayad Utang", description=desc, color=discord.Color.green())
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------------- /budol
    @app_commands.command(name="budol", description="Try to scam another player. Risky!")
    @app_commands.describe(target="Who to try to scam")
    async def budol(self, interaction: discord.Interaction, target: discord.Member):
        scammer_id = str(interaction.user.id)
        target_id = str(target.id)

        if target_id == scammer_id:
            await interaction.response.send_message("Hindi mo pwedeng budol-budolin ang sarili mo. 😂", ephemeral=True)
            return
        if target.bot:
            await interaction.response.send_message("Hindi pwedeng i-budol ang bot.", ephemeral=True)
            return

        remaining = db.check_cooldown(scammer_id, "last_budol", BUDOL_COOLDOWN_SECONDS)
        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Baka mahalata ka. Try ulit in {db.format_duration(remaining)}.",
                ephemeral=True,
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
                    description=f"Sinubukan mong i-budol si {target.mention} pero wala naman siyang pera. Sayang!",
                    color=discord.Color.greyple(),
                )
            else:
                db.add_balance(target_id, -stolen)
                new_balance = db.add_balance(scammer_id, stolen)
                embed = discord.Embed(
                    title="🎭 Budol Success!",
                    description=f"Na-budol mo si {target.mention} ng **{db.format_peso(stolen)}**! 😈",
                    color=discord.Color.green(),
                )
                embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        else:
            penalty = random.randint(100, 1000)
            new_balance = db.add_balance(scammer_id, -penalty)
            embed = discord.Embed(
                title="🎭 Budol Failed — Nahuli Ka!",
                description=f"Nahalata ka ni {target.mention} at na-report ka. "
                f"Nawalan ka ng **{db.format_peso(penalty)}** sa multa.",
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
                f"⏳ Paos ka pa. Kumanta ulit in {db.format_duration(remaining)}.",
                ephemeral=True,
            )
            return

        db.set_cooldown(user_id, "last_karaoke", int(time.time()))
        tip = random.randint(50, 500)
        new_balance = db.add_balance(user_id, tip)

        songs = ["My Way", "Zombie", "Pagbigyan Mo Na", "Tala", "Kisapmata", "Anak"]
        song = random.choice(songs)

        embed = discord.Embed(
            title="🎤 Videoke Time!",
            description=f"Kinanta mo ang **\"{song}\"** at natuwa ang mga kapitbahay. "
            f"Natanggap ka ng **{db.format_peso(tip)}** na tip!",
            color=discord.Color.purple(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Social(bot))
