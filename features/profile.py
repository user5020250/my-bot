import discord
from discord import app_commands
from discord.ext import commands
import db_utils as db
from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS
WHITE = discord.Color(0x2B2D31)
SIDELINE_COOLDOWN_SECONDS = 60
BAON_COOLDOWN_SECONDS = 24 * 60 * 60
KARAOKE_COOLDOWN_SECONDS = 60
class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    @app_commands.command(
        name="profile",
        description="View a profile.",
    )
    @app_commands.describe(
        user="Leave blank to view yourself."
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        user: discord.Member = None,
    ):
        target = user or interaction.user
        user_id = str(target.id)
        data = db.get_user(user_id)
        job_key = data["job"]
        job_label = (
            JOBS[job_key]["label"]
            if job_key in JOBS
            else "Unemployed"
        )
        trabaho_cd = db.check_cooldown(
            user_id,
            "last_trabaho",
            TRABAHO_COOLDOWN_SECONDS,
        )
        sideline_cd = db.check_cooldown(
            user_id,
            "last_sideline",
            SIDELINE_COOLDOWN_SECONDS,
        )
        baon_cd = db.check_cooldown(
            user_id,
            "last_baon",
            BAON_COOLDOWN_SECONDS,
        )
        karaoke_cd = db.check_cooldown(
            user_id,
            "last_karaoke",
            KARAOKE_COOLDOWN_SECONDS,
        )
        inventory = db.get_all_inventory(
            user_id
        )
        unique_items = len(
            inventory
        )
        total_items = sum(
            item["qty"]
            for item in inventory
        )
        inventory_value = sum(
            item["qty"] * item["avg_buy_price"]
            for item in inventory
        )
        embed = discord.Embed(
            color=WHITE,
        )
        embed.set_author(
            name=f"{target.display_name}'s Profile",
            icon_url=target.display_avatar.url,
        )
        embed.set_thumbnail(
            url=target.display_avatar.url
        )
        embed.add_field(
            name="💰 Money",
            value=(
                f"Wallet: `{db.format_peso(data['balance'])}`\n"
                f"Net Worth: `{db.format_peso(data['balance'] + inventory_value)}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="💼 Job",
            value=(
                f"Current: `{job_label}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎒 Inventory",
            value=(
                f"Unique: `{unique_items}`\n"
                f"Total: `{total_items}`\n"
                f"Value: `{db.format_peso(inventory_value)}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="⚡ Cooldowns",
            value=(
                f"Work: "
                f"`{'Ready' if trabaho_cd == 0 else db.format_duration(trabaho_cd)}`\n"
                f"Sideline: "
                f"`{'Ready' if sideline_cd == 0 else db.format_duration(sideline_cd)}`\n"
                f"Daily Allowance: "
                f"`{'Ready' if baon_cd == 0 else db.format_duration(baon_cd)}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="🎤 Activities",
            value=(
                f"Karaoke: "
                f"`{'Ready' if karaoke_cd == 0 else db.format_duration(karaoke_cd)}`"
            ),
            inline=True,
        )
        embed.add_field(
            name="📋 Information",
            value=(
                f"User ID:\n"
                f"`{target.id}`"
            ),
            inline=True,
        )
        embed.set_footer(
            text="Keep grinding 💸"
        )
        await interaction.response.send_message(
            embed=embed
        )
async def setup(bot: commands.Bot):
    await bot.add_cog(
        Profile(bot)
    )
