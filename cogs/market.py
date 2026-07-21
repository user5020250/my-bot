import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

MARKET_REFRESH_SECONDS = 3 * 60 * 60  # prices change every 3 hours

ITEMS = {
    "rice": {"label": "Rice", "base": 50, "unit": "kg"},
    "fish": {"label": "Fish", "base": 200, "unit": "kg"},
    "mangoes": {"label": "Mangoes", "base": 120, "unit": "kg"},
    "chicken": {"label": "Chicken", "base": 180, "unit": "kg"},
    "meat": {"label": "Meat", "base": 260, "unit": "kg", "variants": ["Pork", "Beef", "Goat"]},
    "vegetables": {
        "label": "Vegetables",
        "base": 80,
        "unit": "kg",
        "variants": ["Kangkong", "Talong", "Sitaw", "Ampalaya", "Kalabasa"],
    },
}
ITEM_CHOICES = [
    app_commands.Choice(name=info["label"], value=key) for key, info in ITEMS.items()
]

LOAD_BUY_PRICE = 8     # ₱ per unit, buying from a load retailer
LOAD_SELL_MIN_MULT = 0.9
LOAD_SELL_MAX_MULT = 1.5
LOAD_BASE_SELL_PRICE = 10  # ₱ per unit baseline before the random multiplier


def _get_or_refresh_market_row(item_key: str) -> dict:
    info = ITEMS[item_key]
    conn = get_conn()
    row = conn.execute("SELECT * FROM market WHERE item = ?", (item_key,)).fetchone()
    now = int(time.time())

    needs_refresh = row is None or (now - row["updated_at"]) > MARKET_REFRESH_SECONDS
    if needs_refresh:
        fluctuation = random.uniform(0.7, 1.3)
        buy_price = max(1, round(info["base"] * fluctuation))
        sell_price = max(1, round(buy_price * 0.85))
        display_name = info["label"]
        if "variants" in info:
            display_name = random.choice(info["variants"])
        conn.execute(
            """
            INSERT INTO market (item, display_name, buy_price, sell_price, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(item) DO UPDATE SET
                display_name = excluded.display_name,
                buy_price = excluded.buy_price,
                sell_price = excluded.sell_price,
                updated_at = excluded.updated_at
            """,
            (item_key, display_name, buy_price, sell_price, now),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM market WHERE item = ?", (item_key,)).fetchone()

    conn.close()
    return dict(row)


class Market(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    palengke = app_commands.Group(name="palengke", description="Buy and sell palengke goods.")
    load = app_commands.Group(name="load", description="Buy mobile load and resell it for profit.")

    # ------------------------------------------------------ /palengke presyo
    @palengke.command(name="presyo", description="See current palengke prices.")
    async def palengke_presyo(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🥬 Palengke Prices Today",
            color=discord.Color.orange(),
        )
        for key, info in ITEMS.items():
            row = _get_or_refresh_market_row(key)
            embed.add_field(
                name=f"{row['display_name']} ({info['unit']})",
                value=f"Bili: {db.format_peso(row['buy_price'])} | Benta: {db.format_peso(row['sell_price'])}",
                inline=False,
            )
        embed.set_footer(text="Prices update every few hours. Use /palengke bili or /palengke benta.")
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /palengke bili
    @palengke.command(name="bili", description="Buy goods from the palengke.")
    @app_commands.describe(item="Which item to buy", quantity="How many kg to buy")
    @app_commands.choices(item=ITEM_CHOICES)
    async def palengke_bili(
        self,
        interaction: discord.Interaction,
        item: app_commands.Choice[str],
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)
        row = _get_or_refresh_market_row(item.value)
        cost = row["buy_price"] * quantity

        if cost > user["balance"]:
            await interaction.response.send_message(
                f"Kulang ang pera mo! Kailangan mo ng {db.format_peso(cost)}, "
                f"meron ka lang {db.format_peso(user['balance'])}.",
                ephemeral=True,
            )
            return

        new_balance = db.add_balance(user_id, -cost)
        db.add_inventory(user_id, item.value, quantity)

        embed = discord.Embed(
            title="🛒 Bumili sa Palengke",
            description=f"Bumili ka ng **{quantity} {ITEMS[item.value]['unit']}** ng "
            f"**{row['display_name']}** para sa **{db.format_peso(cost)}**.",
            color=discord.Color.orange(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /palengke benta
    @palengke.command(name="benta", description="Sell goods you bought from the palengke.")
    @app_commands.describe(item="Which item to sell", quantity="How many kg to sell")
    @app_commands.choices(item=ITEM_CHOICES)
    async def palengke_benta(
        self,
        interaction: discord.Interaction,
        item: app_commands.Choice[str],
        quantity: app_commands.Range[int, 1],
    ):
        user_id = str(interaction.user.id)
        owned = db.get_inventory_qty(user_id, item.value)

        if quantity > owned:
            await interaction.response.send_message(
                f"Wala kang sapat na {ITEMS[item.value]['label']}. Meron ka lang {owned}.",
                ephemeral=True,
            )
            return

        row = _get_or_refresh_market_row(item.value)
        proceeds = row["sell_price"] * quantity
        db.add_inventory(user_id, item.value, -quantity)
        new_balance = db.add_balance(user_id, proceeds)

        embed = discord.Embed(
            title="💰 Nagbenta sa Palengke",
            description=f"Nagbenta ka ng **{quantity} {ITEMS[item.value]['unit']}** ng "
            f"**{row['display_name']}** para sa **{db.format_peso(proceeds)}**.",
            color=discord.Color.green(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------ /load bili
    @load.command(name="bili", description="Buy mobile load to resell later.")
    @app_commands.describe(quantity="How many units of load to buy")
    async def load_bili(self, interaction: discord.Interaction, quantity: app_commands.Range[int, 1]):
        user_id = str(interaction.user.id)
        user = db.get_user(user_id)
        cost = quantity * LOAD_BUY_PRICE

        if cost > user["balance"]:
            await interaction.response.send_message(
                f"Kulang ang pera mo! Kailangan mo ng {db.format_peso(cost)}.",
                ephemeral=True,
            )
            return

        new_balance = db.add_balance(user_id, -cost)
        db.add_inventory(user_id, "load", quantity)

        embed = discord.Embed(
            title="📱 Bumili ng Load",
            description=f"Bumili ka ng **{quantity} units** ng load para sa **{db.format_peso(cost)}**.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------------ /load benta
    @load.command(name="benta", description="Resell your mobile load for profit.")
    @app_commands.describe(quantity="How many units of load to sell")
    async def load_benta(self, interaction: discord.Interaction, quantity: app_commands.Range[int, 1]):
        user_id = str(interaction.user.id)
        owned = db.get_inventory_qty(user_id, "load")

        if quantity > owned:
            await interaction.response.send_message(
                f"Wala kang sapat na load. Meron ka lang {owned} units.",
                ephemeral=True,
            )
            return

        multiplier = random.uniform(LOAD_SELL_MIN_MULT, LOAD_SELL_MAX_MULT)
        proceeds = round(quantity * LOAD_BASE_SELL_PRICE * multiplier)
        db.add_inventory(user_id, "load", -quantity)
        new_balance = db.add_balance(user_id, proceeds)

        profit = proceeds - (quantity * LOAD_BUY_PRICE)
        verdict = "Cha-ching! 📈" if profit >= 0 else "Medyo lugi ka dito. 📉"

        embed = discord.Embed(
            title="📱 Nagbenta ng Load",
            description=f"Nagbenta ka ng **{quantity} units** para sa **{db.format_peso(proceeds)}**.\n{verdict}",
            color=discord.Color.green() if profit >= 0 else discord.Color.red(),
        )
        embed.set_footer(text=f"Balance: {db.format_peso(new_balance)}")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Market(bot))
