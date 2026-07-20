"""
Corruption-themed strategy game (slash commands).
"""

import json
import os
import random
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta, timezone

from .config import EMBED_COLOR, OWNER_ID

DATA_FILE = "corruption_data.json"

CAMPAIGN_COOLDOWN_HOURS = 6
CAMPAIGN_REP_RANGE = (5, 15)
CAMPAIGN_SUPPORTER_RANGE = (1, 5)

BRIBE_COOLDOWN_HOURS = 4
BRIBE_CATCH_CHANCE = 0.35
BRIBE_INFLUENCE_PER_100 = 10

CONTRACT_COOLDOWN_HOURS = 8
CONTRACT_MIN_REWARD = 50
CONTRACT_MAX_REWARD = 300
CONTRACT_FAIL_CHANCE = 0.25

LAUNDER_FEE_PERCENT = 0.15
LAUNDER_COOLDOWN_HOURS = 3

INVESTIGATE_COOLDOWN_HOURS = 12
INVESTIGATE_SUCCESS_CHANCE = 0.5
INVESTIGATE_COST = 50

RAID_COOLDOWN_HOURS = 12
RAID_SUCCESS_CHANCE = 0.4
RAID_STEAL_PERCENT = 0.2
RAID_FAIL_PENALTY_PERCENT = 0.1

COURT_COST = 100


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def now_utc():
    return datetime.now(timezone.utc)


class Corruption(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    def get_profile(self, user_id):
        uid = str(user_id)
        if uid not in self.data:
            self.data[uid] = {
                "money": 0,
                "dirty_money": 0,
                "influence": 0,
                "reputation": 0,
                "supporters": 0,
                "caught": False,
                "allies": [],
                "cooldowns": {},
            }
        return self.data[uid]

    def on_cooldown(self, profile, key, hours):
        last = profile["cooldowns"].get(key)
        if not last:
            return None
        last_time = datetime.fromisoformat(last)
        next_time = last_time + timedelta(hours=hours)
        if now_utc() < next_time:
            return next_time - now_utc()
        return None

    def set_cooldown(self, profile, key):
        profile["cooldowns"][key] = now_utc().isoformat()

    def fmt_delta(self, delta):
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes = remainder // 60
        return f"{hours}h {minutes}m"

    def save(self):
        save_data(self.data)

    # ---------- /help ----------

    @app_commands.command(name="help", description="Show all corruption game commands and how they work.")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Corruption Game — Command Guide",
            description="Build your empire, dodge the law, and climb to the top.",
            color=EMBED_COLOR,
        )

        embed.add_field(name="📣 /campaign", value="Gain supporters and reputation.", inline=False)
        embed.add_field(name="🤫 /bribe `amount`", value="Spend money to increase your influence, but risk getting caught.", inline=False)
        embed.add_field(name="🤝 /connections `[member]`", value="View your network, or recruit a new ally for bonuses.", inline=False)
        embed.add_field(name="📄 /contracts", value="Complete shady deals for dirty money rewards.", inline=False)
        embed.add_field(name="🧺 /launder `[amount]`", value='Convert "dirty money" into usable currency (a fee applies).', inline=False)
        embed.add_field(name="🔍 /investigate `member`", value="Try to uncover another player's secrets.", inline=False)
        embed.add_field(name="💥 /raid `member`", value="Steal part of another player's resources — risky if it fails.", inline=False)
        embed.add_field(name="⚖️ /court", value="Defend yourself if you've been caught bribing or raiding.", inline=False)
        embed.add_field(name="🗳️ /election", value="See who currently holds the most influence and wins the title.", inline=False)
        embed.add_field(name="🏆 /leaderboard `[category]`", value="Rank players by money, influence, or reputation.", inline=False)
        embed.add_field(name="🎁 /donate `member` `amount`", value="Give another player some of your money.", inline=False)

        embed.set_footer(text="Tip: most actions have cooldowns, so plan your moves wisely.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- /campaign ----------

    @app_commands.command(name="campaign", description="Gain supporters and reputation.")
    async def campaign(self, interaction: discord.Interaction):
        profile = self.get_profile(interaction.user.id)
        remaining = self.on_cooldown(profile, "campaign", CAMPAIGN_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ Your campaign team needs rest. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return

        rep_gain = random.randint(*CAMPAIGN_REP_RANGE)
        supporters_gain = random.randint(*CAMPAIGN_SUPPORTER_RANGE)
        profile["reputation"] += rep_gain
        profile["supporters"] += supporters_gain
        self.set_cooldown(profile, "campaign")
        self.save()

        embed = discord.Embed(
            title="📣 Campaign Trail",
            description=(
                f"You held a rally and won over the crowd.\n"
                f"+{rep_gain} reputation, +{supporters_gain} supporters\n\n"
                f"**Reputation:** {profile['reputation']} | **Supporters:** {profile['supporters']}"
            ),
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /bribe ----------

    @app_commands.command(name="bribe", description="Spend money to increase your influence, but risk getting caught.")
    @app_commands.describe(amount="How much money to spend on the bribe")
    async def bribe(self, interaction: discord.Interaction, amount: int):
        profile = self.get_profile(interaction.user.id)
        remaining = self.on_cooldown(profile, "bribe", BRIBE_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ Your contacts are lying low. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return
        if profile["money"] < amount:
            await interaction.response.send_message(
                f"You don't have enough money. Balance: {profile['money']}", ephemeral=True
            )
            return

        self.set_cooldown(profile, "bribe")
        profile["money"] -= amount
        caught = random.random() < BRIBE_CATCH_CHANCE

        if caught:
            profile["caught"] = True
            profile["reputation"] = max(0, profile["reputation"] - 15)
            self.save()
            embed = discord.Embed(
                title="🚨 Bribe Exposed!",
                description=(
                    f"You spent 💰{amount} trying to bribe an official — but it leaked to the press.\n"
                    f"-15 reputation, and you're now **flagged** (use `/court` to clear it)."
                ),
                color=discord.Color.red(),
            )
        else:
            influence_gain = (amount // 100) * BRIBE_INFLUENCE_PER_100
            profile["influence"] += influence_gain
            self.save()
            embed = discord.Embed(
                title="🤫 Bribe Successful",
                description=(
                    f"You quietly spent 💰{amount} and gained **{influence_gain}** influence.\n"
                    f"**Influence:** {profile['influence']}"
                ),
                color=EMBED_COLOR,
            )
        await interaction.response.send_message(embed=embed)

    # ---------- /connections ----------

    @app_commands.command(name="connections", description="View or build your network of allies.")
    @app_commands.describe(member="Recruit this user as an ally (leave empty to view your network)")
    async def connections(self, interaction: discord.Interaction, member: discord.Member = None):
        profile = self.get_profile(interaction.user.id)

        if member is None:
            allies = profile.get("allies", [])
            if not allies:
                await interaction.response.send_message(
                    "You have no allies yet. Use `/connections member:@user` to recruit one.",
                    ephemeral=True,
                )
                return
            names = []
            for uid in allies:
                m = interaction.guild.get_member(int(uid))
                names.append(m.display_name if m else f"User {uid}")
            bonus = len(allies) * 2
            embed = discord.Embed(
                title="🤝 Your Network",
                description=f"Allies: {', '.join(names)}\nNetwork bonus: +{bonus}% (flavor only for now)",
                color=EMBED_COLOR,
            )
            await interaction.response.send_message(embed=embed)
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't recruit yourself.", ephemeral=True)
            return

        ally_id = str(member.id)
        if ally_id in profile["allies"]:
            await interaction.response.send_message(f"{member.display_name} is already
