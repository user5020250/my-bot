import discord

from discord import app_commands
from discord.ext import commands

WHITE = discord.Color(0xFFFFFF)

COMMANDS_PER_PAGE = 6

CATEGORIES = [
    (
        "💰 Economy",
        [
            (
                "💼 /jobs",
                "View all available jobs and see how much each one pays.",
            ),
            (
                "👔 /work [job]",
                "Choose or switch jobs. Run `/work` without selecting a job to earn money. Cooldown: 8 hours.",
            ),
            (
                "🎰 /scatter [amount]",
                "Bet your money on a coin flip. Win big or lose everything.",
            ),
            (
                "🎤 /karaoke",
                "Sing karaoke and earn ₱100–₱1,000. Cooldown: 1 minute.",
            ),
            (
                "💵 /allowance",
                "Claim your allowance. Cooldown: 24 hours.",
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
        "🛒 Shop & Inventory",
        [
            (
                "🛍️ /shop",
                "Browse all items available in the shop.",
            ),
            (
                "💸 /buy [item]",
                "Purchase an item from the shop.",
            ),
            (
                "🎒 /inventory",
                "View all items you own.",
            ),
            (
                "🛡️ /use [item]",
                "Use an item from your inventory.",
            ),
            (
                "🔒 Padlock",
                "Protects you from /steal for 24 hours.",
            ),
            (
                "🎟️ Lottery Ticket",
                "Use it to enter the global lottery.",
            ),
            (
                "💰 /balance [user]",
                "Check your balance or another player's balance.",
            ),
        ],
    ),

    (
        "🎟️ Lottery",
        [
            (
                "🎟️ /use lottery_ticket",
                "Consume one lottery ticket and enter the next draw.",
            ),
            (
                "🎲 /draw_lottery",
                "Owner-only command that picks a random winner.",
            ),
        ],
    ),

    (
        "🥷 Crime",
        [
            (
                "🥷 /steal [user]",
                "Attempt to steal another player's money. Cooldown: 24 hours.",
            ),
        ],
    ),

    (
        "🏦 Loans",
        [
            (
                "📨 /loan request",
                "Request a loan from another player.",
            ),
            (
                "💵 /loan pay",
                "Pay back part or all of a loan.",
            ),
            (
                "📒 /loan list",
                "View all active loans.",
            ),
            (
                "📄 /loan info",
                "See detailed information about a loan.",
            ),
            (
                "❌ /loan cancel",
                "Cancel a pending loan request.",
            ),
        ],
    ),

    (
        "💼 Businesses",
        [
            (
                "📋 /business list",
                "View all businesses you can buy.",
            ),
            (
                "🛒 /business buy",
                "Purchase a business.",
            ),
            (
                "💰 /business sell",
                "Sell one of your businesses.",
            ),
            (
                "📊 /business portfolio",
                "View your businesses.",
            ),
            (
                "💵 /business collect",
                "Collect income.",
            ),
            (
                "⬆️ /business upgrade",
                "Upgrade a business.",
            ),
            (
                "📈 /business stats",
                "See business statistics.",
            ),
            (
                "🏆 /business leaderboard",
                "View the richest business owners.",
            ),
            (
                "🏴‍☠️ /business raid",
                "Raid another player's business.",
            ),
            (
                "🛡️ /business defend",
                "Protect your businesses.",
            ),
            (
                "💥 /business bankrupt",
                "Close a business permanently.",
            ),
        ],
    ),

    (
        "📊 Rankings",
        [
            (
                "🏆 /leaderboard",
                "View the richest players in the server.",
            ),
        ],
    ),

    (
        "ℹ️ Info",
        [
            (
                "👤 /profile [user]",
                "View a player's profile.",
            ),
            (
                "📖 /help",
                "Open this help menu.",
            ),
        ],
    ),
]

PAGES = []

for category_name, category_commands in CATEGORIES:
    chunks = [
        category_commands[i:i + COMMANDS_PER_PAGE]
        for i in range(
            0,
            len(category_commands),
            COMMANDS_PER_PAGE,
        )
    ]

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
        self.page = 0
        self.message = None

    def build_embed(self):
        data = PAGES[self.page]

        embed = discord.Embed(
            title=f"📖 Commands — {data['category']}",
            color=WHITE,
        )

        for name, desc in data["commands"]:
            embed.add_field(
                name=name,
                value=desc,
                inline=False,
            )

        embed.set_footer(
            text=f"Page {self.page + 1}/{len(PAGES)}"
        )

        return embed

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This isn't your help menu.",
                ephemeral=True,
            )
            return False

        return True

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True

        if self.message:
            try:
                await self.message.edit(
                    view=self
                )
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
        self.page = (
            self.page - 1
        ) % len(PAGES)

        await interaction.response.edit_message(
            embed=self.build_embed(),
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
            content="👋 Help menu closed.",
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
        self.page = (
            self.page + 1
        ) % len(PAGES)

        await interaction.response.edit_message(
            embed=self.build_embed(),
            view=self,
        )


class Help(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
    ):
        self.bot = bot

    @app_commands.command(
        name="help",
        description="View all commands.",
    )
    async def help(
        self,
        interaction: discord.Interaction,
    ):
        view = HelpView(
            interaction.user.id
        )

        await interaction.response.send_message(
            embed=view.build_embed(),
            view=view,
        )

        view.message = (
            await interaction.original_response()
        )


async def setup(
    bot: commands.Bot,
):
    await bot.add_cog(
        Help(bot)
    )
