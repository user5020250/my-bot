import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

MARKET_REFRESH_SECONDS = 3 * 60 * 60

ITEMS = {
    "rice": {
        "label": "Rice",
        "base": 50,
        "unit": "kg",
    },
    "fish": {
        "label": "Fish",
        "base": 200,
        "unit": "kg",
    },
    "mangoes": {
        "label": "Mangoes",
        "base": 120,
        "unit": "kg",
    },
    "chicken": {
        "label": "Chicken",
        "base": 180,
        "unit": "kg",
    },
    "meat": {
        "label": "Meat",
        "base": 260,
        "unit": "kg",
        "variants": [
            "Pork",
            "Beef",
            "Goat",
        ],
    },
    "vegetables": {
        "label": "Vegetables",
        "base": 80,
        "unit": "kg",
        "variants": [
            "Kangkong",
            "Talong",
            "Sitaw",
            "Ampalaya",
            "Kalabasa",
        ],
    },
}

ITEM_CHOICES = [
    app_commands.Choice(
        name=info["label"],
        value=key,
    )
    for key, info in ITEMS.items()
]

LOAD_BUY_PRICE = 8

LOAD_SELL_MIN_MULT = 0.9
LOAD_SELL_MAX_MULT = 1.5

LOAD_BASE_SELL_PRICE = 10


def _get_or_refresh_market_row(item_key: str) -> dict:
    info = ITEMS[item_key]

    conn = get_conn()

    row = conn.execute(
        "SELECT * FROM market WHERE item = ?",
        (item_key,),
    ).fetchone()

    now = int(time.time())

    needs_refresh = (
        row is None
        or (now - row["updated_at"]) > MARKET_REFRESH_SECONDS
    )

    if needs_refresh:
        fluctuation = random.uniform(
            0.7,
            1.3,
        )

        buy_price = max(
            1,
            round(info["base"] * fluctuation),
        )

        sell_price = max(
            1,
            round(buy_price * 0.85),
        )

        display_name = info["label"]

        if "variants" in info:
            display_name = random.choice(
                info["variants"]
            )

        conn.execute(
            """
            INSERT INTO market (
                item,
                display_name,
                buy_price,
                sell_price,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(item)
            DO UPDATE SET
                display_name = excluded.display_name,
                buy_price = excluded.buy_price,
                sell_price = excluded.sell_price,
                updated_at = excluded.updated_at
            """,
            (
                item_key,
                display_name,
                buy_price,
                sell_price,
                now,
            ),
        )

        conn.commit()

        row = conn.execute(
            "SELECT * FROM market WHERE item = ?",
            (item_key,),
        ).fetchone()

    conn.close()

    return dict(row)


class Market(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    palengke = app_commands.Group(
        name="palengke",
        description="Buy and sell goods.",
    )

    load = app_commands.Group(
        name="load",
        description="Buy load and sell it later.",
    )

    # ------------------------------------------------------ /palengke presyo

    @palengke.command(
        name="presyo",
        description="Check today's prices.",
    )
    async def palengke_presyo(
        self,
        interaction: discord.Interaction,
    ):
        embed = discord.Embed(
            title="Palengke Prices",
            description="Prices change every 3 hours.",
            color=WHITE,
        )

        for key, info in ITEMS.items():
            row = _get_or_refresh_market_row(
                key
            )

            embed.add_field(
                name=f"{row['display_name']} ({info['unit']})",
                value=(
                    f"Buy: {db.format_peso(row['buy_price'])}\n"
                    f"Sell: {db.format_peso(row['sell_price'])}\n"
                    "\u200b"
                ),
                inline=False,
            )

        embed.set_footer(
            text="Use /palengke bili or /palengke benta."
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -------------------------------------------------------- /palengke bili

    @palengke.command(
        name="bili",
        description="Buy from the palengke.",
    )
    @app_commands.describe(
        item="Choose an item",
        quantity="How many kilograms",
    )
    @app_commands.choices(
        item=ITEM_CHOICES
    )
    async def palengke_bili(
        self,
        interaction: discord.Interaction,
        item: app_commands.Choice[str],
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(
            interaction.user.id
        )

        user = db.get_user(
            user_id
        )

        row = _get_or_refresh_market_row(
            item.value
        )

        cost = (
            row["buy_price"]
            * quantity
        )

        if cost > user["balance"]:
            await interaction.response.send_message(
                f"You only have "
                f"{db.format_peso(user['balance'])}.\n\n"
                f"You need "
                f"{db.format_peso(cost)}."
            )
            return

        new_balance = db.add_balance(
            user_id,
            -cost,
        )

        db.add_inventory(
            user_id=user_id,
            item=item.value,
            delta=quantity,
            buy_price=row["buy_price"],
        )

        embed = discord.Embed(
            title="Palengke",
            description=(
                f"You bought "
                f"**{quantity} {ITEMS[item.value]['unit']}** "
                f"of **{row['display_name']}** "
                f"for **{db.format_peso(cost)}**.\n\n"
                f"Bro is starting a business."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # -------------------------------------------------------- /palengke benta

    @palengke.command(
        name="benta",
        description="Sell your goods.",
    )
    @app_commands.describe(
        item="Choose an item",
        quantity="How many kilograms",
    )
    @app_commands.choices(
        item=ITEM_CHOICES
    )
    async def palengke_benta(
        self,
        interaction: discord.Interaction,
        item: app_commands.Choice[str],
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(
            interaction.user.id
        )

        owned = db.get_inventory_qty(
            user_id,
            item.value,
        )

        if quantity > owned:
            await interaction.response.send_message(
                f"You only own "
                f"**{owned} {ITEMS[item.value]['unit']}**."
            )
            return

        row = _get_or_refresh_market_row(
            item.value
        )

        proceeds = (
            row["sell_price"]
            * quantity
        )

        db.add_inventory(
            user_id,
            item.value,
            -quantity,
        )

        new_balance = db.add_balance(
            user_id,
            proceeds,
        )

        embed = discord.Embed(
            title="Palengke",
            description=(
                f"You sold "
                f"**{quantity} {ITEMS[item.value]['unit']}** "
                f"of **{row['display_name']}** "
                f"for **{db.format_peso(proceeds)}**.\n\n"
                f"Easy money."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------------ /load bili

    @load.command(
        name="bili",
        description="Buy mobile load.",
    )
    @app_commands.describe(
        quantity="How many units",
    )
    async def load_bili(
        self,
        interaction: discord.Interaction,
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(
            interaction.user.id
        )

        user = db.get_user(
            user_id
        )

        cost = (
            quantity
            * LOAD_BUY_PRICE
        )

        if cost > user["balance"]:
            await interaction.response.send_message(
                f"You need "
                f"{db.format_peso(cost)} "
                f"for that."
            )
            return

        new_balance = db.add_balance(
            user_id,
            -cost,
        )

        db.add_inventory(
            user_id=user_id,
            item="load",
            delta=quantity,
            buy_price=LOAD_BUY_PRICE,
        )

        embed = discord.Embed(
            title="Load Business",
            description=(
                f"You bought "
                f"**{quantity} units** "
                f"for "
                f"**{db.format_peso(cost)}**.\n\n"
                f"Time to find customers."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------------ /load benta

    @load.command(
        name="benta",
        description="Sell your load.",
    )
    @app_commands.describe(
        quantity="How many units",
    )
    async def load_benta(
        self,
        interaction: discord.Interaction,
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(
            interaction.user.id
        )

        owned = db.get_inventory_qty(
            user_id,
            "load",
        )

        if quantity > owned:
            await interaction.response.send_message(
                f"You only have "
                f"{owned} units."
            )
            return

        multiplier = random.uniform(
            LOAD_SELL_MIN_MULT,
            LOAD_SELL_MAX_MULT,
        )

        proceeds = round(
            quantity
            * LOAD_BASE_SELL_PRICE
            * multiplier
        )

        db.add_inventory(
            user_id,
            "load",
            -quantity,
        )

        new_balance = db.add_balance(
            user_id,
            proceeds,
        )

        profit = proceeds - (
            quantity
            * LOAD_BUY_PRICE
        )

        verdict = (
            "Big W."
            if profit >= 0
            else "Medyo lugi."
        )

        embed = discord.Embed(
            title="Load Business",
            description=(
                f"You sold "
                f"**{quantity} units** "
                f"for "
                f"**{db.format_peso(proceeds)}**.\n\n"
                f"{verdict}"
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Market(bot)
    )
