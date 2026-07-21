import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn

WHITE = discord.Color(0xFFFFFF)

PADLOCK_DURATION_SECONDS = 24 * 60 * 60
SHOP_REFRESH_SECONDS = 5 * 60

SHOP_ITEMS = {
    "padlock": {
        "name": "Padlock",
        "emoji": "🔒",
        "cost": 5000,
        "description": "Protects you from /steal for 24 hours.",
        "min_stock": 1,
        "max_stock": 3,
    },

    "lottery_ticket": {
        "name": "Lottery Ticket",
        "emoji": "🎟️",
        "cost": 10_000,
        "description": "Might be useful in the future.",
        "min_stock": 0,
        "max_stock": 5,
    },

    "burger": {
        "name": "Burger",
        "emoji": "🍔",
        "cost": 500,
        "description": "Just a burger.",
        "min_stock": 1,
        "max_stock": 10,
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


def refresh_item_stock(item_id: str):
    item = SHOP_ITEMS[item_id]

    stock = random.randint(
        item["min_stock"],
        item["max_stock"],
    )

    now = int(time.time())

    conn = get_conn()

    conn.execute(
        """
        INSERT INTO shop_stock (
            item,
            stock,
            last_refresh
        )
        VALUES (?, ?, ?)

        ON CONFLICT(item)

        DO UPDATE SET
            stock = excluded.stock,
            last_refresh = excluded.last_refresh
        """,
        (
            item_id,
            stock,
            now,
        ),
    )

    conn.commit()
    conn.close()


def refresh_shop():
    now = int(time.time())

    conn = get_conn()

    for item_id in SHOP_ITEMS:

        row = conn.execute(
            """
            SELECT last_refresh
            FROM shop_stock
            WHERE item = ?
            """,
            (item_id,),
        ).fetchone()

        if row is None:
            refresh_item_stock(item_id)
            continue

        elapsed = now - row["last_refresh"]

        if elapsed >= SHOP_REFRESH_SECONDS:
            refresh_item_stock(item_id)

    conn.close()


def get_item_stock(item_id: str) -> int:
    conn = get_conn()

    row = conn.execute(
        """
        SELECT stock
        FROM shop_stock
        WHERE item = ?
        """,
        (item_id,),
    ).fetchone()

    conn.close()

    if row is None:
        return 0

    return row["stock"]


def remove_stock(item_id: str):
    conn = get_conn()

    conn.execute(
        """
        UPDATE shop_stock
        SET stock = stock - 1
        WHERE item = ?
        """,
        (item_id,),
    )

    conn.commit()
    conn.close()


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ==========================
    # /balance
    # ==========================

    @app_commands.command(
        name="balance",
        description="Check your balance.",
    )
    async def balance(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        user = db.get_user(str(member.id))

        embed = discord.Embed(
            title=f"{member.display_name}'s Balance",
            color=WHITE,
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="💰 Wallet",
            value=f"`{db.format_peso(user['balance'])}`",
            inline=False,
        )

        protected_until = get_protected_until(
            str(member.id)
        )

        now = int(time.time())

        if protected_until > now:
            embed.add_field(
                name="🔒 Padlock",
                value=f"`{db.format_duration(protected_until - now)}`",
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed
        )

    # ==========================
    # /shop
    # ==========================

    @app_commands.command(
        name="shop",
        description="Browse the shop.",
    )
    async def shop(
        self,
        interaction: discord.Interaction,
    ):
        refresh_shop()

        embed = discord.Embed(
            title="🛒 Shop",
            description=(
                "Use `/buy <item> <qty>`."
            ),
            color=WHITE,
        )

        for item_id, item in SHOP_ITEMS.items():

            stock = get_item_stock(item_id)

            embed.add_field(
                name=(
                    f"{item['emoji']} "
                    f"{item['name']}"
                ),
                value=(
                    f"Price: `{db.format_peso(item['cost'])}`\n"
                    f"Stock: `{stock}`\n"
                    f"{item['description']}\n"
                    f"ID: `{item_id}`"
                ),
                inline=False,
            )

        embed.set_footer(
            text="Stock refreshes every `5 minutes`."
        )

        await interaction.response.send_message(
            embed=embed
        )

# ==========================
# /buy
# ==========================

@app_commands.command(
    name="buy",
    description="Buy an item.",
)
@app_commands.describe(
    item="Item to buy",
    qty="How many to buy",
)
async def buy(
    self,
    interaction: discord.Interaction,
    item: str,
    qty: int = 1,
):
    item = item.lower()

    refresh_shop()

    if qty <= 0:

        await interaction.response.send_message(
            "❌ Quantity must be greater than 0.",
            ephemeral=True,
        )
        return

    if item not in SHOP_ITEMS:

        await interaction.response.send_message(
            "❌ Item not found.",
            ephemeral=True,
        )
        return

    shop_item = SHOP_ITEMS[item]

    stock = get_item_stock(item)

    if stock <= 0:

        await interaction.response.send_message(
            "❌ This item is out of stock.",
            ephemeral=True,
        )
        return

    if qty > stock:

        await interaction.response.send_message(
            (
                f"❌ There are only "
                f"`{stock}` "
                f"`{shop_item['name']}` left."
            ),
            ephemeral=True,
        )
        return

    total_cost = shop_item["cost"] * qty

    user_id = str(interaction.user.id)

    user = db.get_user(user_id)

    if user["balance"] < total_cost:

        await interaction.response.send_message(
            (
                f"❌ You need "
                f"`{db.format_peso(total_cost)}`.\n"
                f"Current balance: "
                f"`{db.format_peso(user['balance'])}`"
            ),
            ephemeral=True,
        )
        return

    new_balance = db.add_balance(
        user_id,
        -total_cost,
    )

    db.add_inventory(
        user_id,
        item,
        qty,
        buy_price=shop_item["cost"],
    )

    conn = get_conn()

    conn.execute(
        """
        UPDATE shop_stock
        SET stock = stock - ?
        WHERE item = ?
        """,
        (
            qty,
            item,
        ),
    )

    conn.commit()
    conn.close()

    embed = discord.Embed(
        title="🛒 Purchase Complete",
        color=WHITE,
    )

    embed.set_thumbnail(
        url=interaction.user.display_avatar.url
    )

    embed.add_field(
        name="📦 Item",
        value=(
            f"{shop_item['emoji']} "
            f"`{shop_item['name']}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="🔢 Quantity",
        value=f"`{qty}`",
        inline=True,
    )

    embed.add_field(
        name="💸 Total Cost",
        value=f"`{db.format_peso(total_cost)}`",
        inline=True,
    )

    embed.add_field(
        name="📉 Stock Left",
        value=f"`{stock - qty}`",
        inline=True,
    )

    embed.add_field(
        name="💰 New Balance",
        value=f"`{db.format_peso(new_balance)}`",
        inline=False,
    )

    embed.set_footer(
        text="Use /inventory to see your items."
    )

    await interaction.response.send_message(
        embed=embed
    )
    
async def setup(bot):
    await bot.add_cog(
        Shop(bot)
    )
