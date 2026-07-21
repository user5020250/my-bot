import discord
from discord import app_commands
from discord.ext import commands

WHITE = discord.Color(0xFFFFFF)
COMMANDS_PER_PAGE = 5

INTRO = (
    "Starting money: **₱1,000**. Everything is in pesos (₱). "
    "Use the buttons below to browse commands, or press ✖ to close this menu."
)

COMMANDS = [
    (
        "/jobs",
        "View all available jobs and see how much each one pays.",
    ),
    (
        "/trabaho job: [job]",
        "Choose or switch jobs. Run `/trabaho` without selecting a job to work and get paid. Cooldown: 30 minutes.",
    ),
    (
        "/tambay",
        "Hang out with the barkada for a chance to earn some quick cash. "
        "70% chance to win, 30% chance to lose money on snacks or yosi. Cooldown: 1 minute.",
    ),
    (
        "/sugal amount: [₱]",
        "Flip a coin and bet your money. Win big or lose everything. No cooldown.",
    ),
    (
        "/palengke presyo",
        "Check the latest prices for rice, fish, mangoes, chicken, meat, and vegetables.",
    ),
    (
        "/palengke bili item: [item] quantity: [amount]",
        "Buy items from the palengke to keep or resell later.",
    ),
    (
        "/palengke benta item: [item] quantity: [amount]",
        "Sell the items you own and make a profit.",
    ),
    (
        "/load bili quantity: [amount]",
        "Buy mobile load in bulk.",
    ),
    (
        "/load benta quantity: [amount]",
        "Resell your mobile load for a random profit.",
    ),
    (
        "/utang lender: [user] amount: [₱]",
        "Borrow money from another player.",
    ),
    (
        "/bayad lender: [user] amount: [₱]",
        "Pay back your debt.",
    ),
    (
        "/budol target: [user]",
        "Try to scam another player. High risk, high reward. Cooldown: 1 day.",
    ),
    (
        "/karaoke",
        "Sing for tips and earn ₱50–₱500. Cooldown: 5 minutes.",
    ),
    (
        "/baon",
        "Claim your daily allowance of ₱50–₱100. Cooldown: 24 hours.",
    ),
    (
        "/profile user: [user]",
        "View your profile or another player's balance, job, and cooldowns.",
    ),
]

PAGES = [
    COMMANDS[i:i + COMMANDS_PER_PAGE]
    for i in range(0, len(COMMANDS), COMMANDS_PER_PAGE)
]


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
            embed.add_field(
                name=name,
                value=f"{desc}\n\u200b",
                inline=False,
            )

        embed.set_footer(
            text=f"Page {self.index + 1}/{len(PAGES)} • unavailable economy bot"
        )

        return embed

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This menu belongs to someone else. Run `/help` to open your own.",
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
            content="Help menu closed. Run `/help` to open it again.",
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
