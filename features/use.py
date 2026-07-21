import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from database import get_conn

WHITE = discord.Color(0xFFFFFF)

PADLOCK_DURATION = 24 * 60 * 60

GLOVES_WINDOW_SECONDS = 15 * 60
MASK_WINDOW_SECONDS = 15 * 60

LOCKPICK_BREAK_CHANCE = 0.70

ENERGY_DRINK_COOLDOWN_FIELD = "last_trabaho"

MYSTERY_CASH_MIN = -3000
MYSTERY_CASH_MAX = 8000

MYSTERY_CRATE_CASH_MIN = 1000
MYSTERY_CRATE_CASH_MAX = 5000

MYSTERY_CRATE_REWARDS = [
    ("diamond", 0.05),
    ("crown", 0.03),
    ("trophy", 0.05),
    ("ancient_coin", 0.02),
    ("cash", 0.85),
]

RARE_ITEM_NAMES = {
    "diamond": ("💎", "Diamond"),
    "crown": ("👑", "Crown"),
    "trophy": ("🏆", "Trophy"),
    "ancient_coin": ("🪙", "Ancient Coin"),
}


class Use(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db.ensure_status_effect_columns()

    @app_commands.command(
        name="use",
        description="Use an item.",
    )
    @app_commands.describe(
        item="Item to use",
        target="Required for lockpick",
    )
    async def use(
        self,
        interaction: discord.Interaction,
        item: str,
        target: discord.Member = None,
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

        # =========================
        # GLOVES
        # =========================
        if item == "gloves":
            now = int(time.time())
            expires_at = now + GLOVES_WINDOW_SECONDS

            db.set_status_field(
                user_id,
                "gloves_until",
                expires_at,
            )

            db.remove_inventory(
                user_id,
                "gloves",
                1,
            )

            embed = discord.Embed(
                title="🧤 Gloves Equipped",
                description=(
                    "Your next `/steal` attempt has a "
                    "reduced chance of getting caught."
                ),
                color=WHITE,
            )
            embed.add_field(
                name="Expires In",
                value=f"`{db.format_duration(GLOVES_WINDOW_SECONDS)}`",
                inline=False,
            )
            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # MASK
        # =========================
        if item == "mask":
            now = int(time.time())
            expires_at = now + MASK_WINDOW_SECONDS

            db.set_status_field(
                user_id,
                "mask_until",
                expires_at,
            )

            db.remove_inventory(
                user_id,
                "mask",
                1,
            )

            embed = discord.Embed(
                title="😷 Mask Equipped",
                description=(
                    "Your next `/steal` attempt has a "
                    "reduced chance of getting caught."
                ),
                color=WHITE,
            )
            embed.add_field(
                name="Expires In",
                value=f"`{db.format_duration(MASK_WINDOW_SECONDS)}`",
                inline=False,
            )
            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # ALARM SYSTEM / INSURANCE
        # (passive - auto-triggered, not manually used)
        # =========================
        if item in ("alarm_system", "insurance"):
            await interaction.response.send_message(
                "❌ This item activates automatically and doesn't need to be used.",
                ephemeral=True,
            )
            return

        # =========================
        # LOCKPICK
        # =========================
        if item == "lockpick":
            if target is None:
                await interaction.response.send_message(
                    "❌ You need to specify a `target` to use the lockpick on.",
                    ephemeral=True,
                )
                return

            if target.id == interaction.user.id:
                await interaction.response.send_message(
                    "🚫 You can't lockpick yourself.",
                    ephemeral=True,
                )
                return

            target_id = str(target.id)

            now = int(time.time())
            conn = get_conn()
            row = conn.execute(
                """
                SELECT protected_until
                FROM business_status
                WHERE user_id = ?
                """,
                (target_id,),
            ).fetchone()
            conn.close()

            protected_until = row["protected_until"] if row else 0

            if protected_until <= now:
                db.remove_inventory(
                    user_id,
                    "lockpick",
                    1,
                )
                await interaction.response.send_message(
                    f"❌ {target.mention} doesn't have an active padlock.",
                    ephemeral=True,
                )
                return

            db.remove_inventory(
                user_id,
                "lockpick",
                1,
            )

            success = random.random() < LOCKPICK_BREAK_CHANCE

            if success:
                db.set_status_field(
                    target_id,
                    "protected_until",
                    0,
                )

                embed = discord.Embed(
                    title="🔑 Lockpick Success",
                    description=(
                        f"You broke {target.mention}'s padlock!"
                    ),
                    color=WHITE,
                )
            else:
                embed = discord.Embed(
                    title="🔑 Lockpick Failed",
                    description=(
                        f"The lockpick broke. "
                        f"{target.mention}'s padlock is still active."
                    ),
                    color=WHITE,
                )

            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # ENERGY DRINK
        # =========================
        if item == "energy_drink":
            db.set_cooldown(
                user_id,
                ENERGY_DRINK_COOLDOWN_FIELD,
                0,
            )

            db.remove_inventory(
                user_id,
                "energy_drink",
                1,
            )

            embed = discord.Embed(
                title="⚡ Energy Drink",
                description="You feel energized! Your work cooldown has been reset.",
                color=WHITE,
            )

            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # MYSTERY CASH BOX
        # =========================
        if item == "mystery_cash_box":
            db.remove_inventory(
                user_id,
                "mystery_cash_box",
                1,
            )

            amount = random.randint(
                MYSTERY_CASH_MIN,
                MYSTERY_CASH_MAX,
            )

            new_balance = db.add_balance(
                user_id,
                amount,
            )

            if amount >= 0:
                description = f"You won **{db.format_peso(amount)}**!"
            else:
                description = f"You lost **{db.format_peso(-amount)}**..."

            embed = discord.Embed(
                title="🎁 Mystery Cash Box",
                description=description,
                color=WHITE,
            )
            embed.set_footer(
                text=f"💰 Balance: {db.format_peso(new_balance)}"
            )

            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # MYSTERY CRATE
        # =========================
        if item == "mystery_crate":
            db.remove_inventory(
                user_id,
                "mystery_crate",
                1,
            )

            reward_ids = [r[0] for r in MYSTERY_CRATE_REWARDS]
            weights = [r[1] for r in MYSTERY_CRATE_REWARDS]

            reward = random.choices(
                reward_ids,
                weights=weights,
                k=1,
            )[0]

            if reward == "cash":
                amount = random.randint(
                    MYSTERY_CRATE_CASH_MIN,
                    MYSTERY_CRATE_CASH_MAX,
                )

                new_balance = db.add_balance(
                    user_id,
                    amount,
                )

                embed = discord.Embed(
                    title="📦 Mystery Crate",
                    description=f"You found **{db.format_peso(amount)}** in cash.",
                    color=WHITE,
                )
                embed.set_footer(
                    text=f"💰 Balance: {db.format_peso(new_balance)}"
                )
            else:
                emoji, name = RARE_ITEM_NAMES[reward]

                db.add_inventory(
                    user_id,
                    reward,
                    1,
                )

                embed = discord.Embed(
                    title="📦 Mystery Crate",
                    description=f"You found a {emoji} **{name}**!",
                    color=WHITE,
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
