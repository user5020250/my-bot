import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from jobs_data import JOBS, TRABAHO_COOLDOWN_SECONDS

from features.economy import ALLOWANCE_COOLDOWN_SECONDS
from features.rewards import (
    DAILY_COOLDOWN_SECONDS,
    WEEKLY_COOLDOWN_SECONDS,
    MONTHLY_COOLDOWN_SECONDS,
    YEARLY_COOLDOWN_SECONDS,
)
from features.sideline import (
    SIDELINE_COOLDOWN_SECONDS,
    FISH_COOLDOWN_SECONDS,
    MINE_COOLDOWN_SECONDS,
    FARM_COOLDOWN_SECONDS,
    HUNT_COOLDOWN_SECONDS,
    COOK_COOLDOWN_SECONDS,
)

WHITE = discord.Color(0xFFFFFF)

# Confirmed against db_utils.py (last_karaoke is an allowed cooldown
# field) and help.py's listed "Cooldown: 1 minute" for /karaoke.
KARAOKE_COOLDOWN_FIELD = "last_karaoke"
KARAOKE_COOLDOWN_SECONDS = 60

WORK_COOLDOWN_FIELD = "last_trabaho"
ALLOWANCE_COOLDOWN_FIELD = "last_baon"

VIEW_TIMEOUT_SECONDS = 120


def fmt_cooldown(user_id: str, field: str, duration: int) -> str:
    try:
        remaining = db.check_cooldown(user_id, field, duration)
    except Exception:
        return "Unknown"

    if remaining <= 0:
        return "Ready"

    return db.format_duration(remaining)


def get_inventory_stats(user_id: str):
    rows = db.get_all_inventory(user_id)

    unique = len(rows)
    total = sum(row["qty"] for row in rows)

    return unique, total


def build_main_embed(member: discord.Member) -> discord.Embed:
    user_id = str(member.id)
    user = db.get_user(user_id)
    balance = user["balance"]

    unique_items, total_items = get_inventory_stats(user_id)

    embed = discord.Embed(
        title=f"{member.display_name}",
        color=WHITE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="Money",
        value=f"Wallet: `{db.format_peso(balance)}`",
        inline=True,
    )

    current_job = user["job"]

    if current_job and current_job in JOBS:
        job_info = JOBS[current_job]
        job_range = f"`{db.format_peso(job_info['min'])} - {db.format_peso(job_info['max'])}`"
    else:
        job_info = None
        job_range = "`Unemployed`"

    embed.add_field(
        name="Job",
        value=(
            f"Current: `{job_info['label'] if job_info else 'None'}`\n"
            f"Range: {job_range}"
        ),
        inline=True,
    )

    embed.add_field(
        name="Items",
        value=(
            f"Unique: `{unique_items}`\n"
            f"Total: `{total_items}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="Information",
        value=f"User ID: `{member.id}`",
        inline=True,
    )

    embed.set_footer(text="Keep grinding  •  Main Profile")

    return embed


def build_cooldowns_embed(member: discord.Member) -> discord.Embed:
    user_id = str(member.id)

    embed = discord.Embed(
        title=f"{member.display_name}",
        color=WHITE,
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    embed.add_field(
        name="Cooldowns",
        value=(
            f"Work: `{fmt_cooldown(user_id, WORK_COOLDOWN_FIELD, TRABAHO_COOLDOWN_SECONDS)}`\n"
            f"Allowance: `{fmt_cooldown(user_id, ALLOWANCE_COOLDOWN_FIELD, ALLOWANCE_COOLDOWN_SECONDS)}`\n"
            f"Daily: `{fmt_cooldown(user_id, 'last_daily', DAILY_COOLDOWN_SECONDS)}`\n"
            f"Weekly: `{fmt_cooldown(user_id, 'last_weekly', WEEKLY_COOLDOWN_SECONDS)}`\n"
            f"Monthly: `{fmt_cooldown(user_id, 'last_monthly', MONTHLY_COOLDOWN_SECONDS)}`\n"
            f"Yearly: `{fmt_cooldown(user_id, 'last_yearly', YEARLY_COOLDOWN_SECONDS)}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="Activities",
        value=(
            f"Karaoke: `{fmt_cooldown(user_id, KARAOKE_COOLDOWN_FIELD, KARAOKE_COOLDOWN_SECONDS)}`\n"
            f"Sideline: `{fmt_cooldown(user_id, 'last_sideline', SIDELINE_COOLDOWN_SECONDS)}`\n"
            f"Fish: `{fmt_cooldown(user_id, 'last_fish', FISH_COOLDOWN_SECONDS)}`\n"
            f"Mine: `{fmt_cooldown(user_id, 'last_mine', MINE_COOLDOWN_SECONDS)}`\n"
            f"Farm: `{fmt_cooldown(user_id, 'last_farm', FARM_COOLDOWN_SECONDS)}`\n"
            f"Hunt: `{fmt_cooldown(user_id, 'last_hunt', HUNT_COOLDOWN_SECONDS)}`\n"
            f"Cook: `{fmt_cooldown(user_id, 'last_cook', COOK_COOLDOWN_SECONDS)}`"
        ),
        inline=True,
    )

    embed.set_footer(text="Keep grinding  •  Cooldowns & Activities")

    return embed


PAGES = {
    "main": build_main_embed,
    "cooldowns": build_cooldowns_embed,
}


class ProfilePageSelect(discord.ui.Select):
    def __init__(self, member: discord.Member, owner_id: int):
        self.member = member
        self.owner_id = owner_id

        options = [
            discord.SelectOption(
                label="Main Profile",
                value="main",
                description="Money, job, items, and info",
                default=True,
            ),
            discord.SelectOption(
                label="Cooldowns & Activities",
                value="cooldowns",
                description="Work, daily/weekly rewards, and activity timers",
            ),
        ]

        super().__init__(
            placeholder="Main Profile",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "Only the person who ran this command can switch pages.",
                ephemeral=True,
            )
            return

        page = self.values[0]

        # Update which option shows as selected/default.
        for option in self.options:
            option.default = option.value == page

        self.placeholder = next(
            o.label for o in self.options if o.value == page
        )

        embed = PAGES[page](self.member)

        await interaction.response.edit_message(embed=embed, view=self.view)


class ProfileView(discord.ui.View):
    def __init__(self, member: discord.Member, owner_id: int):
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.message: discord.Message | None = None
        self.add_item(ProfilePageSelect(member, owner_id))

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class Profile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="profile",
        description="View a player's profile.",
    )
    @app_commands.describe(
        member="Whose profile to view (defaults to you)",
    )
    async def profile(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        embed = build_main_embed(member)
        view = ProfileView(member, owner_id=interaction.user.id)

        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Profile(bot)
    )
