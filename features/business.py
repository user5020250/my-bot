import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

# ------------------------------------------------------------- constants

COLLECT_INTERVAL_SECONDS = 4 * 60 * 60

UPGRADE_MAX_LEVEL = 5
UPGRADE_COST_MULTIPLIER = 1.8
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

# Filipino small/medium businesses only.
BUSINESSES = {
    "taho_cart": {
        "name": "Taho Cart",
        "emoji": "🥣",
        "price": 1500,
        "income": 120,
    },
    "sari_sari": {
        "name": "Sari-sari Store",
        "emoji": "🏪",
        "price": 2000,
        "income": 150,
    },
    "fish_stall": {
        "name": "Fish Stall",
        "emoji": "🐟",
        "price": 3000,
        "income": 220,
    },
    "carinderia": {
        "name": "Carinderia",
        "emoji": "🍲",
        "price": 5000,
        "income": 380,
    },
    "internet_cafe": {
        "name": "Internet Café",
        "emoji": "💻",
        "price": 8000,
        "income": 600,
    },
    "laundry_shop": {
        "name": "Laundry Shop",
        "emoji": "🧺",
        "price": 9000,
        "income": 680,
    },
    "rice_farm": {
        "name": "Rice Farm",
        "emoji": "🌾",
        "price": 10000,
        "income": 750,
    },
    "coconut_plantation": {
        "name": "Coconut Plantation",
        "emoji": "🥥",
        "price": 12000,
        "income": 900,
    },
    "milk_tea_shop": {
        "name": "Milk Tea Shop",
        "emoji": "🧋",
        "price": 14000,
        "income": 1050,
    },
    "water_refilling": {
        "name": "Water Refilling Station",
        "emoji": "💧",
        "price": 15000,
        "income": 1100,
    },
    "computer_shop": {
        "name": "Computer Shop",
        "emoji": "🖥️",
        "price": 18000,
        "income": 1350,
    },
    "convenience_store": {
        "name": "Convenience Store",
        "emoji": "🏬",
        "price": 20000,
        "income": 1500,
    },
    "delivery_service": {
        "name": "Delivery Service",
        "emoji": "🛵",
        "price": 25000,
        "income": 1900,
    },
    "jeepney_franchise": {
        "name": "Jeepney Franchise",
        "emoji": "🚙",
        "price": 35000,
        "income": 2700,
    },
    "resort": {
        "name": "Resort",
        "emoji": "🏖️",
        "price": 60000,
        "income": 4800,
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
        * 0.5
        * (UPGRADE_COST_MULTIPLIER ** (level - 1))
    )


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
            f"(income: {db.format_peso(info['income'])} / "
            f"{COLLECT_INTERVAL_SECONDS // 3600}h)"
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
                f"May-ari ka na ng {business_label(key)}."
            )
            return

        user = db.get_user(user_id)

        if user["balance"] < info["price"]:
            conn.close()

            await interaction.response.send_message(
                f"Kulang ang pera mo. Kailangan mo ng "
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
                purchased_at
            )
            VALUES (?, ?, 1, ?, 0, ?)
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
                f"Nabili mo ang {business_label(key)} para sa "
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
                f"Wala kang {business_label(key)}."
            )
            return

        refund = round(
            info["price"] * SELL_RETURN_RATE * owned["level"]
        )

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
                f"Naibenta mo ang {business_label(key)} "
                f"(Level {owned['level']}) para sa "
                f"**{db.format_peso(refund)}**."
            ),
            color=WHITE,
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
                "Wala ka pang negosyo. Try `/business list`."
            )
            return

        now = int(time.time())
        lines = []
        total_lifetime = 0

        for row in owned:
            info = BUSINESSES.get(row["business_key"])

            if info is None:
                continue

            elapsed = now - row["last_collected"]
            ready = elapsed >= COLLECT_INTERVAL_SECONDS

            status = (
                "ready to collect"
                if ready
                else f"ready <t:{row['last_collected'] + COLLECT_INTERVAL_SECONDS}:R>"
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
                    f"Wala kang {business_label(business.value)}."
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
                    "Wala ka pang negosyo."
                )
                return

        total_collected = 0
        lines = []

        for row in rows:
            info = BUSINESSES.get(row["business_key"])

            if info is None:
                continue

            elapsed = now - row["last_collected"]

            if elapsed < COLLECT_INTERVAL_SECONDS:
                remaining = COLLECT_INTERVAL_SECONDS - elapsed
                lines.append(
                    f"{business_label(row['business_key'])} — "
                    f"hintay pa **{db.format_duration(remaining)}**"
                )
                continue

            income = income_for_level(info["income"], row["level"])
            total_collected += income

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
                f"Wala kang {business_label(key)}."
            )
            return

        if owned["level"] >= UPGRADE_MAX_LEVEL:
            conn.close()

            await interaction.response.send_message(
                f"Max level na ang {business_label(key)} "
                f"(Lv. {UPGRADE_MAX_LEVEL})."
            )
            return

        cost = upgrade_cost(info["price"], owned["level"])
        user = db.get_user(user_id)

        if user["balance"] < cost:
            conn.close()

            await interaction.response.send_message(
                f"Kulang ang pera mo. Kailangan mo ng "
                f"**{db.format_peso(cost)}** para mag-upgrade."
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
                f"Na-upgrade ang {business_label(key)} sa "
                f"**Level {new_level}**.\n"
                f"Bagong income: **{db.format_peso(new_income)}** "
                f"per collect."
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
                f"Wala kang {business_label(key)}."
            )
            return

        current_income = income_for_level(info["income"], owned["level"])

        next_upgrade = (
            "Max level na."
            if owned["level"] >= UPGRADE_MAX_LEVEL
            else db.format_peso(
                upgrade_cost(info["price"], owned["level"])
            )
        )

        embed = discord.Embed(
            title=f"{business_label(key)} Stats",
            description=(
                f"Level: **{owned['level']}** / {UPGRADE_MAX_LEVEL}\n"
                f"Income per collect: **{db.format_peso(current_income)}**\n"
                f"Lifetime earnings: **{db.format_peso(owned['lifetime_earnings'])}**\n"
                f"Next upgrade cost: **{next_upgrade}**\n"
                f"Purchased: <t:{owned['purchased_at']}:D>"
            ),
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
        description="Attempt to steal from another player's business.",
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
                "Hindi mo puwedeng raidin ang sarili mong negosyo."
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "Hindi puwedeng raidin ang bots."
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
                f"Wala pang negosyo si {target.display_name}."
            )
            return

        attacker_status = get_status(attacker_id)
        now = int(time.time())
        elapsed = now - attacker_status["last_raid"]

        if elapsed < RAID_COOLDOWN_SECONDS:
            remaining = RAID_COOLDOWN_SECONDS - elapsed

            await interaction.response.send_message(
                f"Nakaka-pagod mag-raid. Try again in "
                f"**{db.format_duration(remaining)}**."
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
                f"May protection pa si {target.mention}. "
                f"Bigo ang raid mo."
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
                        f"Wala palang pera sa kaha ni "
                        f"{target.mention}."
                    ),
                    color=WHITE,
                )
            else:
                db.add_balance(target_id, -stolen)
                new_balance = db.add_balance(attacker_id, stolen)

                embed = discord.Embed(
                    title="Raid Success",
                    description=(
                        f"Na-raid mo ang negosyo ni "
                        f"{target.mention} at nakakuha ka ng "
                        f"**{db.format_peso(stolen)}**."
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

            new_balance = db.add_balance(attacker_id, -penalty)

            embed = discord.Embed(
                title="Raid Failed",
                description=(
                    f"Nahuli ka ng guwardiya ni "
                    f"{target.mention}.\n\n"
                    f"Multa: **{db.format_peso(penalty)}**."
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
                f"Protektado ka pa hanggang "
                f"<t:{status['protected_until']}:R>."
            )
            return

        user = db.get_user(user_id)

        if user["balance"] < DEFEND_COST:
            await interaction.response.send_message(
                f"Kulang ang pera mo. Kailangan mo ng "
                f"**{db.format_peso(DEFEND_COST)}** para mag-tanod."
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
                f"Protektado ang mga negosyo mo hanggang "
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
                f"Wala kang {business_label(key)}."
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
                f"Isinara mo ang {business_label(key)}. "
                f"Walang refund."
            ),
            color=WHITE,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Business(bot)
    )
