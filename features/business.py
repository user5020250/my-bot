import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

# ------------------------------------------------------------- constants

COLLECT_INTERVAL_SECONDS = 24 * 60 * 60  # once per day, like real daily income

UPGRADE_MAX_LEVEL = 5
UPGRADE_COST_MULTIPLIER = 1.25
UPGRADE_INCOME_BONUS = 0.25

SELL_RETURN_RATE = 0.5

RAID_COOLDOWN_SECONDS = 12 * 60 * 60
RAID_SUCCESS_CHANCE = 0.45
RAID_STEAL_MIN_RATE = 0.05
RAID_STEAL_MAX_RATE = 0.15
RAID_STEAL_CAP = 8000
RAID_FAIL_PENALTY_MIN = 200
RAID_FAIL_PENALTY_MAX = 1500

DEFEND_DURATION_SECONDS = 6 * 60 * 60
DEFEND_COST = 1000

# After each successful collection, there's a chance the business
# breaks down and needs a repair paid before it earns again.
# Bigger/more complex businesses (equipment-heavy) break down a
# little more often than a simple cart.
MAINTENANCE_BASE_CHANCE = 0.10
MAINTENANCE_CHANCE_PER_LEVEL = 0.015  # more equipment/wear at higher levels
REPAIR_COST_MIN_RATE = 0.03  # % of purchase price
REPAIR_COST_MAX_RATE = 0.09

MAINTENANCE_ISSUES = [
    "The faucet or pipes broke.",
    "The generator malfunctioned.",
    "A new compressor is needed.",
    "The electrical wiring was damaged.",
    "Some equipment was broken.",
    "The roof started leaking.",
    "The air conditioner or refrigeration unit broke down.",
    "The machines need maintenance.",
    "The business was flooded.",
    "New machine parts are needed.",
    "The permit expired and needs to be renewed.",
    "The cash register / POS system broke.",
]

# Realistic-ish PHP capital + net daily income for Filipino small and
# medium businesses. "income" is the amount collectible once per day
# (COLLECT_INTERVAL_SECONDS = 24h), tuned to roughly match what these
# businesses actually net per day in the Philippines at a decent,
# established scale — e.g. a taho vendor clearing a few hundred pesos
# a day, vs. a resort netting tens of thousands. Payback period on
# capital grows from about a week (small hustle) to a few months
# (capital-heavy business), which also matches real life: small
# vendors recoup fast on thin margins, big businesses take longer to
# pay back but earn far more in absolute terms once established.
BUSINESSES = {
    "taho_cart": {
        "name": "Taho Cart",
        "emoji": "🥣",
        "price": 4000,
        "income": 400,
    },
    "sari_sari": {
        "name": "Sari-sari Store",
        "emoji": "🏪",
        "price": 15000,
        "income": 500,
    },
    "fish_stall": {
        "name": "Fish Stall",
        "emoji": "🐟",
        "price": 25000,
        "income": 700,
    },
    "carinderia": {
        "name": "Carinderia",
        "emoji": "🍲",
        "price": 45000,
        "income": 1200,
    },
    "internet_cafe": {
        "name": "Internet Café",
        "emoji": "💻",
        "price": 120000,
        "income": 2200,
    },
    "laundry_shop": {
        "name": "Laundry Shop",
        "emoji": "🧺",
        "price": 150000,
        "income": 2600,
    },
    "rice_farm": {
        "name": "Rice Farm",
        "emoji": "🌾",
        "price": 200000,
        "income": 3200,
    },
    "coconut_plantation": {
        "name": "Coconut Plantation",
        "emoji": "🥥",
        "price": 250000,
        "income": 3800,
    },
    "milk_tea_shop": {
        "name": "Milk Tea Shop",
        "emoji": "🧋",
        "price": 350000,
        "income": 5000,
    },
    "water_refilling": {
        "name": "Water Refilling Station",
        "emoji": "💧",
        "price": 400000,
        "income": 5600,
    },
    "computer_shop": {
        "name": "Computer Shop",
        "emoji": "🖥️",
        "price": 550000,
        "income": 7200,
    },
    "convenience_store": {
        "name": "Convenience Store",
        "emoji": "🏬",
        "price": 700000,
        "income": 8800,
    },
    "delivery_service": {
        "name": "Delivery Service",
        "emoji": "🛵",
        "price": 900000,
        "income": 10800,
    },
    "jeepney_franchise": {
        "name": "Jeepney Franchise",
        "emoji": "🚙",
        "price": 1200000,
        "income": 13600,
    },
    "resort": {
        "name": "Resort",
        "emoji": "🏖️",
        "price": 3000000,
        "income": 30000,
    },
}

BUSINESS_CHOICES = [
    app_commands.Choice(
        name=info["name"],
        value=key,
    )
    for key, info in BUSINESSES.items()
]


def ensure_business_tables():
    conn = get_conn()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS owned_businesses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            business_key TEXT NOT NULL,
            level INTEGER NOT NULL DEFAULT 1,
            last_collected INTEGER NOT NULL,
            lifetime_earnings INTEGER NOT NULL DEFAULT 0,
            purchased_at INTEGER NOT NULL,
            broken INTEGER NOT NULL DEFAULT 0,
            repair_cost INTEGER NOT NULL DEFAULT 0,
            repair_reason TEXT,
            broken_since INTEGER,
            UNIQUE (
                user_id,
                business_key
            )
        );
        CREATE TABLE IF NOT EXISTS business_status (
            user_id TEXT PRIMARY KEY,
            last_raid INTEGER NOT NULL DEFAULT 0,
            protected_until INTEGER NOT NULL DEFAULT 0
        );
        """
    )

    # Migrate databases created before the repair/maintenance columns
    # existed, so this doesn't break on existing installs.
    existing_cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(owned_businesses)")
    }

    if "broken" not in existing_cols:
        conn.execute(
            "ALTER TABLE owned_businesses ADD COLUMN broken INTEGER NOT NULL DEFAULT 0"
        )

    if "repair_cost" not in existing_cols:
        conn.execute(
            "ALTER TABLE owned_businesses ADD COLUMN repair_cost INTEGER NOT NULL DEFAULT 0"
        )

    if "repair_reason" not in existing_cols:
        conn.execute(
            "ALTER TABLE owned_businesses ADD COLUMN repair_reason TEXT"
        )

    if "broken_since" not in existing_cols:
        conn.execute(
            "ALTER TABLE owned_businesses ADD COLUMN broken_since INTEGER"
        )

    conn.commit()
    conn.close()


def business_label(key: str) -> str:
    info = BUSINESSES.get(key)

    if info is None:
        return key

    return f"{info['emoji']} {info['name']}"


def income_for_level(base_income: int, level: int) -> int:
    return round(
        base_income * (1 + UPGRADE_INCOME_BONUS * (level - 1))
    )


def upgrade_cost(base_price: int, level: int) -> int:
    return round(
        base_price
        * 0.25
        * (UPGRADE_COST_MULTIPLIER ** (level - 1))
    )


def maintenance_chance(level: int) -> float:
    return MAINTENANCE_BASE_CHANCE + MAINTENANCE_CHANCE_PER_LEVEL * (level - 1)


def roll_repair_cost(base_price: int, level: int) -> int:
    rate = random.uniform(REPAIR_COST_MIN_RATE, REPAIR_COST_MAX_RATE)
    # Higher-level setups have more equipment on the line, so repairs
    # scale up a bit with level too.
    scaled_price = base_price * (1 + 0.1 * (level - 1))
    return max(50, round(scaled_price * rate))


def get_status(user_id: str):
    conn = get_conn()

    row = conn.execute(
        "SELECT * FROM business_status WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO business_status (user_id, last_raid, protected_until)
            VALUES (?, 0, 0)
            """,
            (user_id,),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM business_status WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    conn.close()
    return row


class Business(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        ensure_business_tables()

    business_group = app_commands.Group(
        name="business",
        description="Buy, manage, and grow your businesses.",
    )

    # -------------------------------------------------------- /business list

    @business_group.command(
        name="list",
        description="Show all available businesses and their prices.",
    )
    async def business_list(
        self,
        interaction: discord.Interaction,
    ):
        lines = [
            f"{info['emoji']} **{info['name']}** — "
            f"{db.format_peso(info['price'])} "
            f"(income: {db.format_peso(info['income'])} / day)"
            for info in BUSINESSES.values()
        ]

        embed = discord.Embed(
            title="Available Businesses",
            description="\n".join(lines),
            color=WHITE,
        )

        embed.set_footer(
            text="/business buy <business> para bumili."
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------------- /business buy

    @business_group.command(
        name="buy",
        description="Buy a business.",
    )
    @app_commands.describe(business="Which business to buy")
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_buy(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        key = business.value
        info = BUSINESSES[key]

        conn = get_conn()

        existing = conn.execute(
            """
            SELECT id FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()

        if existing is not None:
            conn.close()

            await interaction.response.send_message(
                f"You already own {business_label(key)}."
            )
            return

        user = db.get_user(user_id)

        if user["balance"] < info["price"]:
            conn.close()

            await interaction.response.send_message(
                f"You don't have enough money. You need "
                f"**{db.format_peso(info['price'])}**."
            )
            return

        new_balance = db.add_balance(user_id, -info["price"])

        conn.execute(
            """
            INSERT INTO owned_businesses (
                user_id,
                business_key,
                level,
                last_collected,
                lifetime_earnings,
                purchased_at,
                broken,
                repair_cost,
                repair_reason,
                broken_since
            )
            VALUES (?, ?, 1, ?, 0, ?, 0, 0, NULL, NULL)
            """,
            (
                user_id,
                key,
                int(time.time()),
                int(time.time()),
            ),
        )

        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="Business Bought",
            description=(
                f"You purchased {business_label(key)} for "
                f"**{db.format_peso(info['price'])}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /business sell

    @business_group.command(
        name="sell",
        description="Sell a business back to the bot.",
    )
    @app_commands.describe(business="Which business to sell")
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_sell(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        key = business.value
        info = BUSINESSES[key]

        conn = get_conn()

        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()

        if owned is None:
            conn.close()

            await interaction.response.send_message(
                f"You don't own {business_label(key)}."
            )
            return

        refund = round(
            info["price"] * SELL_RETURN_RATE * owned["level"]
        )

        # Unpaid repairs get deducted from the resale value — nobody
        # wants to buy a broken-down business at full price.
        if owned["broken"]:
            refund = max(0, refund - owned["repair_cost"])

        conn.execute(
            "DELETE FROM owned_businesses WHERE id = ?",
            (owned["id"],),
        )

        conn.commit()
        conn.close()

        new_balance = db.add_balance(user_id, refund)

        embed = discord.Embed(
            title="Business Sold",
            description=(
                f"You sold {business_label(key)} "
                f"(Level {owned['level']}) para sa "
                f"**{db.format_peso(refund)}**."
            ),
            color=WHITE,
        )

        if owned["broken"]:
            embed.description += (
                f"\n(The value was reduced because of unpaid repairs worth "
                f"nababayarang repair na **{db.format_peso(owned['repair_cost'])}**.)"
            )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(embed=embed)

    # --------------------------------------------------- /business portfolio

    @business_group.command(
        name="portfolio",
        description="Show all businesses you own.",
    )
    async def business_portfolio(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        conn = get_conn()

        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ?
            ORDER BY purchased_at ASC
            """,
            (user_id,),
        ).fetchall()

        conn.close()

        if not owned:
            await interaction.response.send_message(
                "You don't own any businesses yet. Try `/business list`."
            )
            return

        now = int(time.time())
        lines = []
        total_lifetime = 0

        for row in owned:
            info = BUSINESSES.get(row["business_key"])

            if info is None:
                continue

            if row["broken"]:
                status = (
                    f"🛠️ Needs repair — "
                    f"**{db.format_peso(row['repair_cost'])}**"
                )
            else:
                elapsed = now - row["last_collected"]
                ready = elapsed >= COLLECT_INTERVAL_SECONDS

                status = (
                    "Ready to collect"
                    if ready
                    else f"Ready <t:{row['last_collected'] + COLLECT_INTERVAL_SECONDS}:R>"
                )

            total_lifetime += row["lifetime_earnings"]

            lines.append(
                f"{business_label(row['business_key'])} "
                f"(Lv. {row['level']}) — {status}"
            )

        embed = discord.Embed(
            title=f"{interaction.user.display_name}'s Portfolio",
            description="\n".join(lines),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Lifetime earnings: {db.format_peso(total_lifetime)}"
        )

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------ /business collect

    @business_group.command(
        name="collect",
        description="Collect income from your businesses.",
    )
    @app_commands.describe(
        business="Leave empty to collect from all businesses"
    )
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_collect(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str] = None,
    ):
        user_id = str(interaction.user.id)
        now = int(time.time())

        conn = get_conn()

        if business is not None:
            rows = conn.execute(
                """
                SELECT * FROM owned_businesses
                WHERE user_id = ? AND business_key = ?
                """,
                (user_id, business.value),
            ).fetchall()

            if not rows:
                conn.close()

                await interaction.response.send_message(
                    "You don't own {business_label(business.value)}."
                )
                return
        else:
            rows = conn.execute(
                "SELECT * FROM owned_businesses WHERE user_id = ?",
                (user_id,),
            ).fetchall()

            if not rows:
                conn.close()

                await interaction.response.send_message(
                    "You don't own any businesses yet."
                )
                return

        total_collected = 0
        lines = []
        newly_broken = []

        for row in rows:
            info = BUSINESSES.get(row["business_key"])

            if info is None:
                continue

            if row["broken"]:
                lines.append(
                    f"{business_label(row['business_key'])} — 🛠️ "
                    f"Needs repair (**{db.format_peso(row['repair_cost'])}**) "
                    f"before it can earn again"
                )
                continue

            elapsed = now - row["last_collected"]

            if elapsed < COLLECT_INTERVAL_SECONDS:
                remaining = COLLECT_INTERVAL_SECONDS - elapsed
                lines.append(
                    f"{business_label(row['business_key'])} — "
                    f"Wait **{db.format_duration(remaining)}**"
                )
                continue

            income = income_for_level(info["income"], row["level"])
            total_collected += income

            # Roll for a random maintenance breakdown after collecting.
            breaks_down = random.random() < maintenance_chance(row["level"])

            if breaks_down:
                repair_cost = roll_repair_cost(info["price"], row["level"])
                reason = random.choice(MAINTENANCE_ISSUES)

                conn.execute(
                    """
                    UPDATE owned_businesses
                    SET last_collected = ?,
                        lifetime_earnings = lifetime_earnings + ?,
                        broken = 1,
                        repair_cost = ?,
                        repair_reason = ?,
                        broken_since = ?
                    WHERE id = ?
                    """,
                    (now, income, repair_cost, reason, now, row["id"]),
                )

                lines.append(
                    f"{business_label(row['business_key'])} — "
                    f"**{db.format_peso(income)}**\n"
                    f"⚠️ {reason}! Repairs costing **{db.format_peso(repair_cost)}** "
                    f"are needed — use `/business repair`."
                )

                newly_broken.append(row["business_key"])
            else:
                conn.execute(
                    """
                    UPDATE owned_businesses
                    SET last_collected = ?,
                        lifetime_earnings = lifetime_earnings + ?
                    WHERE id = ?
                    """,
                    (now, income, row["id"]),
                )

                lines.append(
                    f"{business_label(row['business_key'])} — "
                    f"**{db.format_peso(income)}**"
                )

        conn.commit()
        conn.close()

        if total_collected > 0:
            new_balance = db.add_balance(user_id, total_collected)
        else:
            new_balance = db.get_user(user_id)["balance"]

        embed = discord.Embed(
            title="Business Collection",
            description="\n".join(lines),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                f"Total: {db.format_peso(total_collected)} | "
                f"Balance: {db.format_peso(new_balance)}"
            )
        )

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------- /business repair

    @business_group.command(
        name="repair",
        description="Pay for maintenance on a broken-down business.",
    )
    @app_commands.describe(
        business="Leave empty to see which businesses need repair"
    )
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_repair(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str] = None,
    ):
        user_id = str(interaction.user.id)
    
        conn = get_conn()
    
        if business is None:
            broken_rows = conn.execute(
                """
                SELECT * FROM owned_businesses
                WHERE user_id = ? AND broken = 1
                """,
                (user_id,),
            ).fetchall()
    
            conn.close()
    
            if not broken_rows:
                await interaction.response.send_message(
                    "All of your businesses are running normally. ✅"
                )
                return
    
            lines = [
                f"{business_label(r['business_key'])} — "
                f"**{db.format_peso(r['repair_cost'])}** ({r['repair_reason']})"
                for r in broken_rows
            ]
    
            embed = discord.Embed(
                title="🛠️ Businesses Needing Repair",
                description="\n".join(lines),
                color=WHITE,
            )
    
            embed.set_footer(
                text="Use /business repair <business> to repair it."
            )
    
            await interaction.response.send_message(embed=embed)
            return
    
        key = business.value
    
        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()
    
        if owned is None:
            conn.close()
    
            await interaction.response.send_message(
                f"You don't own {business_label(key)}."
            )
            return
    
        if not owned["broken"]:
            conn.close()
    
            await interaction.response.send_message(
                f"{business_label(key)} doesn't need repairs."
            )
            return
    
        user = db.get_user(user_id)
    
        if user["balance"] < owned["repair_cost"]:
            conn.close()
    
            await interaction.response.send_message(
                f"You don't have enough money. You need "
                f"**{db.format_peso(owned['repair_cost'])}** to repair "
                f"{business_label(key)} ({owned['repair_reason']})."
            )
            return
    
        new_balance = db.add_balance(
            user_id,
            -owned["repair_cost"],
        )
    
        conn.execute(
            """
            UPDATE owned_businesses
            SET broken = 0,
                repair_cost = 0,
                repair_reason = NULL,
                broken_since = NULL
            WHERE id = ?
            """,
            (owned["id"],),
        )
    
        conn.commit()
        conn.close()
    
        embed = discord.Embed(
            title="Business Repaired",
            description=(
                f"You repaired {business_label(key)} for "
                f"**{db.format_peso(owned['repair_cost'])}**.\n"
                f"You can collect income from it again."
            ),
            color=WHITE,
        )
    
        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )
    
        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------- /business upgrade

    @business_group.command(
        name="upgrade",
        description="Upgrade a business to increase its income.",
    )
    @app_commands.describe(business="Which business to upgrade")
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_upgrade(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        key = business.value
        info = BUSINESSES[key]
    
        conn = get_conn()
    
        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()
    
        if owned is None:
            conn.close()
    
            await interaction.response.send_message(
                f"You do not own {business_label(key)}."
            )
            return
    
        if owned["broken"]:
            conn.close()
    
            await interaction.response.send_message(
                f"You must repair {business_label(key)} "
                f"first using `/business repair` before upgrading it."
            )
            return
    
        if owned["level"] >= UPGRADE_MAX_LEVEL:
            conn.close()
    
            await interaction.response.send_message(
                f"{business_label(key)} has already reached "
                f"the maximum level (Lv. {UPGRADE_MAX_LEVEL})."
            )
            return
    
        cost = upgrade_cost(info["price"], owned["level"])
        user = db.get_user(user_id)
    
        if user["balance"] < cost:
            conn.close()
    
            await interaction.response.send_message(
                f"You do not have enough money.\n"
                f"You need **{db.format_peso(cost)}** to upgrade "
                f"{business_label(key)}."
            )
            return
    
        new_balance = db.add_balance(user_id, -cost)
        new_level = owned["level"] + 1
    
        conn.execute(
            "UPDATE owned_businesses SET level = ? WHERE id = ?",
            (new_level, owned["id"]),
        )
    
        conn.commit()
        conn.close()
    
        new_income = income_for_level(info["income"], new_level)
    
        embed = discord.Embed(
            title="Business Upgraded",
            description=(
                f"{business_label(key)} has been upgraded to "
                f"**Level {new_level}**.\n\n"
                f"New daily income: "
                f"**{db.format_peso(new_income)}**."
            ),
            color=WHITE,
        )
    
        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )
    
        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------- /business stats

    @business_group.command(
        name="stats",
        description="Show lifetime earnings, level, and upgrades for a business.",
    )
    @app_commands.describe(business="Which business to inspect")
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_stats(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        key = business.value
        info = BUSINESSES[key]
    
        conn = get_conn()
    
        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()
    
        conn.close()
    
        if owned is None:
            await interaction.response.send_message(
                f"You do not own {business_label(key)}."
            )
            return
    
        current_income = income_for_level(
            info["income"],
            owned["level"],
        )
    
        next_upgrade = (
            "Maximum level reached"
            if owned["level"] >= UPGRADE_MAX_LEVEL
            else db.format_peso(
                upgrade_cost(
                    info["price"],
                    owned["level"],
                )
            )
        )
    
        description = (
            f"Level: **{owned['level']} / {UPGRADE_MAX_LEVEL}**\n"
            f"Daily income: **{db.format_peso(current_income)}**\n"
            f"Lifetime earnings: **{db.format_peso(owned['lifetime_earnings'])}**\n"
            f"Next upgrade cost: **{next_upgrade}**\n"
            f"Purchased on: <t:{owned['purchased_at']}:D>"
        )
    
        if owned["broken"]:
            description += (
                f"\n\n🛠️ **Needs repair**\n"
                f"Issue: {owned['repair_reason']}\n"
                f"Repair cost: **{db.format_peso(owned['repair_cost'])}**"
            )
    
        embed = discord.Embed(
            title=f"{business_label(key)} Stats",
            description=description,
            color=WHITE,
        )
    
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------- /business leaderboard

    @business_group.command(
        name="leaderboard",
        description="Show the richest business owners.",
    )
    async def business_leaderboard(
        self,
        interaction: discord.Interaction,
    ):
        conn = get_conn()

        rows = conn.execute(
            """
            SELECT user_id, SUM(lifetime_earnings) AS total
            FROM owned_businesses
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT 10
            """
        ).fetchall()

        conn.close()

        if not rows:
            await interaction.response.send_message(
                "Wala pang negosyante."
            )
            return

        lines = [
            f"**{i}.** <@{row['user_id']}> — "
            f"{db.format_peso(row['total'])}"
            for i, row in enumerate(rows, start=1)
        ]

        embed = discord.Embed(
            title="🏆 Business Leaderboard",
            description="\n".join(lines),
            color=WHITE,
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /business raid

    @business_group.command(
        name="raid",
        description="Attempt to steal money from another player's business.",
    )
    @app_commands.describe(target="Who to raid")
    async def business_raid(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        attacker_id = str(interaction.user.id)
        target_id = str(target.id)
    
        if attacker_id == target_id:
            await interaction.response.send_message(
                "You cannot raid your own business."
            )
            return
    
        if target.bot:
            await interaction.response.send_message(
                "You cannot raid bots."
            )
            return
    
        conn = get_conn()
    
        target_owns_business = conn.execute(
            "SELECT id FROM owned_businesses WHERE user_id = ? LIMIT 1",
            (target_id,),
        ).fetchone()
    
        conn.close()
    
        if target_owns_business is None:
            await interaction.response.send_message(
                f"{target.display_name} does not own any businesses."
            )
            return
    
        attacker_status = get_status(attacker_id)
        now = int(time.time())
        elapsed = now - attacker_status["last_raid"]
    
        if elapsed < RAID_COOLDOWN_SECONDS:
            remaining = RAID_COOLDOWN_SECONDS - elapsed
    
            await interaction.response.send_message(
                f"You are still recovering from your last raid.\n"
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return
    
        conn = get_conn()
    
        conn.execute(
            """
            UPDATE business_status
            SET last_raid = ?
            WHERE user_id = ?
            """,
            (now, attacker_id),
        )
    
        conn.commit()
        conn.close()
    
        target_status = get_status(target_id)
    
        if target_status["protected_until"] > now:
            await interaction.response.send_message(
                f"{target.mention} is currently protected.\n"
                f"Your raid has failed."
            )
            return
    
        success = random.random() < RAID_SUCCESS_CHANCE
    
        if success:
            target_user = db.get_user(target_id)
    
            stolen = min(
                round(
                    target_user["balance"]
                    * random.uniform(
                        RAID_STEAL_MIN_RATE,
                        RAID_STEAL_MAX_RATE,
                    )
                ),
                RAID_STEAL_CAP,
            )
    
            if stolen <= 0:
                embed = discord.Embed(
                    title="Raid Attempt",
                    description=(
                        f"You broke into {target.mention}'s business, "
                        f"but there was no money to steal."
                    ),
                    color=WHITE,
                )
            else:
                db.add_balance(target_id, -stolen)
                new_balance = db.add_balance(attacker_id, stolen)
    
                embed = discord.Embed(
                    title="Raid Successful",
                    description=(
                        f"You raided {target.mention}'s business and "
                        f"stole **{db.format_peso(stolen)}**."
                    ),
                    color=WHITE,
                )
    
                embed.set_footer(
                    text=f"Balance: {db.format_peso(new_balance)}"
                )
    
        else:
            penalty = random.randint(
                RAID_FAIL_PENALTY_MIN,
                RAID_FAIL_PENALTY_MAX,
            )
    
            new_balance = db.add_balance(
                attacker_id,
                -penalty,
            )
    
            embed = discord.Embed(
                title="Raid Failed",
                description=(
                    f"You were caught by {target.mention}'s security guards.\n\n"
                    f"Fine: **{db.format_peso(penalty)}**."
                ),
                color=WHITE,
            )
    
            embed.set_footer(
                text=f"Balance: {db.format_peso(new_balance)}"
            )
    
        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------- /business defend

    @business_group.command(
        name="defend",
        description="Add temporary protection against raids.",
    )
    async def business_defend(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)
    
        status = get_status(user_id)
        now = int(time.time())
    
        if status["protected_until"] > now:
            await interaction.response.send_message(
                f"Your businesses are already protected until "
                f"<t:{status['protected_until']}:R>."
            )
            return
    
        user = db.get_user(user_id)
    
        if user["balance"] < DEFEND_COST:
            await interaction.response.send_message(
                f"You do not have enough money.\n"
                f"You need **{db.format_peso(DEFEND_COST)}** "
                f"to hire security."
            )
            return
    
        new_balance = db.add_balance(user_id, -DEFEND_COST)
        protected_until = now + DEFEND_DURATION_SECONDS
    
        conn = get_conn()
    
        conn.execute(
            """
            UPDATE business_status
            SET protected_until = ?
            WHERE user_id = ?
            """,
            (protected_until, user_id),
        )
    
        conn.commit()
        conn.close()
    
        embed = discord.Embed(
            title="Security Hired",
            description=(
                f"Your businesses are protected from raids until "
                f"<t:{protected_until}:R>."
            ),
            color=WHITE,
        )
    
        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )
    
        await interaction.response.send_message(embed=embed)

    # ----------------------------------------------------- /business bankrupt

    @business_group.command(
        name="bankrupt",
        description="Close a business permanently (no refund).",
    )
    @app_commands.describe(business="Which business to close")
    @app_commands.choices(business=BUSINESS_CHOICES)
    async def business_bankrupt(
        self,
        interaction: discord.Interaction,
        business: app_commands.Choice[str],
    ):
        user_id = str(interaction.user.id)
        key = business.value
    
        conn = get_conn()
    
        owned = conn.execute(
            """
            SELECT * FROM owned_businesses
            WHERE user_id = ? AND business_key = ?
            """,
            (user_id, key),
        ).fetchone()
    
        if owned is None:
            conn.close()
    
            await interaction.response.send_message(
                f"You do not own {business_label(key)}."
            )
            return
    
        conn.execute(
            "DELETE FROM owned_businesses WHERE id = ?",
            (owned["id"],),
        )
    
        conn.commit()
        conn.close()
    
        embed = discord.Embed(
            title="Business Closed",
            description=(
                f"You permanently closed {business_label(key)}.\n\n"
                f"You will not receive any refund."
            ),
            color=WHITE,
        )
    
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Business(bot)
    )
