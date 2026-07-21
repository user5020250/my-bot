import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn

WHITE = discord.Color(0xFFFFFF)

PADLOCK_DURATION = 24 * 60 * 60


class Use(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="use",
        description="Use an item.",
    )
    async def use(
        self,
        interaction: discord.Interaction,
        item: str,
    ):
        item = item.lower()

        user_id = str(interaction.user.id)

        if not db.has_item(
            user_id,
            item,
        ):
            await interaction.response.send_message(
                f"❌ You don't own `{item}`.",
                ephemeral=True,
            )
            return

        # =========================
        # PADLOCK
        # =========================

        if item == "padlock":

            now = int(time.time())

            conn = get_conn()

            row = conn.execute(
                """
                SELECT protected_until
                FROM business_status
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

            protected_until = 0

            if row:
                protected_until = row["protected_until"]

            if protected_until > now:

                conn.close()

                await interaction.response.send_message(
                    (
                        "❌ You already have an active padlock.\n"
                        f"Remaining: `{db.format_duration(protected_until - now)}`"
                    ),
                    ephemeral=True,
                )

                return

            new_expiry = now + PADLOCK_DURATION

            conn.execute(
                """
                INSERT INTO business_status (
                    user_id,
                    protected_until
                )
                VALUES (?, ?)

                ON CONFLICT(user_id)

                DO UPDATE SET
                    protected_until = excluded.protected_until
                """,
                (
                    user_id,
                    new_expiry,
                ),
            )

            conn.commit()
            conn.close()

            db.remove_inventory(
                user_id,
                "padlock",
                1,
            )

            embed = discord.Embed(
                title="🔒 Padlock Activated",
                color=WHITE,
            )

            embed.add_field(
                name="Protection",
                value="`24h`",
                inline=False,
            )

            embed.add_field(
                name="Expires In",
                value=f"`{db.format_duration(PADLOCK_DURATION)}`",
                inline=False,
            )

            await interaction.response.send_message(
                embed=embed
            )

            return

        await interaction.response.send_message(
            "❌ This item cannot be used.",
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(
        Use(bot)
    )
