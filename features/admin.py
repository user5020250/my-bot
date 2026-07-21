import discord
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


class Admin(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
    ):
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
            title="💰 Money Added",
            description=(
                f"Gave **{db.format_peso(amount)}** "
                f"to {target.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                "New balance: "
                f"{db.format_peso(new_balance)}"
            )
        )

        await ctx.send(
            embed=embed
        )

    @commands.command(
        name="resetcooldowns",
    )
    async def reset_cooldowns(
        self,
        ctx: commands.Context,
        user: discord.Member | None = None,
    ):
        if ctx.author.id != OWNER_ID:
            return

        if user is None:

            db.reset_all_cooldowns()

            embed = discord.Embed(
                title="✅ Cooldowns Reset",
                description=(
                    "All user cooldowns "
                    "have been reset."
                ),
                color=WHITE,
            )

        else:

            db.reset_user_cooldowns(
                str(user.id)
            )

            embed = discord.Embed(
                title="✅ Cooldowns Reset",
                description=(
                    f"Cooldowns for "
                    f"{user.mention} "
                    "have been reset."
                ),
                color=WHITE,
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
