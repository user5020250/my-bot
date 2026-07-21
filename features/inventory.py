import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db

WHITE = discord.Color(0xFFFFFF)

ITEMS = {
    "padlock": {
        "emoji": "🔒",
        "name": "Padlock",
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

        items = db.get_all_inventory(user_id)

        embed = discord.Embed(
            title=f"🎒 {interaction.user.display_name}'s Inventory",
            color=WHITE,
        )

        if not items:
            embed.description = "You don't own anything yet."

        else:
            lines = []

            for row in items:
                item_id = row["item"]

                item_data = ITEMS.get(
                    item_id,
                    {
                        "emoji": "📦",
                        "name": item_id.title(),
                    },
                )

                lines.append(
                    f"{item_data['emoji']} "
                    f"**{item_data['name']}** "
                    f"×{row['qty']}"
                )

            embed.description = "\n".join(lines)

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(
        Inventory(bot)
    )
