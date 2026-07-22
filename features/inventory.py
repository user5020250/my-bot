import discord

from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

ITEMS = {
    # ---------------- Protection ----------------

    "padlock": {
        "emoji": "🔒",
        "name": "Padlock",
        "description": "Protects you from /steal for 24 hours.",
        "usable": True,
        "category": "Protection",
    },

    "alarm_system": {
        "emoji": "🚨",
        "name": "Alarm System",
        "description": (
            "Activates automatically. Gives the "
            "thief a longer cooldown if caught."
        ),
        "usable": False,
        "category": "Protection",
    },

    "insurance": {
        "emoji": "🛡️",
        "name": "Insurance",
        "description": (
            "Activates automatically. Refunds "
            "part of the stolen money."
        ),
        "usable": False,
        "category": "Protection",
    },

    # ---------------- Crime ----------------

    "gloves": {
        "emoji": "🧤",
        "name": "Gloves",
        "description": (
            "Increases steal success chance "
            "for your next attempt."
        ),
        "usable": True,
        "category": "Crime",
    },

    "mask": {
        "emoji": "😷",
        "name": "Mask",
        "description": (
            "Lowers the chance of getting caught "
            "for your next steal."
        ),
        "usable": True,
        "category": "Crime",
    },

    "lockpick": {
        "emoji": "🔑",
        "name": "Lockpick",
        "description": (
            "70% chance to break a target's padlock."
        ),
        "usable": True,
        "category": "Crime",
    },

    # ---------------- Consumables ----------------

    "burger": {
        "emoji": "🍔",
        "name": "Burger",
        "description": "Just a burger.",
        "usable": True,
        "category": "Consumables",
    },

    "energy_drink": {
        "emoji": "⚡",
        "name": "Energy Drink",
        "description": "Lets you work again instantly.",
        "usable": True,
        "category": "Consumables",
    },

    "mystery_cash_box": {
        "emoji": "🎁",
        "name": "Mystery Cash Box",
        "description": (
            "Contains a random amount of cash. "
            "Either loses or wins."
        ),
        "usable": True,
        "category": "Consumables",
    },

    "mystery_crate": {
        "emoji": "📦",
        "name": "Mystery Crate",
        "description": "Contains a random item.",
        "usable": True,
        "category": "Consumables",
    },

    # ---------------- Lottery ----------------

    "lottery_ticket": {
        "emoji": "🎟️",
        "name": "Lottery Ticket",
        "description": (
            "Used automatically "
            "when joining lotteries."
        ),
        "usable": False,
        "category": "Lottery",
    },

    # ---------------- Collectibles ----------------

    "diamond": {
        "emoji": "💎",
        "name": "Diamond",
        "description": "An expensive trade item.",
        "usable": False,
        "category": "Collectibles",
    },

    "crown": {
        "emoji": "👑",
        "name": "Crown",
        "description": "A prestige collectible.",
        "usable": False,
        "category": "Collectibles",
    },

    "trophy": {
        "emoji": "🏆",
        "name": "Trophy",
        "description": "An event reward.",
        "usable": False,
        "category": "Collectibles",
    },

    "ancient_coin": {
        "emoji": "🪙",
        "name": "Ancient Coin",
        "description": "A very rare collectible.",
        "usable": False,
        "category": "Collectibles",
    },

    "trade_permit": {
        "emoji": "📜",
        "name": "Trade Permit",
        "description": (
            "Required for trading. Consumed "
            "each time you trade."
        ),
        "usable": False,
        "category": "Collectibles",
    },

    # ---------------- Resources ----------------

    "fish": {
        "emoji": "🐟",
        "name": "Fish",
        "description": "Caught from /fish.",
        "usable": False,
        "category": "Resources",
    },

    "wheat": {
        "emoji": "🌾",
        "name": "Wheat",
        "description": "Harvested from /farm.",
        "usable": False,
        "category": "Resources",
    },

    "copper": {
        "emoji": "🟠",
        "name": "Copper",
        "description": "Mined from /mine.",
        "usable": False,
        "category": "Resources",
    },

    "silver": {
        "emoji": "⚪",
        "name": "Silver",
        "description": "Mined from /mine.",
        "usable": False,
        "category": "Resources",
    },

    "gold": {
        "emoji": "🟡",
        "name": "Gold",
        "description": "Mined from /mine.",
        "usable": False,
        "category": "Resources",
    },

    "raw_diamond": {
        "emoji": "💎",
        "name": "Raw Diamond",
        "description": "Mined from /mine.",
        "usable": False,
        "category": "Resources",
    },

    "obsidian": {
        "emoji": "⬛",
        "name": "Obsidian",
        "description": "Mined from /mine.",
        "usable": False,
        "category": "Resources",
    },
}


class InventoryDropdown(discord.ui.Select):

    def __init__(self, user_id: str):

        self.user_id = user_id

        options = [
            discord.SelectOption(
                label="Protection",
                emoji="🛡️",
            ),
            discord.SelectOption(
                label="Crime",
                emoji="🔪",
            ),
            discord.SelectOption(
                label="Consumables",
                emoji="🍔",
            ),
            discord.SelectOption(
                label="Lottery",
                emoji="🎟️",
            ),
            discord.SelectOption(
                label="Collectibles",
                emoji="💎",
            ),
            discord.SelectOption(
                label="Resources",
                emoji="⛏️",
            ),
        ]

        super().__init__(
            placeholder="Choose a category...",
            options=options,
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ):

        category = self.values[0]

        inventory = db.get_all_inventory(
            self.user_id
        )

        embed = discord.Embed(
            title=f"🎒 {category}",
            color=WHITE,
        )

        found = False

        for row in inventory:

            item_id = row["item"]

            item = ITEMS.get(item_id)

            if not item:
                continue

            if item["category"] != category:
                continue

            found = True

            status = (
                "🟢 Usable"
                if item["usable"]
                else "🔴 Not usable"
            )

            embed.add_field(
                name=(
                    f"{item['emoji']} "
                    f"{item['name']} "
                    f"`{status}`"
                ),
                value=(
                    f"`Qty: {row['qty']}`\n"
                    f"{item['description']}"
                ),
                inline=False,
            )

        if not found:
            embed.description = (
                "You don't own any items in this category."
            )

        await interaction.response.edit_message(
            embed=embed,
            view=self.view,
        )


class InventoryView(discord.ui.View):

    def __init__(self, user_id: str):

        super().__init__(timeout=300)

        self.add_item(
            InventoryDropdown(user_id)
        )


class Inventory(commands.Cog):

    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    @app_commands.command(
        name="inventory",
        description="View everything you own.",
    )
    async def inventory(
        self,
        interaction: discord.Interaction,
    ):

        embed = discord.Embed(
            title=(
                f"🎒 "
                f"{interaction.user.display_name}'s Inventory"
            ),
            description=(
                "Choose a category below."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text="Use /use <item> to use usable items."
        )

        await interaction.response.send_message(
            embed=embed,
            view=InventoryView(
                str(interaction.user.id)
            ),
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Inventory(bot)
    )
