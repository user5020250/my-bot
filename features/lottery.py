import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

OWNER_ID = 843377668488429569


class Lottery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    lottery_group = app_commands.Group(
        name="lottery",
        description="Lottery commands.",
    )

    # ==========================
    # /lottery setchannel
    # ==========================

    @lottery_group.command(
        name="setchannel",
        description="Set the lottery announcement channel.",
    )
    @app_commands.checks.has_permissions(
        administrator=True
    )
    async def setchannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        db.set_lottery_channel(
            str(interaction.guild.id),
            str(channel.id),
        )

        await interaction.response.send_message(
            (
                "✅ Lottery announcements "
                f"will be sent to {channel.mention}."
            )
        )

    # ==========================
    # !createlottery
    # Usage:
    # !createlottery 1m 1d
    # !createlottery 500k 12h
    # ==========================

    @commands.command(
        name="createlottery",
    )
    async def create_lottery(
        self,
        ctx: commands.Context,
        prize: str,
        duration: str,
    ):
        if ctx.author.id != OWNER_ID:
            return

        try:
            prize = db.parse_money(
                prize
            )

        except ValueError:

            await ctx.send(
                "❌ Invalid amount.\n"
                "Examples:\n"
                "`500k`\n"
                "`2m`\n"
                "`1b`"
            )
            return

        if db.get_lottery() is not None:

            await ctx.send(
                "❌ There is already an active lottery."
            )
            return

        duration = duration.lower()

        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
        }

        unit = duration[-1]

        if unit not in multipliers:

            await ctx.send(
                "❌ Invalid duration.\n"
                "Examples:\n"
                "`30s`\n"
                "`15m`\n"
                "`12h`\n"
                "`1d`"
            )
            return

        try:
            amount = int(
                duration[:-1]
            )

        except ValueError:

            await ctx.send(
                "❌ Invalid duration."
            )
            return

        if amount <= 0:

            await ctx.send(
                "❌ Duration must be greater than 0."
            )
            return

        ends_at = int(time.time()) + (
            amount * multipliers[unit]
        )

        db.create_lottery(
            prize,
            ends_at,
        )

        embed = discord.Embed(
            title="🎟️ New Lottery",
            description=(
                f"💰 Prize: "
                f"**{db.format_peso(prize)}**\n"
                f"⏳ Ends: "
                f"<t:{ends_at}:R>\n\n"
                f"Use `/lottery join` "
                f"to enter."
            ),
            color=WHITE,
        )

        channels = db.get_all_lottery_channels()

        for data in channels:

            channel = self.bot.get_channel(
                int(
                    data["channel_id"]
                )
            )

            if channel is None:
                continue

            try:

                await channel.send(
                    embed=embed
                )

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        await ctx.send(
            "✅ Lottery created."
        )

    # ==========================
    # /lottery info
    # ==========================

    @lottery_group.command(
        name="info",
        description="View the current lottery.",
    )
    async def lottery_info(
        self,
        interaction: discord.Interaction,
    ):
        lottery = db.get_lottery()

        if lottery is None:

            await interaction.response.send_message(
                "❌ No active lottery.",
                ephemeral=True,
            )
            return

        entries = db.get_lottery_entries()

        total_tickets = sum(
            entry["tickets"]
            for entry in entries
        )

        now = int(
            time.time()
        )

        if lottery["ends_at"] <= now:

            status_text = (
                "❌ Lottery Ended"
            )

        else:

            status_text = (
                f"⏳ Ends: "
                f"<t:{lottery['ends_at']}:R>"
            )

        embed = discord.Embed(
            title="🎟️ Current Lottery",
            description=(
                f"💰 Prize: "
                f"**{db.format_peso(lottery['prize'])}**\n"
                f"🎫 Total Tickets: "
                f"**{total_tickets:,}**\n"
                f"{status_text}"
            ),
            color=WHITE,
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ==========================
    # /lottery join
    # ==========================

    @lottery_group.command(
        name="join",
        description="Join the current lottery.",
    )
    @app_commands.describe(
        tickets="How many tickets to use",
    )
    async def join_lottery(
        self,
        interaction: discord.Interaction,
        tickets: int = 1,
    ):
        lottery = db.get_lottery()

        if lottery is None:

            await interaction.response.send_message(
                "❌ No active lottery.",
                ephemeral=True,
            )
            return

        if tickets <= 0:

            await interaction.response.send_message(
                "❌ Invalid ticket amount.",
                ephemeral=True,
            )
            return

        success = db.join_lottery(
            str(
                interaction.user.id
            ),
            tickets,
        )

        if not success:

            await interaction.response.send_message(
                "❌ You don't have enough lottery tickets.",
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                "🎟️ You joined with "
                f"**{tickets}** ticket(s)."
            )
        )

    # ==========================
    # !drawlottery
    # ==========================

    @commands.command(
        name="drawlottery",
        aliases=[
            "lotterydraw",
        ],
    )
    async def draw_lottery(
        self,
        ctx: commands.Context,
    ):
        if ctx.author.id != OWNER_ID:
            return

        lottery = db.get_lottery()

        if lottery is None:

            await ctx.send(
                "❌ No active lottery."
            )
            return

        entries = db.get_lottery_entries()

        if not entries:

            db.end_lottery()

            await ctx.send(
                "❌ Nobody joined the lottery."
            )
            return

        pool = []

        for entry in entries:

            pool.extend(
                [entry["user_id"]]
                * entry["tickets"]
            )

        winner_id = random.choice(
            pool
        )

        db.add_balance(
            winner_id,
            lottery["prize"],
        )

        db.end_lottery()

        embed = discord.Embed(
            title="🎉 Lottery Winner",
            color=WHITE,
        )

        embed.add_field(
            name="Winner",
            value=(
                f"<@{winner_id}>"
            ),
            inline=False,
        )

        embed.add_field(
            name="Prize",
            value=db.format_peso(
                lottery["prize"]
            ),
            inline=False,
        )

        channels = db.get_all_lottery_channels()

        for data in channels:

            channel = self.bot.get_channel(
                int(
                    data["channel_id"]
                )
            )

            if channel is None:
                continue

            try:

                await channel.send(
                    embed=embed
                )

            except (
                discord.Forbidden,
                discord.HTTPException,
            ):
                pass

        await ctx.send(
            embed=embed
        )


async def setup(
    bot,
):
    cog = Lottery(
        bot
    )

    await bot.add_cog(
        cog
    )

    try:

        bot.tree.add_command(
            cog.lottery_group
        )

    except app_commands.CommandAlreadyRegistered:
        pass
