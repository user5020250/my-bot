"""
Utility Cog for discord.py (v2.x)
-----------------------------------
Provides: serverinfo, avatar

Setup: save as `utility.py` inside your `cogs/` folder, then load it in
main.py the same way as moderation.py:
    await bot.load_extension("cogs.utility")
"""

import discord
from discord.ext import commands


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------- SERVERINFO ----------------------------
    @commands.command(name="serverinfo")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild

        embed = discord.Embed(
            title=f"{guild.name}",
            color=discord.Color.blurple(),
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="Members", value=str(guild.member_count), inline=True)
        embed.add_field(name="Created On", value=guild.created_at.strftime("%B %d, %Y"), inline=True)
        embed.add_field(name="Text Channels", value=str(len(guild.text_channels)), inline=True)
        embed.add_field(name="Voice Channels", value=str(len(guild.voice_channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Boost Level", value=str(guild.premium_tier), inline=True)
        embed.add_field(name="Boosts", value=str(guild.premium_subscription_count), inline=True)
        embed.set_footer(text=f"Server ID: {guild.id}")

        await ctx.send(embed=embed)

    # ---------------------------- AVATAR ----------------------------
    @commands.command(name="avatar")
    async def avatar(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author  # default to the command author if no one is mentioned

        embed = discord.Embed(
            title=f"{member.display_name}'s Avatar",
            color=discord.Color.blurple(),
        )
        embed.set_image(url=member.display_avatar.url)

        await ctx.send(embed=embed)

    @avatar.error
    async def avatar_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MemberNotFound):
            await ctx.send("Couldn't find that member.")
        else:
            await ctx.send(f"An error occurred: {error}")
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Utility(bot))