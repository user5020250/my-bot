# features/utang.py

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta


class LoanView(discord.ui.View):
    def __init__(self, lender, borrower, amount):
        super().__init__(timeout=60)

        self.lender = lender
        self.borrower = borrower
        self.amount = amount

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id != self.lender.id:
            await interaction.response.send_message(
                "Only the lender can respond to this request.",
                ephemeral=True
            )
            return False

        return True

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        # TODO:
        # Check lender balance

        # TODO:
        # Remove money from lender

        # TODO:
        # Give money to borrower

        loan_data = {
            "lender_id": self.lender.id,
            "borrower_id": self.borrower.id,
            "amount": self.amount,
            "created_at": datetime.utcnow(),
            "due_date": datetime.utcnow() + timedelta(days=7),
            "status": "active"
        }

        # Save loan_data to your database here

        embed = discord.Embed(
            title="Loan Approved",
            color=discord.Color.light_grey()
        )

        embed.add_field(
            name="Borrower",
            value=self.borrower.mention,
            inline=False
        )

        embed.add_field(
            name="Lender",
            value=self.lender.mention,
            inline=False
        )

        embed.add_field(
            name="Amount",
            value=f"₱{self.amount:,}",
            inline=False
        )

        embed.add_field(
            name="Due Date",
            value="<t:{}:F>".format(
                int(
                    (datetime.utcnow() + timedelta(days=7)).timestamp()
                )
            ),
            inline=False
        )

        self.clear_items()

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.danger
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        embed = discord.Embed(
            title="Loan Declined",
            description="The loan request has been declined.",
            color=discord.Color.light_grey()
        )

        self.clear_items()

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class Utang(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    utang = app_commands.Group(
        name="utang",
        description="Loan commands"
    )

    @utang.command(
        name="request",
        description="Request a loan from another user."
    )
    async def request(
        self,
        interaction: discord.Interaction,
        lender: discord.Member,
        amount: int
    ):
        if amount <= 0:
            return await interaction.response.send_message(
                "Amount must be greater than zero.",
                ephemeral=True
            )

        if lender.bot:
            return await interaction.response.send_message(
                "You cannot request a loan from a bot.",
                ephemeral=True
            )

        if lender.id == interaction.user.id:
            return await interaction.response.send_message(
                "You cannot request a loan from yourself.",
                ephemeral=True
            )

        due_date = datetime.utcnow() + timedelta(days=7)

        embed = discord.Embed(
            title="Loan Request",
            color=discord.Color.light_grey()
        )

        embed.add_field(
            name="Borrower",
            value=interaction.user.mention,
            inline=False
        )

        embed.add_field(
            name="Lender",
            value=lender.mention,
            inline=False
        )

        embed.add_field(
            name="Amount",
            value=f"₱{amount:,}",
            inline=False
        )

        embed.add_field(
            name="Due Date",
            value=f"<t:{int(due_date.timestamp())}:F>",
            inline=False
        )

        embed.set_footer(
            text="This request expires in 60 seconds."
        )

        view = LoanView(
            lender=lender,
            borrower=interaction.user,
            amount=amount
        )

        await interaction.response.send_message(
            content=lender.mention,
            embed=embed,
            view=view
        )


async def setup(bot):
    await bot.add_cog(Utang(bot))
