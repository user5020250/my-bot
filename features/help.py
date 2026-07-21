import discord

from discord import app_commands
from discord.ext import commands

WHITE = discord.Color(0xFFFFFF)

COMMANDS_PER_PAGE = 6

(
    "💰 Economy",
    [
        (
            "💼 /jobs",
            "`View all available jobs and see how much each one pays.`",
        ),
        (
            "👔 /work [job]",
            "`Choose or switch jobs. Run /work without selecting a job to earn money. Cooldown: 8 hours.`",
        ),
        (
            "🎰 /scatter [amount]",
            "`Bet your money on a coin flip. Win big or lose everything.`",
        ),
        (
            "🎤 /karaoke",
            "`Sing karaoke and earn ₱100–₱1,000. Cooldown: 1 minute.`",
        ),
        (
            "💵 /allowance",
            "`Claim your allowance. Cooldown: 24 hours.`",
        ),
        (
            "☀️ /daily",
            "`Claim your daily reward.`",
        ),
        (
            "📅 /weekly",
            "`Claim your weekly reward.`",
        ),
        (
            "🎉 /yearly",
            "`Claim your yearly reward.`",
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
