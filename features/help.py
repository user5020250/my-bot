import discord
from discord import app_commands
from discord.ext import commands

WHITE = discord.Color(0xFFFFFF)
COMMANDS_PER_PAGE = 5

INTRO = (
    "Starting money: **₱1,000**. Everything is in pesos (₱). "
    "Use the buttons below to browse commands, or press ✖ to close this menu."
)

CATEGORIES = [
    (
        "💰 Economy",
        [
            (
                "💼 /jobs",
                "View all available jobs and see how much each one pays.",
            ),
            (
                "👔 /work: [job]",
                "Choose or switch jobs. Run `/work` without selecting a job to work and get paid. Cooldown: 8 hours.",
            ),
            (
                "🎰 /scatter: [₱]",
                "Flip a coin and bet your money. Win big or lose everything. No cooldown.",
            ),
            (
                "🎤 /karaoke",
                "Sing for tips and earn ₱50–₱500. Cooldown: 5 minutes.",
            ),
            (
                "💵 /allowance",
                "Claim your daily allowance of ₱50–₱100. Cooldown: 24 hours.",
            ),
            (
                "☀️ /daily",
                "Claim your daily reward.",
            ),
            (
                "📅 /weekly",
                "Claim your weekly reward.",
            ),
            (
                "🎉 /yearly",
                "Claim your yearly reward.",
            ),
        ],
    ),
    (
        "🏦 Loans",
        [
            (
                "📨 /loan request lender: [user] amount: [₱]",
                "Send a loan request to another player. They get 60 seconds to approve or decline. 20% interest, due in 7 days.",
            ),
            (
                "💵 /loan pay id: [id] amount: [₱]",
                "Pay off your active loans, oldest due date first.",
            ),
            (
                "📒 /loan list",
                "See all loans you owe and all loans owed to you.",
            ),
            (
                "📄 /loan info loan_id: [id]",
                "View details for a specific loan.",
            ),
            (
                "❌ /loan cancel request_id: [id]",
                "Cancel a loan request you sent before the lender responds.",
            ),
        ],
    ),
    (
        "😈 Scamming",
        [
            (
                "🎭 /scam target: [user]",
                "Try to scam another player. High risk, high reward. Cooldown: 1 day.",
            ),
        ],
    ),
    (
        "💼 Businesses",
        [
            (
                "📋 /business list",
                "Show all available businesses and their prices.",
            ),
            (
                "🛒 /business buy business: [business]",
                "Buy a business.",
            ),
            (
                "💰 /business sell business: [business]",
                "Sell a business back to the bot.",
            ),
            (
                "📊 /business portfolio",
                "Show all businesses you own.",
            ),
            (
                "💵 /business collect business: [business]",
                "Collect income from one business, or leave it blank to collect from all of them.",
            ),
            (
                "⬆️ /business upgrade business: [business]",
                "Upgrade a business to increase its income.",
            ),
            (
                "📈 /business stats business: [business]",
                "Show lifetime earnings, level, and next upgrade cost for a business.",
            ),
            (
                "🏆 /business leaderboard",
                "Show the richest business owners.",
            ),
            (
                "🏴‍☠️ /business raid target: [user]",
                "Attempt to steal from another player's business.",
            ),
            (
                "🛡️ /business defend",
                "Hire security for temporary protection against raids.",
            ),
            (
                "💥 /business bankrupt business: [business]",
                "Close a business permanently. No refund.",
            ),
        ],
    ),
    (
        "ℹ️ Info",
        [
            (
                "👤 /profile user: [user]",
                "View your profile or another player's balance, job, and cooldowns.",
            ),
        ],
    ),
]

PAGES = []

for category_name, category_commands in CATEGORIES:
    chunks = [
        category_commands[i:i + COMMANDS_PER_PAGE]
        for i in range(0, len(category_commands), COMMANDS_PER_PAGE)
    ] or [[]]

    for chunk in chunks:
        PAGES.append(
            {
                "category": category_name,
                "commands": chunk,
            }
        )


class HelpView(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.index = 0
        self.message: discord.Message | None = None

    def make_embed(self) -> discord.Embed:
        page = PAGES[self.index]

        embed = discord.Embed(
            title=f"📖 Commands — {page['category']}",
            description=INTRO if self.index == 0 else None,
            color=WHITE,
        )

        for name, desc in page["commands"]:
            embed.add_field(
                name=name,
                value=f"{desc}\n\u200b",
                inline=False,
            )

        embed.set_footer(
            text=f"📄 Page {self.index + 1}/{len(PAGES)} • unavailable economy bot"
        )

        return embed

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "🚫 This menu belongs to someone else. Run `/help` to open your own.",
                ephemeral=True,
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

    @discord.ui.button(
        label="◀",
        style=discord.ButtonStyle.secondary,
    )
    async def previous(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.index = (self.index - 1) % len(PAGES)

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self,
        )

    @discord.ui.button(
        label="✖",
        style=discord.ButtonStyle.danger,
    )
    async def close(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.stop()

        await interaction.response.edit_message(
            content="👋 Help menu closed. Run `/help` to open it again.",
            embed=None,
            view=None,
        )

    @discord.ui.button(
        label="▶",
        style=discord.ButtonStyle.secondary,
    )
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.index = (self.index + 1) % len(PAGES)

        await interaction.response.edit_message(
            embed=self.make_embed(),
            view=self,
        )


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Browse all commands and learn how to use them.",
    )
    async def help(self, interaction: discord.Interaction):
        view = HelpView(interaction.user.id)

        await interaction.response.send_message(
            embed=view.make_embed(),
            view=view,
        )

        view.message = await interaction.original_response()


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
