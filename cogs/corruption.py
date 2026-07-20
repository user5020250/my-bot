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
            await interaction.response.send_message(f"{member.display_name} is already your ally.", ephemeral=True)
            return

        profile["allies"].append(ally_id)
        self.save()
        embed = discord.Embed(
            title="🤝 New Alliance",
            description=f"{interaction.user.mention} formed an alliance with {member.mention}.",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /contracts ----------

    @app_commands.command(name="contracts", description="Complete shady deals for rewards.")
    async def contracts(self, interaction: discord.Interaction):
        profile = self.get_profile(interaction.user.id)
        remaining = self.on_cooldown(profile, "contracts", CONTRACT_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ No new contracts available. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return

        self.set_cooldown(profile, "contracts")
        failed = random.random() < CONTRACT_FAIL_CHANCE

        if failed:
            self.save()
            embed = discord.Embed(
                title="📄 Contract Fell Through",
                description="The deal fell apart at the last minute. No reward this time.",
                color=discord.Color.orange(),
            )
        else:
            reward = random.randint(CONTRACT_MIN_REWARD, CONTRACT_MAX_REWARD)
            profile["dirty_money"] += reward
            self.save()
            embed = discord.Embed(
                title="📄 Contract Completed",
                description=(
                    f"You closed a shady deal and earned 💵**{reward}** dirty money.\n"
                    f"Use `/launder` to convert it into usable funds.\n\n"
                    f"**Dirty Money:** {profile['dirty_money']}"
                ),
                color=EMBED_COLOR,
            )
        await interaction.response.send_message(embed=embed)

    # ---------- /launder ----------

    @app_commands.command(name="launder", description='Convert "dirty money" into usable currency.')
    @app_commands.describe(amount="Amount to launder (leave empty to launder all)")
    async def launder(self, interaction: discord.Interaction, amount: int = None):
        profile = self.get_profile(interaction.user.id)
        remaining = self.on_cooldown(profile, "launder", LAUNDER_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ Your laundering front is busy. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return

        if amount is None:
            amount = profile["dirty_money"]

        if amount <= 0 or amount > profile["dirty_money"]:
            await interaction.response.send_message(
                f"Invalid amount. Dirty money available: {profile['dirty_money']}", ephemeral=True
            )
            return

        self.set_cooldown(profile, "launder")
        fee = int(amount * LAUNDER_FEE_PERCENT)
        clean_amount = amount - fee

        profile["dirty_money"] -= amount
        profile["money"] += clean_amount
        self.save()

        embed = discord.Embed(
            title="🧺 Money Laundered",
            description=(
                f"Converted 💵{amount} dirty money → 💰{clean_amount} clean money "
                f"(lost {fee} to fees).\n\n"
                f"**Balance:** {profile['money']} | **Dirty Money:** {profile['dirty_money']}"
            ),
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /investigate ----------

    @app_commands.command(name="investigate", description="Try to uncover another player's secrets.")
    @app_commands.describe(member="The player to investigate")
    async def investigate(self, interaction: discord.Interaction, member: discord.Member):
        profile = self.get_profile(interaction.user.id)
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't investigate yourself.", ephemeral=True)
            return

        remaining = self.on_cooldown(profile, "investigate", INVESTIGATE_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ Your investigator needs time. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return
        if profile["money"] < INVESTIGATE_COST:
            await interaction.response.send_message(
                f"You need 💰{INVESTIGATE_COST} to hire an investigator.", ephemeral=True
            )
            return

        profile["money"] -= INVESTIGATE_COST
        self.set_cooldown(profile, "investigate")
        target = self.get_profile(member.id)
        success = random.random() < INVESTIGATE_SUCCESS_CHANCE
        self.save()

        if success:
            embed = discord.Embed(
                title="🔍 Investigation Successful",
                description=(
                    f"You dug up dirt on {member.mention}:\n"
                    f"💰 Money: ~{target['money']}\n"
                    f"💵 Dirty Money: {target['dirty_money']}\n"
                    f"🚩 Flagged: {'Yes' if target['caught'] else 'No'}"
                ),
                color=EMBED_COLOR,
            )
        else:
            embed = discord.Embed(
                title="🔍 Investigation Failed",
                description=f"Your investigator came back empty-handed. You lost 💰{INVESTIGATE_COST}.",
                color=discord.Color.orange(),
            )
        await interaction.response.send_message(embed=embed)

    # ---------- /raid ----------

    @app_commands.command(name="raid", description="Steal part of another player's resources.")
    @app_commands.describe(member="The player to raid")
    async def raid(self, interaction: discord.Interaction, member: discord.Member):
        profile = self.get_profile(interaction.user.id)
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't raid yourself.", ephemeral=True)
            return

        remaining = self.on_cooldown(profile, "raid", RAID_COOLDOWN_HOURS)
        if remaining:
            await interaction.response.send_message(
                f"⏳ Your crew is regrouping. Try again in {self.fmt_delta(remaining)}.",
                ephemeral=True,
            )
            return

        target = self.get_profile(member.id)
        self.set_cooldown(profile, "raid")
        success = random.random() < RAID_SUCCESS_CHANCE

        if success:
            stolen = int(target["money"] * RAID_STEAL_PERCENT)
            target["money"] -= stolen
            profile["money"] += stolen
            self.save()
            embed = discord.Embed(
                title="💥 Raid Successful",
                description=f"You raided {member.mention} and stole 💰**{stolen}**!",
                color=EMBED_COLOR,
            )
        else:
            penalty = int(profile["money"] * RAID_FAIL_PENALTY_PERCENT)
            profile["money"] -= penalty
            profile["caught"] = True
            self.save()
            embed = discord.Embed(
                title="🚨 Raid Failed",
                description=(
                    f"Your raid on {member.mention} was foiled! "
                    f"You lost 💰{penalty} and are now **flagged** (use `/court`)."
                ),
                color=discord.Color.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ---------- /court ----------

    @app_commands.command(name="court", description="Defend yourself if you're accused.")
    async def court(self, interaction: discord.Interaction):
        profile = self.get_profile(interaction.user.id)
        if not profile["caught"]:
            await interaction.response.send_message("You're not currently flagged. Nothing to defend against.", ephemeral=True)
            return
        if profile["money"] < COURT_COST:
            await interaction.response.send_message(
                f"You need 💰{COURT_COST} to hire a defense. Balance: {profile['money']}", ephemeral=True
            )
            return

        profile["money"] -= COURT_COST
        cleared = random.random() < 0.7
        if cleared:
            profile["caught"] = False
            self.save()
            embed = discord.Embed(
                title="⚖️ Case Dismissed",
                description=f"Your lawyers got the charges dropped. Spent 💰{COURT_COST}.",
                color=EMBED_COLOR,
            )
        else:
            profile["reputation"] = max(0, profile["reputation"] - 10)
            self.save()
            embed = discord.Embed(
                title="⚖️ Found Guilty",
                description="The court wasn't convinced. -10 reputation, and you're still flagged.",
                color=discord.Color.red(),
            )
        await interaction.response.send_message(embed=embed)

    # ---------- /election ----------

    @app_commands.command(name="election", description="Compete for special titles based on influence.")
    async def election(self, interaction: discord.Interaction):
        if not self.data:
            await interaction.response.send_message("No candidates yet. Someone needs to build influence first.")
            return

        ranked = sorted(self.data.items(), key=lambda x: x[1].get("influence", 0), reverse=True)
        winner_id, winner_profile = ranked[0]
        member = interaction.guild.get_member(int(winner_id))
        name = member.display_name if member else f"User {winner_id}"

        embed = discord.Embed(
            title="🗳️ Election Results",
            description=f"**{name}** wins the election with **{winner_profile.get('influence', 0)}** influence!\nTitle earned: 👑 *Power Broker*",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /leaderboard ----------

    @app_commands.command(name="leaderboard", description="Rank players by wealth, influence, or reputation.")
    @app_commands.describe(category="Which stat to rank by")
    @app_commands.choices(category=[
        app_commands.Choice(name="Money", value="money"),
        app_commands.Choice(name="Influence", value="influence"),
        app_commands.Choice(name="Reputation", value="reputation"),
    ])
    async def leaderboard(self, interaction: discord.Interaction, category: app_commands.Choice[str] = None):
        cat = category.value if category else "money"
        ranked = sorted(self.data.items(), key=lambda x: x[1].get(cat, 0), reverse=True)[:10]
        if not ranked:
            await interaction.response.send_message("No players yet.")
            return

        description = ""
        for i, (uid, info) in enumerate(ranked, start=1):
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            description += f"**{i}.** {name} — {info.get(cat, 0)} {cat}\n"

        embed = discord.Embed(
            title=f"🏆 Leaderboard: {cat.title()}",
            description=description,
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /donate ----------

    @app_commands.command(name="donate", description="Give another player some of your money.")
    @app_commands.describe(member="Who to donate to", amount="How much money to give")
    async def donate(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't donate to yourself.", ephemeral=True)
            return
        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        profile = self.get_profile(interaction.user.id)
        if profile["money"] < amount:
            await interaction.response.send_message(
                f"You don't have enough money. Balance: {profile['money']}", ephemeral=True
            )
            return

        target_profile = self.get_profile(member.id)
        profile["money"] -= amount
        target_profile["money"] += amount
        self.save()

        embed = discord.Embed(
            title="🎁 Donation Sent",
            description=f"{interaction.user.mention} donated 💰**{amount}** to {member.mention}.",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed)

    # ---------- /give (owner only) ----------

    @app_commands.command(name="give", description="[Owner only] Give any player any amount of money.")
    @app_commands.describe(member="Who to give money to", amount="How much money to give")
    async def give(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("🚫 Only the bot owner can use this command.", ephemeral=True)
            return

        target_profile = self.get_profile(member.id)
        target_profile["money"] += amount
        self.save()

        embed = discord.Embed(
            title="👑 Owner Grant",
            description=f"Gave 💰**{amount}** to {member.mention}.\nNew balance: {target_profile['money']}",
            color=EMBED_COLOR,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Corruption(bot))
