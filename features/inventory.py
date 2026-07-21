import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn

WHITE = discord.Color(0xFFFFFF)


class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="inventory",
        description="View everything you own."
    )
    async def inventory(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        conn = get_conn()

        items = conn.execute(
            """
            SELECT item, qty
            FROM inventory
            WHERE user_id = ?
            """,
            (user_id,)
        ).fetchall()

        conn.close()

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Inventory",
            color=WHITE,
        )

        if not items:
            embed.description = "You don't own anything yet."

        else:
            for item in items:
                embed.add_field(
                    name=item["item"].title(),
                    value=f"x{item['qty']}",
                    inline=False,
                )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot):
    await bot.add_cog(Inventory(bot))
