"""
embeds
!embed [#channel] [title] | [desc]                  shortcut: !em
!editembed [#channel] [message_id] [title] | [desc]  shortcut: !ee
!message [#channel] [message]                        shortcut: !m
"""

import asyncio

import discord
from discord import app_commands
from discord.ext import commands

from .config import EMBED_COLOR


class Embeds(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    def _split_title_description(content: str):
        if "|" in content:
            title, description = content.split("|", 1)
            title = title.strip() or None
            description = description.strip()
        else:
            title, description = None, content.strip()
        return title, description

    # ---------------------------- MESSAGE (send plain text as bot) ----------------------------
    @commands.command(name="message", aliases=["m"])
    @commands.has_permissions(manage_messages=True)
    async def message(self, ctx: commands.Context, channel: discord.TextChannel, *, message: str):
        """usage: !message #channel your message here (or !m #channel your message here)"""
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages:
            return await ctx.send(f"i don't have permission to send messages in {channel.mention}.")

        try:
            await channel.send(message)
        except discord.Forbidden:
            return await ctx.send(f"i don't have permission to send messages in {channel.mention}.")
        except discord.HTTPException as e:
            return await ctx.send(f"failed to send message: {e}")

        if channel.id != ctx.channel.id:
            await ctx.send(f"message sent to {channel.mention}.")

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ---------------------------- MESSAGE (slash command version) ----------------------------
    @app_commands.command(name="message", description="send a message as the bot in this channel")
    @app_commands.describe(message="the message to send")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def slash_message(self, interaction: discord.Interaction, message: str):
        """usage: /message message:<your message here> — sends in the channel the command was used in"""
        channel = interaction.channel
        perms = channel.permissions_for(interaction.guild.me)
        if not perms.send_messages:
            return await interaction.response.send_message(
                "i don't have permission to send messages in this channel.", ephemeral=True
            )

        try:
            await channel.send(message)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "i don't have permission to send messages in this channel.", ephemeral=True
            )
        except discord.HTTPException as e:
            return await interaction.response.send_message(f"failed to send message: {e}", ephemeral=True)

        await interaction.response.send_message("message sent.", ephemeral=True)
        await asyncio.sleep(3)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

    @slash_message.error
    async def slash_message_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            msg = "you don't have permission to use this command."
        else:
            msg = f"an error occurred: {error}"

        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)

    # ---------------------------- EMBED (send) ----------------------------
    @commands.command(name="embed", aliases=["em"])
    @commands.has_permissions(manage_messages=True)
    async def embed(self, ctx: commands.Context, channel: discord.TextChannel, *, content: str):
        """usage: !embed #channel title here | desc here"""
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send(f"i don't have permission to send embeds in {channel.mention}.")

        title, description = self._split_title_description(content)

        embed = discord.Embed(
            title=title,
            description=description,
            color=EMBED_COLOR,
        )

        try:
            sent_msg = await channel.send(embed=embed)
        except discord.Forbidden:
            return await ctx.send(f"i don't have permission to send embeds in {channel.mention}.")
        except discord.HTTPException as e:
            return await ctx.send(f"failed to send embed: {e}")

        await ctx.send(
            f"embed sent to {channel.mention}.\n"
            f"message id: `{sent_msg.id}` — save this if you want to edit it later with "
            f"`!editembed {channel.mention} {sent_msg.id} <new content>`."
        )

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ---------------------------- EDITEMBED ----------------------------
    @commands.command(name="editembed", aliases=["ee"])
    @commands.has_permissions(manage_messages=True)
    async def editembed(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        message_id: int,
        *,
        content: str,
    ):
        """usage: !editembed #channel <message_id> new title here | new description here"""
        try:
            target_msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            return await ctx.send("couldn't find a message with that id in that channel.")
        except discord.Forbidden:
            return await ctx.send(f"i don't have permission to read messages in {channel.mention}.")

        if target_msg.author.id != self.bot.user.id:
            return await ctx.send("i can only edit embeds that i sent myself.")
        if not target_msg.embeds:
            return await ctx.send("that message doesn't contain an embed to edit.")

        title, description = self._split_title_description(content)
        old_embed = target_msg.embeds[0]

        new_embed = discord.Embed(
            title=title if title is not None else old_embed.title,
            description=description,
            color=old_embed.color or EMBED_COLOR,
        )
        if old_embed.thumbnail:
            new_embed.set_thumbnail(url=old_embed.thumbnail.url)
        if old_embed.image:
            new_embed.set_image(url=old_embed.image.url)
        if old_embed.footer:
            new_embed.set_footer(text=old_embed.footer.text, icon_url=old_embed.footer.icon_url)
        if old_embed.author:
            new_embed.set_author(name=old_embed.author.name, icon_url=old_embed.author.icon_url)

        try:
            await target_msg.edit(embed=new_embed)
        except discord.Forbidden:
            return await ctx.send("i don't have permission to edit that message.")
        except discord.HTTPException as e:
            return await ctx.send(f"failed to edit embed: {e}")

        await ctx.send(f"embed edited in {channel.mention}.")

        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    # ---------------------------- ERROR HANDLING ----------------------------
    @message.error
    @embed.error
    @editembed.error
    async def embeds_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("you don't have permission to use this command.")
        elif isinstance(error, commands.ChannelNotFound):
            await ctx.send("couldn't find that channel. try mentioning it like #general.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("invalid message id — make sure you're passing a valid numeric message id.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"missing argument: `{error.param.name}`.")
        else:
            await ctx.send(f"an error occurred: {error}")
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Embeds(bot))