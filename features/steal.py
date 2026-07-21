import random
import time

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

STEAL_COOLDOWN_SECONDS = 24 * 60 * 60
ALARM_COOLDOWN_SECONDS = 48 * 60 * 60

STEAL_BRACKETS = [
    (0, 0.30, 0.60),           # ₱0+
    (100_000, 0.40, 0.80),    # ₱100k+
    (500_000, 0.50, 1.00),    # ₱500k+
    (1_000_000, 0.75, 1.25),  # ₱1m+
    (5_000_000, 0.80, 1.50),  # ₱5m+
    (10_000_000, 1.00, 2.00), # ₱10m+
]

STEAL_MIN_TARGET_BALANCE = 1_000

BASE_CATCH_CHANCE = 0.15
GLOVES_CATCH_REDUCTION = 0.07
MASK_CATCH_REDUCTION = 0.08
MIN_CATCH_CHANCE = 0.02

INSURANCE_REFUND_PERCENT = 0.40


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


def get_steal_percent(balance: int) -> float:
    minimum = 0.30
    maximum = 0.60

    for threshold, low, high in STEAL_BRACKETS:
        if balance >= threshold:
            minimum = low
            maximum = high

    return random.uniform(
        minimum,
        maximum,
    )


class Steal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        db.ensure_status_effect_columns()

    @app_commands.command(
        name="steal",
        description="Attempt to steal money from another player.",
    )
    @app_commands.describe(
        target="Who to steal from",
    )
    async def steal(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        thief_id = str(interaction.user.id)
        target_id = str(target.id)

        if target_id == thief_id:
            await interaction.response.send_message(
                "🚫 You can't steal from yourself."
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "🤖 Bots can't be robbed."
            )
            return

        remaining = db.check_cooldown(
            thief_id,
            "last_budol",
            STEAL_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"🕒 You need to lay low.\n"
                f"Try again in **{db.format_duration(remaining)}**."
            )
            return

        now = int(time.time())

        protected_until = get_protected_until(
            target_id
        )

        if protected_until > now:
            await interaction.response.send_message(
                f"🔒 {target.mention} is protected by a padlock for another "
                f"**{db.format_duration(protected_until - now)}**."
            )
            return

        target_user = db.get_user(
            target_id
        )

        balance = target_user["balance"]

        if balance < STEAL_MIN_TARGET_BALANCE:
            await interaction.response.send_message(
                f"💸 {target.mention} barely has any money."
            )
            return

        # =========================
        # Consume gloves / mask buffs
        # =========================
        thief_status = db.get_business_status(
            thief_id
        )

        gloves_active = thief_status["gloves_until"] > now
        mask_active = thief_status["mask_until"] > now

        if gloves_active:
            db.set_status_field(
                thief_id,
                "gloves_until",
                0,
            )

        if mask_active:
            db.set_status_field(
                thief_id,
                "mask_until",
                0,
            )

        catch_chance = BASE_CATCH_CHANCE

        if gloves_active:
            catch_chance -= GLOVES_CATCH_REDUCTION

        if mask_active:
            catch_chance -= MASK_CATCH_REDUCTION

        catch_chance = max(
            MIN_CATCH_CHANCE,
            catch_chance,
        )

        caught = random.random() < catch_chance

        db.set_cooldown(
            thief_id,
            "last_budol",
            now,
        )

        # =========================
        # CAUGHT
        # =========================
        if caught:
            target_has_alarm = db.has_item(
                target_id,
                "alarm_system",
                1,
            )

            if target_has_alarm:
                db.remove_inventory(
                    target_id,
                    "alarm_system",
                    1,
                )

                db.set_cooldown(
                    thief_id,
                    "last_budol",
                    now - STEAL_COOLDOWN_SECONDS + ALARM_COOLDOWN_SECONDS,
                )

                description = (
                    f"🚨 {target.mention}'s alarm system went off! "
                    f"You've been caught and slapped with a longer cooldown."
                )
            else:
                description = (
                    f"🚔 You got caught trying to steal from {target.mention}!"
                )

            embed = discord.Embed(
                title="🚫 Robbery Failed",
                description=description,
                color=WHITE,
            )

            await interaction.response.send_message(
                embed=embed
            )
            return

        # =========================
        # SUCCESS
        # =========================
        percent = get_steal_percent(
            balance
        )

        stolen = round(
            balance * percent
        )

        db.add_balance(
            target_id,
            -stolen,
        )

        new_balance = db.add_balance(
            thief_id,
            stolen,
        )

        insurance_note = ""

        target_has_insurance = db.has_item(
            target_id,
            "insurance",
            1,
        )

        if target_has_insurance:
            db.remove_inventory(
                target_id,
                "insurance",
                1,
            )

            refund = round(
                stolen * INSURANCE_REFUND_PERCENT
            )

            db.add_balance(
                target_id,
                refund,
            )

            insurance_note = (
                f"\n\n🛡️ {target.mention}'s insurance refunded them "
                f"**{db.format_peso(refund)}**."
            )

        embed = discord.Embed(
            title="🥷 Robbery Success",
            description=(
                f"You stole **{db.format_peso(stolen)}** "
                f"from {target.mention}.\n\n"
                f"That's **{percent * 100:.0f}%** "
                f"of their balance."
                f"{insurance_note}"
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=(
                f"💰 Balance: "
                f"{db.format_peso(new_balance)}"
            )
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Steal(bot)
    )
