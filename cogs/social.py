import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

BUDOL_COOLDOWN_SECONDS = 24 * 60 * 60
KARAOKE_COOLDOWN_SECONDS = 5 * 60

BUDOL_SUCCESS_CHANCE = 0.4


class Social(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # -------------------------------------------------------------- /utang

    @app_commands.command(
        name="utang",
        description="Borrow money from another player.",
    )
    @app_commands.describe(
        lender="Who you're borrowing from",
        amount="How much to borrow",
    )
    async def utang(
        self,
        interaction: discord.Interaction,
        lender: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        borrower_id = str(interaction.user.id)
        lender_id = str(lender.id)

        if lender_id == borrower_id:
            await interaction.response.send_message(
                "Hindi ka puwedeng umutang sa sarili mo."
            )
            return

        if lender.bot:
            await interaction.response.send_message(
                "Hindi nagpapautang ang bots."
            )
            return

        lender_user = db.get_user(lender_id)

        if lender_user["balance"] < amount:
            await interaction.response.send_message(
                f"Walang sapat na pera si {lender.display_name}."
            )
            return

        db.add_balance(lender_id, -amount)
        new_balance = db.add_balance(borrower_id, amount)

        conn = get_conn()

        conn.execute(
            """
            INSERT INTO debts (
                lender,
                borrower,
                amount,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                lender_id,
                borrower_id,
                amount,
                int(time.time()),
            ),
        )

        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="Utang Approved",
            description=(
                f"{interaction.user.mention} borrowed "
                f"**{db.format_peso(amount)}** "
                f"from {lender.mention}.\n\n"
                f"Use `/bayad` to pay it back."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -------------------------------------------------------------- /bayad

    @app_commands.command(
        name="bayad",
        description="Pay your debt.",
    )
    @app_commands.describe(
        lender="Who you owe money to",
        amount="How much to pay",
    )
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
            """
            SELECT *
            FROM debts
            WHERE lender = ?
            AND borrower = ?
            ORDER BY created_at ASC
            """,
            (
                lender_id,
                borrower_id,
            ),
        ).fetchall()

        total_owed = sum(
            debt["amount"]
            for debt in debts
        )

        if total_owed == 0:
            conn.close()

            await interaction.response.send_message(
                f"Wala kang utang kay {lender.display_name}."
            )
            return

        borrower_user = db.get_user(
            borrower_id
        )

        pay_amount = min(
            amount,
            total_owed,
            borrower_user["balance"],
        )

        if pay_amount <= 0:
            conn.close()

            await interaction.response.send_message(
                "Wala kang sapat na pera."
            )
            return

        remaining = pay_amount

        for debt in debts:
            if remaining <= 0:
                break

            payment = min(
                debt["amount"],
                remaining,
            )

            new_amount = (
                debt["amount"] - payment
            )

            if new_amount <= 0:
                conn.execute(
                    "DELETE FROM debts WHERE id = ?",
                    (debt["id"],),
                )
            else:
                conn.execute(
                    """
                    UPDATE debts
                    SET amount = ?
                    WHERE id = ?
                    """,
                    (
                        new_amount,
                        debt["id"],
                    ),
                )

            remaining -= payment

        conn.commit()
        conn.close()

        db.add_balance(
            borrower_id,
            -pay_amount,
        )

        db.add_balance(
            lender_id,
            pay_amount,
        )

        left = total_owed - pay_amount

        description = (
            f"Nagbayad ka ng "
            f"**{db.format_peso(pay_amount)}** "
            f"kay {lender.mention}."
        )

        if left > 0:
            description += (
                f"\n\nMay utang ka pang "
                f"**{db.format_peso(left)}**."
            )
        else:
            description += (
                "\n\nBayad na lahat."
            )

        embed = discord.Embed(
            title="Bayad Utang",
            description=description,
            color=WHITE,
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -------------------------------------------------------------- /budol

    @app_commands.command(
        name="budol",
        description="Try to scam another player.",
    )
    @app_commands.describe(
        target="Who to scam",
    )
    async def budol(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        scammer_id = str(
            interaction.user.id
        )

        target_id = str(
            target.id
        )

        if target_id == scammer_id:
            await interaction.response.send_message(
                "Hindi mo puwedeng i-budol ang sarili mo."
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "Hindi naloloko ang bots."
            )
            return

        remaining = db.check_cooldown(
            scammer_id,
            "last_budol",
            BUDOL_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Mainit ka pa. "
                f"Try again in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            scammer_id,
            "last_budol",
            int(time.time()),
        )

        target_user = db.get_user(
            target_id
        )

        success = (
            random.random()
            < BUDOL_SUCCESS_CHANCE
        )

        if success:
            stolen = min(
                round(
                    target_user["balance"]
                    * random.uniform(
                        0.1,
                        0.3,
                    )
                ),
                5000,
            )

            if stolen <= 0:
                embed = discord.Embed(
                    title="Budol Attempt",
                    description=(
                        f"Wala ring pera si "
                        f"{target.mention}."
                    ),
                    color=WHITE,
                )

            else:
                db.add_balance(
                    target_id,
                    -stolen,
                )

                new_balance = db.add_balance(
                    scammer_id,
                    stolen,
                )

                embed = discord.Embed(
                    title="Budol Success",
                    description=(
                        f"Nakakuha ka ng "
                        f"**{db.format_peso(stolen)}** "
                        f"mula kay "
                        f"{target.mention}."
                    ),
                    color=WHITE,
                )

                embed.set_footer(
                    text=(
                        f"Balance: "
                        f"{db.format_peso(new_balance)}"
                    )
                )

        else:
            penalty = random.randint(
                100,
                1000,
            )

            new_balance = db.add_balance(
                scammer_id,
                -penalty,
            )

            embed = discord.Embed(
                title="Budol Failed",
                description=(
                    f"Nahuli ka ni "
                    f"{target.mention}.\n\n"
                    f"Multa: "
                    f"**{db.format_peso(penalty)}**."
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

    # ------------------------------------------------------------ /karaoke

    @app_commands.command(
        name="karaoke",
        description="Kumanta para kumita.",
    )
    async def karaoke(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(
            interaction.user.id
        )

        remaining = db.check_cooldown(
            user_id,
            "last_karaoke",
            KARAOKE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nagpapahinga pa ang mic.\n"
                f"Try again in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_karaoke",
            int(time.time()),
        )

        tip = random.randint(
            50,
            500,
        )

        new_balance = db.add_balance(
            user_id,
            tip,
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

        song = random.choice(
            songs
        )

        embed = discord.Embed(
            title="Videoke Time",
            description=(
                f"Kumanta ka ng "
                f"**{song}**.\n\n"
                f"Kumita ka ng "
                f"**{db.format_peso(tip)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Social(bot)
    )
