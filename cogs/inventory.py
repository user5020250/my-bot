import discord

from discord import app_commands
from discord.ext import commands

from database import get_conn

WHITE = discord.Color(0xFFFFFF)

ITEMS = {
    "rice": {
        "label": "Rice",
        "unit": "kg",
    },
    "fish": {
        "label": "Fish",
        "unit": "kg",
    },
    "mangoes": {
        "label": "Mangoes",
        "unit": "kg",
    },
    "chicken": {
        "label": "Chicken",
        "unit": "kg",
    },
    "meat": {
        "label": "Meat",
        "unit": "kg",
    },
    "vegetables": {
        "label": "Vegetables",
        "unit": "kg",
    },
}


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
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

        conn = get_conn()

        rows = conn.execute(
            """
            SELECT item, qty
            FROM inventory
            WHERE user_id = ?
            AND qty > 0
            ORDER BY item
            """,
            (user_id,),
        ).fetchall()

        conn.close()

        if not rows:
            await interaction.response.send_message(
                "You don't own anything yet."
            )
            return

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=WHITE,
        )

        for row in rows:
            item = row["item"]
            qty = row["qty"]

            if item == "load":
                name = "Load"
                unit = "units"

            elif item in ITEMS:
                name = ITEMS[item]["label"]
                unit = ITEMS[item]["unit"]

            else:
                name = item.title()
                unit = "pcs"

            embed.add_field(
                name=name,
                value=f"{qty} {unit}",
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Inventory(bot)
    )
