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
        conn = get_conn()

        # NOTE: assumes the `users` table has a `user_id` column storing
        # the Discord user ID as text, matching the `lender`/`borrower`
        # convention used elsewhere (e.g. loans.py). Rename here if your
        # schema uses a different column name (e.g. `id`, `discord_id`).
        rows = conn.execute(
            """
            SELECT user_id, balance
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
                f"{prefix} <@{row['user_id']}> — "
                f"**{db.format_peso(row['balance'])}**"
            )

        embed = discord.Embed(
            title="🏆 Richest Players",
            description="\n".join(lines),
            color=WHITE,
        )

        requester_id = str(interaction.user.id)
        requester_user = db.get_user(requester_id)

        embed.set_footer(
            text=f"💰 Your balance: {db.format_peso(requester_user['balance'])}"
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Leaderboard(bot)
    )
