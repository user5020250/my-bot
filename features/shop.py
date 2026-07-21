import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn

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
        """
        SELECT protected_until
        FROM business_status
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    return row["protected_until"] if row else 0


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------------------------------------------------------------
    # /balance
    # ---------------------------------------------------------------

    @app_commands.command(
        name="balance",
        description="Check your balance.",
    )
    @app_commands.describe(
        member="Whose balance to check"
    )
    async def balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        user = db.get_user(
            str(member.id)
        )

        embed = discord.Embed(
            title=f"{member.display_name}'s Balance",
            color=WHITE,
        )

        embed.add_field(
            name="💰 Money",
            value=db.format_peso(
                user["balance"]
            ),
            inline=False,
        )

        protected_until = get_protected_until(
            str(member.id)
        )

        now = int(
            time.time()
        )

        if protected_until > now:
            embed.add_field(
                name="🔒 Protection",
                value=(
                    db.format_duration(
                        protected_until - now
                    )
                ),
                inline=False,
            )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ---------------------------------------------------------------
    # /shop
    # ---------------------------------------------------------------

    @app_commands.command(
        name="shop",
        description="View the shop.",
    )
    async def shop(
        self,
        interaction: discord.Interaction,
    ):
        embed = discord.Embed(
            title="🛒 Shop",
            description="Use `/buy <item>` to purchase items.",
            color=WHITE,
        )

        for item_id, item in SHOP_ITEMS.items():
            embed.add_field(
                name=(
                    f"{item['emoji']} "
                    f"{item['name']} "
                    f"— "
                    f"{db.format_peso(item['cost'])}"
                ),
                value=(
                    f"{item['description']}\n"
                    f"ID: `{item_id}`"
                ),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )

    # ---------------------------------------------------------------
    # /buy
    # ---------------------------------------------------------------

    @app_commands.command(
        name="buy",
        description="Buy an item.",
    )
    @app_commands.describe(
        item="Item ID"
    )
    async def buy(
        self,
        interaction: discord.Interaction,
        item: str,
    ):
        item = item.lower()

        if item not in SHOP_ITEMS:
            await interaction.response.send_message(
                (
                    f"❌ `{item}` doesn't exist.\n"
                    "Use `/shop`."
                ),
                ephemeral=True,
            )
            return

        shop_item = SHOP_ITEMS[item]

        user_id = str(
            interaction.user.id
        )

        user = db.get_user(
            user_id
        )

        if user["balance"] < shop_item["cost"]:
            await interaction.response.send_message(
                (
                    "❌ You don't have enough money.\n\n"
                    f"Needed: {db.format_peso(shop_item['cost'])}\n"
                    f"Balance: {db.format_peso(user['balance'])}"
                ),
                ephemeral=True,
            )
            return

        new_balance = db.add_balance(
            user_id,
            -shop_item["cost"],
        )

        db.add_inventory(
            user_id,
            item,
            1,
            buy_price=shop_item["cost"],
        )

        await interaction.response.send_message(
            (
                f"✅ Bought "
                f"{shop_item['emoji']} "
                f"**{shop_item['name']}**.\n\n"
                f"New balance: "
                f"**{db.format_peso(new_balance)}**.\n\n"
                f"Use `/inventory` to see it."
            )
        )


async def setup(bot):
    await bot.add_cog(
        Shop(bot)
    )
