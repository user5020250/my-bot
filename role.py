"""
roles
type a word (e.g. "abracadabra") in the roles channel to get the matching role.
no command needed - just send the word. edit ROLE_MAP in config.py to add more.
"""

import discord
from discord.ext import commands

from .config import ROLE_CHANNEL_ID, ROLE_MAP, CONFIRMATION_DELETE_AFTER, ERROR_DELETE_AFTER


class RoleAssign(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.author.bot:
            return
        if message.channel.id != ROLE_CHANNEL_ID:
            return

        content = message.content.strip().lower()

        if content not in ROLE_MAP:
            return  # not a recognized word, ignore silently

        role_id = ROLE_MAP[content]
        role = message.guild.get_role(role_id)

        # Delete the triggering message first so the channel stays clean
        # even if something below goes wrong.
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

        if role is None:
            return await self._send_temp(
                message.channel,
                f"{message.author.mention} that role isn't set up correctly (role not found). let a mod know.",
                ERROR_DELETE_AFTER,
            )

        member = message.author

        if role in member.roles:
            return await self._send_temp(
                message.channel,
                f"{member.mention} you already have **{role.name}**.",
                ERROR_DELETE_AFTER,
            )

        other_roles = [
            message.guild.get_role(rid)
            for rid in ROLE_MAP.values()
            if rid != role_id
        ]
        roles_to_remove = [r for r in other_roles if r and r in member.roles]

        try:
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="switching role")
            await member.add_roles(role, reason="self-assigned role")
        except discord.Forbidden:
            return await self._send_temp(
                message.channel,
                f"{member.mention} i don't have permission to manage that role. "
                "make sure my role is above the assignable roles in server settings.",
                ERROR_DELETE_AFTER,
            )

        await self._send_temp(
            message.channel,
            f"**{role.name}** role has been added to your profile",
            CONFIRMATION_DELETE_AFTER,
        )

    @staticmethod
    async def _send_temp(channel: discord.abc.Messageable, content: str, delete_after: int):
        try:
            await channel.send(content, delete_after=delete_after)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(RoleAssign(bot))