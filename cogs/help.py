import discord
from discord import app_commands
from discord.ext import commands

WHITE = discord.Color(0xFFFFFF)
COMMANDS_PER_PAGE = 5

INTRO = (
    "Starting money: **₱1,000**. Everything's in pesos (₱). Use the arrows below to "
    "browse commands, or hit ✖ to close this menu whenever you're done. Let's get this bread."
)

COMMANDS = [
    (
        "💼 /jobs",
        "See every job on the market and how much each one pays. No commitment, just vibes.",
    ),
    (
        "👔 /trabaho job: <pick>",
        "Pick or switch your job. Run `/trabaho` again with no `job` param to actually clock in "
        "and get paid. Cooldown: 30 min.",
    ),
    (
        "🧢 /tambay",
        "Hang out with the barkada for a shot at quick cash. 70% chance you win small, "
        "30% chance it costs you (yosi, snacks, you know how it is). Cooldown: 1 min.",
    ),
    (
        "🎲 /sugal amount: <₱>",
        "50/50 coinflip bet. Go big or go broke — no limit on the bet, no cooldown either.",
    ),
    (
        "🥬 /palengke presyo",
        "Check today's prices for rice, fish, mangoes, chicken, meat, and veggies. "
        "Prices shift every few hours, stay updated.",
    ),
    (
        "🛒 /palengke bili item: <pick> quantity: <n>",
        "Buy goods from the palengke to stock up or flip later.",
    ),
    (
        "💵 /palengke benta item: <pick> quantity: <n>",
        "Sell whatever you bought. Buy low, sell high, that's the whole game.",
    ),
    (
        "📱 /load bili quantity: <n>",
        "Buy mobile load in bulk to resell at a markup later.",
    ),
    (
        "📲 /load benta quantity: <n>",
        "Resell your load. Profit's random — could be cha-ching, could be a flop.",
    ),
    (
        "🤝 /utang lender:<@user> amount: <₱>",
        "Borrow cash from another player. No cooldown, but don't be that friend who ghosts on payback.",
    ),
    (
        "💸 /bayad lender:<@user> amount: <₱>",
        "Pay back what you owe. Do it before it gets awkward.",
    ),
    (
        "🎭 /budol target: <@user>",
        "Attempt to scam someone. Big payout if it works, real penalty if you get caught. "
        "Cooldown: 1 day. High risk, high reward, act accordingly.",
    ),
    (
        "🎤 /karaoke",
        "Sing for tips, ₱50-₱500. Confidence not required. Cooldown: 5 min.",
    ),
    (
        "🎒 /baon",
        "Claim your daily allowance, ₱50-₱100. Cooldown: 24 hrs, don't be greedy.",
    ),
    (
        "🪪 /profile user: <@user>",
        "Check your (or someone else's) balance, job, and cooldown status at a glance. "
        "Leave `user` blank to check yourself.",
    ),
]

# Chunk into pages of 5 commands each.
PAGES = [COMMANDS[i : i + COMMANDS_PER_PAGE] for i in range(0, len(COMMANDS), COMMANDS_PER_PAGE)]


class HelpView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.index = 0
        self.message: discord.Message | None = None

    def make_embed(self) -> discord.Embed:
        page = PAGES[self.index]
        embed = discord.Embed(
            title="Commands",
            description=INTRO if self.index == 0 else None,
            color=WHITE,
        )
        for name, desc in page:
            embed.add_field(name=name, value=desc, inline=False)
        embed.set_footer(text=f"Page {self.index + 1}/{len(PAGES)} • Pinoy Economy Bot")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your menu bestie, run `/help` yourself 👀", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(PAGES)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="Help menu closed. Pull it up again anytime with `/help`.",
            embed=None,
            view=None,
        )
        self.stop()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(PAGES)
        await interaction.response.edit_message(embed=self.make_embed(), view=self)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Browse all commands and how to use them.")
    async def help(self, interaction: discord.Interaction):
        view = HelpView(interaction.user.id)
        await interaction.response.send_message(embed=view.make_embed(), view=view)
        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
