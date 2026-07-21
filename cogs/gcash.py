import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 123456789012345678  # replace with your Discord ID


class GCash(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    gcash = app_commands.Group(
        name="gcash",
        description="Send money to other players.",
    )

    # ------------------------------------------------------ /give

    @app_commands.command(
        name="give",
        description="Owner-only money command.",
    )
    @app_commands.describe(
        user="Who gets the money",
        amount="How much money to give",
    )
    async def give(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "You can't use this command.",
                ephemeral=True,
            )
            return

        new_balance = db.add_balance(
            str(user.id),
            amount,
        )

        embed = discord.Embed(
            title="Money Added",
            description=(
                f"Gave **{db.format_peso(amount)}** "
                f"to {user.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"New balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------ /gcash send

    @gcash.command(
        name="send",
        description="Send money to another player.",
    )
    @app_commands.describe(
        user="Who receives the money",
        amount="How much to send",
    )
    async def send(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        sender_id = str(interaction.user.id)
        receiver_id = str(user.id)

        if user.bot:
            await interaction.response.send_message(
                "You can't send money to bots."
            )
            return

        if sender_id == receiver_id:
            await interaction.response.send_message(
                "You can't send money to yourself."
            )
            return

        sender = db.get_user(sender_id)

        if sender["balance"] < amount:
            await interaction.response.send_message(
                "You don't have enough money."
            )
            return

        db.add_balance(sender_id, -amount)
        receiver_balance = db.add_balance(
            receiver_id,
            amount,
        )

        embed = discord.Embed(
            title="GCash Transfer",
            description=(
                f"{interaction.user.mention} sent "
                f"**{db.format_peso(amount)}** "
                f"to {user.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"{user.display_name}'s balance: {db.format_peso(receiver_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------ /gcash loan

    @gcash.command(
        name="loan",
        description="Loan money to another player.",
    )
    @app_commands.describe(
        user="Who gets the loan",
        amount="Loan amount",
    )
    async def loan(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        lender_id = str(interaction.user.id)
        borrower_id = str(user.id)

        if user.bot:
            await interaction.response.send_message(
                "Bots can't borrow money."
            )
            return

        if lender_id == borrower_id:
            await interaction.response.send_message(
                "You can't loan money to yourself."
            )
            return

        lender = db.get_user(lender_id)

        if lender["balance"] < amount:
            await interaction.response.send_message(
                "You don't have enough money."
            )
            return

        db.add_balance(lender_id, -amount)
        db.add_balance(borrower_id, amount)

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
            title="GCash Loan",
            description=(
                f"{interaction.user.mention} loaned "
                f"**{db.format_peso(amount)}** "
                f"to {user.mention}.\n\n"
                f"Use `/bayad` to repay it."
            ),
            color=WHITE,
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        GCash(bot)
    )
