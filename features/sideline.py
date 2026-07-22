import random
import time
import discord
from discord import app_commands
from discord.ext import commands
from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

SIDELINE_COOLDOWN_SECONDS = 60
FISH_COOLDOWN_SECONDS = 45
MINE_COOLDOWN_SECONDS = 60
FARM_COOLDOWN_SECONDS = 45
HUNT_COOLDOWN_SECONDS = 60
COOK_COOLDOWN_SECONDS = 60

FISH_SELL_PRICE = 100
WHEAT_SELL_PRICE = 100

# (ore item, weight) — higher weight = more common
ORE_WEIGHTS = [
    ("copper", 40),
    ("silver", 30),
    ("gold", 18),
    ("diamond", 8),
    ("obsidian", 4),
]

SIDELINE_COOLDOWN_FIELDS = (
    "last_sideline",
    "last_fish",
    "last_mine",
    "last_farm",
    "last_hunt",
    "last_cook",
)


def ensure_sideline_columns():
    conn = get_conn()
    existing_cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(users)")
    }
    for field in SIDELINE_COOLDOWN_FIELDS:
        if field not in existing_cols:
            conn.execute(
                f"ALTER TABLE users ADD COLUMN {field} INTEGER NOT NULL DEFAULT 0"
            )
    conn.commit()
    conn.close()


class Sideline(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_sideline_columns()

    async def cog_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        # Without this, an unhandled exception here means Discord
        # never gets a response and shows "The application did not
        # respond" instead of a real error message.
        print(f"[sideline] command error: {error!r}")
        message = "⚠️ Something went wrong. Please try again later."
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    # -------------------------------------------------------- /sideline
    @app_commands.command(
        name="sideline",
        description="Do a random side hustle.",
    )
    async def sideline(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_sideline",
            SIDELINE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ You already worked your sideline.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_sideline",
            int(time.time()),
        )

        jobs = [
            ("🛵 You delivered food orders.", 150, 400),
            ("🧼 You washed motorcycles.", 100, 300),
            ("🍿 You sold snacks outside school.", 120, 350),
            ("🏪 You worked at a sari-sari store.", 150, 350),
            ("🧱 You helped a construction worker.", 250, 600),
            ("🐟 You sold fish at the market.", 200, 500),
            ("🌾 You carried sacks of rice.", 250, 700),
        ]

        message, minimum, maximum = random.choice(jobs)
        earnings = random.randint(minimum, maximum)

        new_balance = db.add_balance(user_id, earnings)

        embed = discord.Embed(
            title="💼 Sideline",
            description=(
                f"{message}\n\n"
                f"You earned **{db.format_peso(earnings)}**."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /fish
    @app_commands.command(
        name="fish",
        description="Catch a fish you can sell later.",
    )
    async def fish(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_fish",
            FISH_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ You're still waiting for a bite.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_fish",
            int(time.time()),
        )

        amount = random.randint(1, 5)

        db.add_inventory(
            user_id,
            "fish",
            amount,
            buy_price=FISH_SELL_PRICE,
        )

        qty = db.get_inventory_qty(user_id, "fish")

        embed = discord.Embed(
            title="🎣 Fishing",
            description=(
                f"You caught **{amount} fish**!"
                f"It's not usable, but you can sell it for "
                f"**{db.format_peso(FISH_SELL_PRICE)}** each."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"🐟 Fish in inventory: {qty}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /mine
    @app_commands.command(
        name="mine",
        description="Mine for random ores.",
    )
    async def mine(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_mine",
            MINE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Your pickaxe needs a rest.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_mine",
            int(time.time()),
        )

        ores, weights = zip(*ORE_WEIGHTS)
        ore = random.choices(ores, weights=weights, k=1)[0]

        amount = random.randint(1, 5)
        
        db.add_inventory(
            user_id,
            ore,
            amount,
        )

        qty = db.get_inventory_qty(user_id, ore)

        ore_emojis = {
            "copper": "🟠",
            "silver": "⚪",
            "gold": "🟡",
            "diamond": "💎",
            "obsidian": "⬛",
        }
        emoji = ore_emojis.get(ore, "⛏️")

        embed = discord.Embed(
            title="⛏️ Mining",
            description=(
                f"You mined **{amount}×** {emoji} **{ore.title()}**!"
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"{emoji} {ore.title()} in inventory: {qty}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /farm
    @app_commands.command(
        name="farm",
        description="Harvest wheat you can sell later.",
    )
    async def farm(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_farm",
            FARM_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ Your crops aren't ready yet.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_farm",
            int(time.time()),
        )

        amount = random.randint(1, 5)

        db.add_inventory(
            user_id,
            "wheat",
            amount,
            buy_price=WHEAT_SELL_PRICE,
        )

        qty = db.get_inventory_qty(user_id, "wheat")

        embed = discord.Embed(
            title="🌾 Farming",
            description=(
                f"You harvested **{amount} wheat**!"
                f"It's not usable, but you can sell it for "
                f"**{db.format_peso(WHEAT_SELL_PRICE)}** each."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"🌾 Wheat in inventory: {qty}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /hunt
    @app_commands.command(
        name="hunt",
        description="Hunt for money.",
    )
    async def hunt(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_hunt",
            HUNT_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ The animals are still spooked.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_hunt",
            int(time.time()),
        )

        hunts = [
            "🦌 You bagged a deer.",
            "🐗 You took down a wild boar.",
            "🐦 You shot down some birds.",
            "🐰 You caught a rabbit.",
            "🦆 You hunted a duck by the river.",
        ]

        message = random.choice(hunts)
        earnings = random.randint(100, 5000)

        new_balance = db.add_balance(user_id, earnings)

        embed = discord.Embed(
            title="🏹 Hunting",
            description=(
                f"{message}\n\n"
                f"You earned **{db.format_peso(earnings)}**."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /cook
    @app_commands.command(
        name="cook",
        description="Cook food to earn money.",
    )
    async def cook(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        remaining = db.check_cooldown(
            user_id,
            "last_cook",
            COOK_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"⏳ The kitchen is still busy.\n"
                f"Come back in **{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_cook",
            int(time.time()),
        )

        dishes = [
            "🍜 You cooked a batch of noodles.",
            "🍗 You fried up some chicken.",
            "🍲 You made a pot of sinigang.",
            "🍛 You cooked adobo rice bowls.",
            "🥘 You whipped up street food orders.",
        ]

        message = random.choice(dishes)
        earnings = random.randint(100, 5000)

        new_balance = db.add_balance(user_id, earnings)

        embed = discord.Embed(
            title="🍳 Cooking",
            description=(
                f"{message}\n\n"
                f"You earned **{db.format_peso(earnings)}**."
            ),
            color=WHITE,
        )
        embed.set_footer(
            text=f"💰 Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Sideline(bot)
    )
