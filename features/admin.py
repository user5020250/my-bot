import discord
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="give",
    )
    async def give(
        self,
        ctx: commands.Context,
        amount: int,
        user: discord.Member | None = None,
    ):
        if ctx.author.id != OWNER_ID:
            return

        if amount <= 0:
            await ctx.send(
                "❌ Amount must be greater than 0."
            )
            return

        target = user or ctx.author

        new_balance = db.add_balance(
            str(target.id),
            amount,
        )

        embed = discord.Embed(
            title="💸 Money Added",
            description=(
                f"Gave **{db.format_peso(amount)}** "
                f"to {target.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                f"New balance: "
                f"{db.format_peso(new_balance)}"
            )
        )

        await ctx.send(
            embed=embed
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Admin(bot)
    )
