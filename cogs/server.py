"""
locks
!lock [reason]              shortcut: !l
!unlock                     shortcut: !ul
!serverlockdown [reason]    shortcut: !sld
!serverunlock                shortcut: !sul
"""

import discord
from discord.ext import commands

from .config import EMBED_COLOR


class Locks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Tracks which channels were locked by !serverlockdown, per guild,
        # so !serverunlock only restores channels that were actually affected.
        self.lockdown_channels: dict[int, list[int]] = {}

    # ---------------------------- LOCK / UNLOCK ----------------------------
    @commands.command(name="lock", aliases=["l"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, *, reason: str = "no reason provided"):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)

        embed = discord.Embed(
            title="channel locked",
            description=f"this channel has been locked.\n**reason:** {reason}",
            color=EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    @commands.command(name="unlock", aliases=["ul"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

        embed = discord.Embed(
            title="channel unlocked",
            description="this channel has been unlocked.",
            color=EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    # ---------------------------- SERVER LOCKDOWN ----------------------------
    @commands.command(name="serverlockdown", aliases=["sld"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def serverlockdown(self, ctx: commands.Context, *, reason: str = "no reason provided"):
        guild = ctx.guild
        locked_ids = []

        for channel in guild.text_channels:
            overwrite = channel.overwrites_for(guild.default_role)
            if overwrite.send_messages is False:
                continue

            overwrite.send_messages = False
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite, reason=reason)
                locked_ids.append(channel.id)
            except discord.Forbidden:
                pass

        self.lockdown_channels[guild.id] = locked_ids

        embed = discord.Embed(
            title="server lockdown activated",
            description=f"locked **{len(locked_ids)}** text channels.\n**reason:** {reason}",
            color=EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    @commands.command(name="serverunlock", aliases=["sul"])
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def serverunlock(self, ctx: commands.Context):
        guild = ctx.guild
        locked_ids = self.lockdown_channels.get(guild.id, [])

        if not locked_ids:
            return await ctx.send("there's no active lockdown to undo (or the bot restarted since it was applied).")

        unlocked_count = 0
        for channel_id in locked_ids:
            channel = guild.get_channel(channel_id)
            if channel is None:
                continue
            overwrite = channel.overwrites_for(guild.default_role)
            overwrite.send_messages = None
            try:
                await channel.set_permissions(guild.default_role, overwrite=overwrite)
                unlocked_count += 1
            except discord.Forbidden:
                pass

        self.lockdown_channels.pop(guild.id, None)

        embed = discord.Embed(
            title="server lockdown lifted",
            description=f"unlocked **{unlocked_count}** text channels.",
            color=EMBED_COLOR,
        )
        await ctx.send(embed=embed)

    # ---------------------------- ERROR HANDLING ----------------------------
    @lock.error
    @unlock.error
    @serverlockdown.error
    @serverunlock.error
    async def locks_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("you don't have permission to use this command.")
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("i don't have the required permissions to do that.")
        else:
            await ctx.send(f"an error occurred: {error}")
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Locks(bot))
