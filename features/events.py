import asyncio
import random
import time

import discord
from discord import app_commands
from discord.ext import commands, tasks

import db_utils as db
from database import get_conn

WHITE = discord.Color(0xFFFFFF)

# How often the background loop wakes up to decide whether to spawn
# an event in each configured guild.
EVENT_CHECK_INTERVAL_MINUTES = 30

# Chance, each time the loop wakes up, that a given guild (with a
# channel set and no active event) actually gets an event this tick.
# With a 5 minute interval and 20%, a guild averages one event roughly
# every 25 minutes, but the exact timing is random.
EVENT_SPAWN_CHANCE = 0.20

EVENT_TYPES = {
    "lost_wallet": {
        "name": "Lost Wallet",
        "emoji": "👛",
        "min_reward": 10_000,
        "max_reward": 30_000,
        "weight": 40,
        "claim_seconds": 300,
        "announcement": (
            "Someone dropped a wallet in the chat!\n"
            "First to `/claim` it keeps what's inside."
        ),
        "claimed_line": "grabbed the wallet before anyone else noticed.",
    },
    "treasure_chest": {
        "name": "Treasure Chest",
        "emoji": "📦",
        "min_reward": 10_000,
        "max_reward": 100_000,
        "weight": 25,
        "claim_seconds": 300,
        "announcement": (
            "A treasure chest has appeared out of nowhere!\n"
            "Use `/claim` to crack it open before someone beats you to it."
        ),
        "claimed_line": "cracked open the treasure chest.",
    },
    "cash_rain": {
        "name": "Cash Rain",
        "emoji": "💸",
        "min_reward": 5_000,
        "max_reward": 10_000,
        "weight": 25,
        "claim_seconds": 180,
        "announcement": (
            "It's raining money!\n"
            "Use `/claim` fast to scoop some up before it dries up."
        ),
        "claimed_line": "scooped up some of the falling cash.",
    },
    "atm_glitch": {
        "name": "ATM Glitch",
        "emoji": "🏧",
        "min_reward": 10_000,
        "max_reward": 10_000,
        "weight": 8,
        "claim_seconds": 30,
        "announcement": (
            "An ATM nearby is glitching out free cash!\n"
            "You have **30 seconds** to `/claim` it before it's patched."
        ),
        "claimed_line": "hit /claim just before the glitch was patched.",
    },
    "jackpot_event": {
        "name": "Jackpot Event",
        "emoji": "🎰",
        "min_reward": 100_000,
        "max_reward": 2_000_000,
        "weight": 2,
        "claim_seconds": 120,
        "announcement": (
            "**JACKPOT EVENT!** This one is extremely rare.\n"
            "Use `/claim` right now for a massive payout."
        ),
        "claimed_line": "hit the jackpot!",
    },
}


def ensure_event_table():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS event_channels (
            guild_id TEXT PRIMARY KEY,
            channel_id TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


ensure_event_table()


def get_event_channel(guild_id: int) -> int | None:
    conn = get_conn()

    row = conn.execute(
        """
        SELECT channel_id
        FROM event_channels
        WHERE guild_id = ?
        """,
        (str(guild_id),),
    ).fetchone()

    conn.close()

    return int(row["channel_id"]) if row else None


def set_event_channel(guild_id: int, channel_id: int):
    conn = get_conn()

    conn.execute(
        """
        INSERT INTO event_channels (guild_id, channel_id)
        VALUES (?, ?)

        ON CONFLICT(guild_id)

        DO UPDATE SET
            channel_id = excluded.channel_id
        """,
        (
            str(guild_id),
            str(channel_id),
        ),
    )

    conn.commit()
    conn.close()


def choose_event_key() -> str:
    keys = list(EVENT_TYPES.keys())
    weights = [EVENT_TYPES[key]["weight"] for key in keys]

    return random.choices(keys, weights=weights, k=1)[0]


def resolve_event_key(raw: str) -> str | None:
    """
    Match free-text input (from the prefix command) to an event key.
    Accepts the internal key ("lost_wallet") or the display name
    ("Lost Wallet"), case-insensitively.
    """
    normalized = raw.strip().lower().replace(" ", "_")

    if normalized in EVENT_TYPES:
        return normalized

    for key, event_type in EVENT_TYPES.items():
        display_normalized = (
            event_type["name"].strip().lower().replace(" ", "_")
        )

        if display_normalized == normalized:
            return key

    return None


def build_event_embed(event_key: str, reward: int) -> discord.Embed:
    event_type = EVENT_TYPES[event_key]

    embed = discord.Embed(
        title=f"{event_type['emoji']} {event_type['name']}",
        description=event_type["announcement"],
        color=WHITE,
    )

    embed.add_field(
        name="💰 Reward Range",
        value=(
            f"`{db.format_peso(event_type['min_reward'])} - "
            f"{db.format_peso(event_type['max_reward'])}`"
        ),
        inline=True,
    )

    embed.add_field(
        name="⏱️ Claim Window",
        value=f"`{db.format_duration(event_type['claim_seconds'])}`",
        inline=True,
    )

    embed.set_footer(
        text="Use /claim to grab it!"
    )

    return embed


def build_claimed_embed(
    event_key: str,
    reward: int,
    winner: discord.Member,
) -> discord.Embed:
    event_type = EVENT_TYPES[event_key]

    embed = discord.Embed(
        title=f"{event_type['emoji']} {event_type['name']} — Claimed!",
        description=f"{winner.mention} {event_type['claimed_line']}",
        color=WHITE,
    )

    embed.add_field(
        name="💰 Reward Won",
        value=f"`{db.format_peso(reward)}`",
        inline=False,
    )

    return embed


def build_expired_embed(event_key: str) -> discord.Embed:
    event_type = EVENT_TYPES[event_key]

    embed = discord.Embed(
        title=f"{event_type['emoji']} {event_type['name']} — Missed!",
        description="Nobody claimed it in time. Better luck next time!",
        color=WHITE,
    )

    return embed


class Events(commands.Cog):
    event_group = app_commands.Group(
        name="event",
        description="Manage random money events.",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # guild_id -> {type, reward, expires_at, message, claimed}
        self.active_events: dict[int, dict] = {}

        # guild_id -> asyncio.Lock, guards claiming/expiring an event
        # so two /claim calls (or a claim racing an expiry) can't
        # both win the same event.
        self.claim_locks: dict[int, asyncio.Lock] = {}

        self.event_loop.start()

    def cog_unload(self):
        self.event_loop.cancel()

    def get_lock(self, guild_id: int) -> asyncio.Lock:
        lock = self.claim_locks.get(guild_id)

        if lock is None:
            lock = asyncio.Lock()
            self.claim_locks[guild_id] = lock

        return lock

    # ==========================
    # Background spawner
    # ==========================

    @tasks.loop(minutes=EVENT_CHECK_INTERVAL_MINUTES)
    async def event_loop(self):
        for guild in list(self.bot.guilds):
            await self.maybe_spawn_event(guild)

    @event_loop.before_loop
    async def before_event_loop(self):
        await self.bot.wait_until_ready()

    async def maybe_spawn_event(self, guild: discord.Guild):
        if guild.id in self.active_events:
            return

        channel_id = get_event_channel(guild.id)

        if channel_id is None:
            return

        if random.random() > EVENT_SPAWN_CHANCE:
            return

        channel = guild.get_channel(channel_id)

        if channel is None:
            return

        await self.spawn_event(guild, channel)

    async def spawn_event(
        self,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        event_key: str | None = None,
    ) -> str | None:
        event_key = event_key or choose_event_key()
        event_type = EVENT_TYPES[event_key]

        reward = random.randint(
            event_type["min_reward"],
            event_type["max_reward"],
        )

        embed = build_event_embed(event_key, reward)

        try:
            message = await channel.send(embed=embed)
        except discord.HTTPException:
            return None

        now = time.time()

        self.active_events[guild.id] = {
            "type": event_key,
            "reward": reward,
            "expires_at": now + event_type["claim_seconds"],
            "message": message,
            "claimed": False,
        }

        asyncio.create_task(
            self.expire_event(
                guild.id,
                event_type["claim_seconds"],
            )
        )

        return event_key

    async def expire_event(self, guild_id: int, delay: float):
        await asyncio.sleep(delay)

        lock = self.get_lock(guild_id)

        async with lock:
            event = self.active_events.get(guild_id)

            if event is None or event["claimed"]:
                return

            event["claimed"] = True

            embed = build_expired_embed(event["type"])

            try:
                await event["message"].edit(embed=embed)
            except discord.HTTPException:
                pass

            self.active_events.pop(guild_id, None)

    # ==========================
    # /event setchannel
    # ==========================

    @event_group.command(
        name="setchannel",
        description="Set the channel where random money events will be announced.",
    )
    @app_commands.describe(
        channel="Channel to send event announcements to",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setchannel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        set_event_channel(interaction.guild.id, channel.id)

        await interaction.response.send_message(
            f"✅ Random events will now be announced in {channel.mention}."
        )

    @setchannel.error
    async def setchannel_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You need the `Manage Server` permission to do that.",
                ephemeral=True,
            )
            return

        raise error

    # ==========================
    # !trigger (owner-only prefix command)
    # ==========================

    @commands.command(
        name="trigger",
        help="Manually start an event now. Owner only.",
    )
    @commands.is_owner()
    async def trigger(
        self,
        ctx: commands.Context,
        *,
        event_type: str = None,
    ):
        guild = ctx.guild

        if guild is None:
            await ctx.send(
                "❌ This command can only be used in a server."
            )
            return

        channel_id = get_event_channel(guild.id)

        if channel_id is None:
            await ctx.send(
                "❌ No event channel is set. Use `/event setchannel` first."
            )
            return

        if guild.id in self.active_events:
            await ctx.send(
                "❌ There's already an active event — wait for it to be claimed or expire."
            )
            return

        channel = guild.get_channel(channel_id)

        if channel is None:
            await ctx.send(
                "❌ The configured event channel no longer exists. "
                "Use `/event setchannel` to set a new one."
            )
            return

        requested_key = None

        if event_type:
            requested_key = resolve_event_key(event_type)

            if requested_key is None:
                valid = ", ".join(
                    f"`{et['name']}`" for et in EVENT_TYPES.values()
                )
                await ctx.send(
                    f"❌ Unknown event type. Choose from: {valid}"
                )
                return

        spawned_key = await self.spawn_event(
            guild,
            channel,
            event_key=requested_key,
        )

        if spawned_key is None:
            await ctx.send(
                "❌ Couldn't send the event to that channel — check my permissions there."
            )
            return

        await ctx.send(
            f"✅ Started a **{EVENT_TYPES[spawned_key]['name']}** "
            f"event in {channel.mention}!"
        )

    @trigger.error
    async def trigger_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        if isinstance(error, commands.NotOwner):
            await ctx.send(
                "❌ Only the bot owner can use that command."
            )
            return

        raise error

    # ==========================
    # /claim
    # ==========================

    @app_commands.command(
        name="claim",
        description="Claim the current active event, if there is one.",
    )
    @app_commands.guild_only()
    async def claim(
        self,
        interaction: discord.Interaction,
    ):
        guild_id = interaction.guild.id
        event = self.active_events.get(guild_id)

        if event is None:
            await interaction.response.send_message(
                "❌ There's no active event to claim right now.",
                ephemeral=True,
            )
            return

        now = time.time()

        if now > event["expires_at"]:
            await interaction.response.send_message(
                "❌ That event already expired.",
                ephemeral=True,
            )
            return

        lock = self.get_lock(guild_id)

        async with lock:
            event = self.active_events.get(guild_id)

            if event is None or event["claimed"]:
                await interaction.response.send_message(
                    "❌ Someone already claimed that event.",
                    ephemeral=True,
                )
                return

            event["claimed"] = True

            event_key = event["type"]
            reward = event["reward"]

            new_balance = db.add_balance(
                str(interaction.user.id),
                reward,
            )

            embed = build_claimed_embed(
                event_key,
                reward,
                interaction.user,
            )

            try:
                await event["message"].edit(embed=embed)
            except discord.HTTPException:
                pass

            self.active_events.pop(guild_id, None)

        await interaction.response.send_message(
            (
                f"🎉 You claimed the **{EVENT_TYPES[event_key]['name']}** "
                f"and won `{db.format_peso(reward)}`!\n"
                f"💰 New Balance: `{db.format_peso(new_balance)}`"
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Events(bot)
    )
