import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

PADLOCK_COST = 50_000
PADLOCK_DURATION_SECONDS = 24 * 60 * 60

SHOP_ITEMS = {
    "padlock": {
        "name": "Padlock",
        "emoji": "🔒",
        "cost": PADLOCK_COST,
        "description": (
            f"Protects your balance from /steal for "
            f"{PADLOCK_DURATION_SECONDS // 3600} hours."
        ),
    },
}


def get_protected_until(user_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        "SELECT protected_until FROM business_status WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    return row["protected_until"] if row else 0


def set_protected_until(user_id: str, until_ts: int) -> None:
    conn = get_conn()

    conn.execute(
        """
        INSERT INTO business_status (
            user_id,
            protected_until
        )
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET protected_until = excluded.protected_until
        """,
        (
            user_id,
            until_ts,
        ),
    )

    conn.commit()
    conn.close()


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ---------------------------------------------------------------
    # /balance
    # ---------------------------------------------------------------
    @app_commands.command(
        name="balance",
        description="Check your (or someone else's) balance.",
    )
    @app_commands.describe(member="Whose balance to check (default: yourself)")
    async def balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None,
    ):
        member = member or interaction.user
        user = db.get_user(str(member.id))

        embed = discord.Embed(
            title=f"{member.display_name}'s Balance",
            color=WHITE,
        )

        embed.add_field(
            name="Balance",
            value=db.format_peso(user["balance"]),
            inline=False,
        )

        protected_until = get_protected_until(str(member.id))
        now = int(time.time())

        if protected_until > now:
            embed.add_field(
                name="🔒 Protected",
                value=f"{db.format_duration(protected_until - now)} remaining",
                inline=False,
            )

        embed.set_thumbnail(url=member.display_avatar.url)

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------------
    # /shop
    # ---------------------------------------------------------------
    @app_commands.command(
        name="shop",
        description="View items available for purchase.",
    )
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🛒 Shop",
            description="Use `/buy <item>` to purchase.",
            color=WHITE,
        )

        for key, item in SHOP_ITEMS.items():
            embed.add_field(
                name=f"{item['emoji']} {item['name']} — {db.format_peso(item['cost'])}",
                value=f"{item['description']}\nID: `{key}`",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------------
    # /buy
    # ---------------------------------------------------------------
    @app_commands.command(
        name="buy",
        description="Buy an item from the shop.",
    )
    @app_commands.describe(item="The item ID to purchase (see /shop)")
    async def buy(self, interaction: discord.Interaction, item: str):
        item = item.lower()

        if item not in SHOP_ITEMS:
            await interaction.response.send_message(
                f"❌ `{item}` isn't a valid shop item. Check `/shop` for options.",
                ephemeral=True,
            )
            return

        shop_item = SHOP_ITEMS[item]
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)

        if user["balance"] < shop_item["cost"]:
            await interaction.response.send_message(
                f"❌ You need {db.format_peso(shop_item['cost'])} but only have "
                f"{db.format_peso(user['balance'])}.",
                ephemeral=True,
            )
            return

        new_balance = db.add_balance(user_id, -shop_item["cost"])

        if item == "padlock":
            now = int(time.time())
            current = get_protected_until(user_id)
            # Stack onto existing protection if it's still active.
            start = current if current > now else now
            set_protected_until(user_id, start + PADLOCK_DURATION_SECONDS)

        await interaction.response.send_message(
            f"✅ Bought {shop_item['emoji']} **{shop_item['name']}** for "
            f"{db.format_peso(shop_item['cost'])}. New balance: "
            f"{db.format_peso(new_balance)}."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
