import logging

import discord
from discord.ext import commands

import db_utils as db

logger = logging.getLogger(__name__)

WHITE = discord.Color(0xFFFFFF)
OWNER_ID = 843377668488429569


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_check(self, ctx: commands.Context) -> bool:
        """
        Runs before every command in this cog.
        Using a cog_check instead of per-command `if ctx.author.id != OWNER_ID: return`
        means non-owners get a clear error instead of silence, and the failure
        shows up in on_command_error / console instead of vanishing.
        """
        if ctx.author.id != OWNER_ID:
            raise commands.CheckFailure(
                "You are not authorized to use this command."
            )
        return True

    async def cog_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ):
        """
        Catches errors raised by commands in this cog specifically, so they
        don't get silently eaten by a global on_command_error handler (if one
        exists elsewhere) and so you actually see what went wrong.
        """
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ You are not authorized to use this command.")
            return

        if isinstance(error, commands.MemberNotFound):
            await ctx.send(f"❌ Could not find member: {error.argument}")
            return

        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Bad argument: {error}")
            return

        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: {error.param.name}")
            return

        # Anything else (e.g. db_utils raising) — log it AND tell the user,
        # instead of failing silently.
        logger.exception(
            "Unhandled error in %s command", ctx.command, exc_info=error
        )
        await ctx.send(f"⚠️ Something went wrong: `{error}`")

    @commands.command(name="give")
    async def give(
        self,
        ctx: commands.Context,
        amount: int,
        user: discord.Member | None = None,
    ):
        if amount <= 0:
            await ctx.send("❌ Amount must be greater than 0.")
            return

        target = user or ctx.author

        try:
            new_balance = db.add_balance(str(target.id), amount)
        except Exception as e:
            logger.exception("db.add_balance failed")
            await ctx.send(f"⚠️ Failed to update balance: `{e}`")
            return

        embed = discord.Embed(
            title="💰 Money Added",
            description=(
                f"Gave **{db.format_peso(amount)}** to {target.mention}."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"New balance: {db.format_peso(new_balance)}"
        )
        await ctx.send(embed=embed)

    @commands.command(name="resetcooldowns")
    async def reset_cooldowns(
        self,
        ctx: commands.Context,
        user: discord.Member | None = None,
    ):
        try:
            if user is None:
                db.reset_all_cooldowns()
                embed = discord.Embed(
                    title="✅ Cooldowns Reset",
                    description="All user cooldowns have been reset.",
                    color=WHITE,
                )
            else:
                db.reset_user_cooldowns(str(user.id))
                embed = discord.Embed(
                    title="✅ Cooldowns Reset",
                    description=f"Cooldowns for {user.mention} have been reset.",
                    color=WHITE,
                )
        except Exception as e:
            logger.exception("Cooldown reset failed")
            await ctx.send(f"⚠️ Failed to reset cooldowns: `{e}`")
            return

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
