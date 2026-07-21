import discord
from discord import app_commands
from discord.ext import commands
import db_utils as db
WHITE = discord.Color(0xFFFFFF)
ITEMS = {
    "padlock": {
        "emoji": "🔒",
        "name": "Padlock",
        "description": (
            "Protects you from /steal "
            "for 24 hours."
        ),
        "usable": True,
    },
    "lottery_ticket": {
        "emoji": "🎟️",
        "name": "Lottery Ticket",
        "description": (
            "Used automatically "
            "when joining lotteries."
        ),
        "usable": False,
    },
    "burger": {
        "emoji": "🍔",
        "name": "Burger",
        "description": (
            "Just a burger."
        ),
        "usable": True,
    },
    "alarm_system": {
        "emoji": "🚨",
        "name": "Alarm System",
        "description": (
            "Activates automatically. Gives the "
            "thief a longer cooldown if caught."
        ),
        "usable": False,
    },
    "insurance": {
        "emoji": "🛡️",
        "name": "Insurance",
        "description": (
            "Activates automatically. Refunds "
            "part of the stolen money."
        ),
        "usable": False,
    },
    "gloves": {
        "emoji": "🧤",
        "name": "Gloves",
        "description": (
            "Increases steal success chance "
            "for your next attempt."
        ),
        "usable": True,
    },
    "mask": {
        "emoji": "😷",
        "name": "Mask",
        "description": (
            "Lowers the chance of getting caught "
            "for your next steal."
        ),
        "usable": True,
    },
    "lockpick": {
        "emoji": "🔑",
        "name": "Lockpick",
        "description": (
            "70% chance to break a target's padlock."
        ),
        "usable": True,
    },
    "energy_drink": {
        "emoji": "⚡",
        "name": "Energy Drink",
        "description": (
            "Lets you work again instantly."
        ),
        "usable": True,
    },
    "mystery_cash_box": {
        "emoji": "🎁",
        "name": "Mystery Cash Box",
        "description": (
            "Contains a random amount of cash. "
            "Either loses or wins."
        ),
        "usable": True,
    },
    "diamond": {
        "emoji": "💎",
        "name": "Diamond",
        "description": (
            "An expensive trade item."
        ),
        "usable": False,
    },
    "crown": {
        "emoji": "👑",
        "name": "Crown",
        "description": (
            "A prestige collectible."
        ),
        "usable": False,
    },
    "trophy": {
        "emoji": "🏆",
        "name": "Trophy",
        "description": (
            "An event reward."
        ),
        "usable": False,
    },
    "mystery_crate": {
        "emoji": "📦",
        "name": "Mystery Crate",
        "description": (
            "Contains a random item."
        ),
        "usable": True,
    },
    "ancient_coin": {
        "emoji": "🪙",
        "name": "Ancient Coin",
        "description": (
            "A very rare collectible."
        ),
        "usable": False,
    },
    "trade_permit": {
        "emoji": "📜",
        "name": "Trade Permit",
        "description": (
            "Required for trading. Consumed "
            "each time you trade."
        ),
        "usable": False,
    },
}
class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    @app_commands.command(
        name="inventory",
        description="View everything you own.",
    )
    async def inventory(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)
        items = db.get_all_inventory(
            user_id
        )
        embed = discord.Embed(
            title=(
                f"🎒 "
                f"{interaction.user.display_name}'s Inventory"
            ),
            color=WHITE,
        )
        if not items:
            embed.description = (
                "You don't own anything yet."
            )
        else:
            for row in items:
                item_id = row["item"]
                item_data = ITEMS.get(
                    item_id,
                    {
                        "emoji": "📦",
                        "name": item_id.title(),
                        "description": (
                            "No description available."
                        ),
                        "usable": False,
                    },
                )
                status = (
                    "🟢 Usable"
                    if item_data["usable"]
                    else "🔴 Not usable"
                )
                embed.add_field(
                    name=(
                        f"{item_data['emoji']} "
                        f"{item_data['name']} "
                        f"`{status}`"
                    ),
                    value=(
                        f"`Qty: {row['qty']}`\n"
                        f"`{item_data['description']}`"
                    ),
                    inline=False,
                )
        embed.set_footer(
            text="Use `/use <item>` to use usable items."
        )
        await interaction.response.send_message(
            embed=embed
        )
async def setup(bot):
    await bot.add_cog(
        Inventory(bot)
    )
