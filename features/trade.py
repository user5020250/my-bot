import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)


class Trade(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="trade",
        description="Give an item to another player. Requires a Trade Permit.",
    )
    @app_commands.describe(
        target="Who to send the item to",
        item="Item to send",
        qty="How many to send",
    )
    async def trade(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
        item: str,
        qty: app_commands.Range[int, 1] = 1,
    ):
        item = item.lower()
        sender_id = str(interaction.user.id)
        target_id = str(target.id)

        if target_id == sender_id:
            await interaction.response.send_message(
                "🚫 You can't trade with yourself.",
                ephemeral=True,
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "🤖 You can't trade with bots.",
                ephemeral=True,
            )
            return

        if not db.has_item(
            sender_id,
            "trade_permit",
            1,
        ):
            await interaction.response.send_message(
                "❌ You need a `Trade Permit` to trade items.",
                ephemeral=True,
            )
            return

        if item == "trade_permit":
            await interaction.response.send_message(
                "❌ Trade Permits can't be traded away.",
                ephemeral=True,
            )
            return

        if not db.has_item(
            sender_id,
            item,
            qty,
        ):
            await interaction.response.send_message(
                f"❌ You don't own `{qty}` of `{item}`.",
                ephemeral=True,
            )
            return

        db.remove_inventory(
            sender_id,
            "trade_permit",
            1,
        )

        db.remove_inventory(
            sender_id,
            item,
            qty,
        )

        db.add_inventory(
            target_id,
            item,
            qty,
        )

        embed = discord.Embed(
            title="📜 Trade Complete",
            description=(
                f"{interaction.user.mention} sent "
                f"**{qty}x `{item}`** to {target.mention}."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text="A Trade Permit was consumed for this trade."
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Trade(bot)
    )
