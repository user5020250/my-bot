import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="give",
        description="Owner-only money command.",
    )
    @app_commands.describe(
        amount="How much money to give",
        user="Leave blank to give yourself money",
    )
    async def give(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1],
        user: discord.Member | None = None,
    ):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "You can't use this command.",
                ephemeral=True,
            )
            return

        target = user or interaction.user

        new_balance = db.add_balance(
            str(target.id),
            amount,
        )

        embed = discord.Embed(
            title="Money Added",
            description=(
                f"Gave **{db.format_peso(amount)}** "
                f"to {target.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"New balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Admin(bot)
    )
