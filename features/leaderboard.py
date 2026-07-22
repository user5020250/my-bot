import traceback

import discord
from discord import app_commands
from discord.ext import commands
from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)
LEADERBOARD_LIMIT = 10
MEDALS = {
    1: "🥇",
    2: "🥈",
    3: "🥉",
}


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------- /leaderboard
    @app_commands.command(
        name="leaderboard",
        description="Show the richest users.",
    )
    async def leaderboard(
        self,
        interaction: discord.Interaction,
    ):
        try:
            conn = get_conn()
            # Make sure rows are dict-like so row["user_id"] works even
            # if get_conn() doesn't already set this. If your database.py
            # already sets row_factory = sqlite3.Row globally, this is a
            # harmless no-op.
            import sqlite3
            conn.row_factory = sqlite3.Row

            rows = conn.execute(
                """
                SELECT id, balance
                FROM users
                ORDER BY balance DESC
                LIMIT ?
                """,
                (LEADERBOARD_LIMIT,),
            ).fetchall()
            conn.close()

            if not rows:
                await interaction.response.send_message(
                    "📉 No users found yet."
                )
                return

            lines = []
            for rank, row in enumerate(rows, start=1):
                prefix = MEDALS.get(rank, f"`#{rank}`")
                lines.append(
                    f"{prefix} <@{row['id']}> — "
                    f"**{db.format_peso(row['balance'])}**"
                )

            embed = discord.Embed(
                title="🏆 Richest Players",
                description="\n".join(lines),
                color=WHITE,
            )

            requester_id = str(interaction.user.id)
            requester_user = db.get_user(requester_id)

            if requester_user is None:
                # Fallback in case the requester has no row yet in `users`.
                embed.set_footer(text="💰 Your balance: ₱0.00")
            else:
                embed.set_footer(
                    text=f"💰 Your balance: {db.format_peso(requester_user['balance'])}"
                )

            await interaction.response.send_message(embed=embed)

        except Exception as e:
            traceback.print_exc()
            error_msg = f"⚠️ Something went wrong: `{e}`"
            if interaction.response.is_done():
                await interaction.followup.send(error_msg, ephemeral=True)
            else:
                await interaction.response.send_message(error_msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Leaderboard(bot)
    )
