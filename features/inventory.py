import discord
from discord import app_commands
from discord.ext import commands

import db_utils as db
from features.shop import SHOP_ITEMS

WHITE = discord.Color(0xFFFFFF)

ITEMS_PER_PAGE = 10


def get_user_inventory(user_id: str):
    """
    Returns a list of (item_id, qty) for everything the user owns
    with qty > 0, sorted alphabetically by item id.
    """
    rows = db.get_all_inventory(user_id)

    items = [(row["item"], row["qty"]) for row in rows]
    items.sort(key=lambda pair: pair[0])

    return items


def build_inventory_embed(
    member: discord.Member,
    items: list[tuple[str, int]],
    page: int,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎒 {member.display_name}'s Inventory",
        color=WHITE,
    )

    if not items:
        embed.description = "This inventory is empty."
        return embed

    start = page * ITEMS_PER_PAGE
    page_items = items[start:start + ITEMS_PER_PAGE]

    for item_id, qty in page_items:
        info = SHOP_ITEMS.get(item_id)

        if info is None:
            # Unknown/legacy item id — still show it rather than
            # silently dropping it from the inventory view.
            embed.add_field(
                name=item_id,
                value=f"Quantity: `{qty}`",
                inline=False,
            )
            continue

        embed.add_field(
            name=f"{info['emoji']} {info['name']}",
            value=(
                f"Quantity: `{qty}`\n"
                f"{info['description']}\n"
                f"ID: `{item_id}`"
            ),
            inline=False,
        )

    total_pages = max(
        1,
        (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE,
    )

    embed.set_footer(
        text=f"Page {page + 1}/{total_pages}"
    )

    return embed


class InventoryView(discord.ui.View):
    def __init__(self, member: discord.Member, items: list[tuple[str, int]]):
        super().__init__(timeout=120)

        self.member = member
        self.items = items
        self.page = 0

        self.total_pages = max(
            1,
            (len(items) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE,
        )

        self.update_buttons()

    def update_buttons(self):
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = (self.page - 1) % self.total_pages

        await interaction.response.edit_message(
            embed=build_inventory_embed(self.member, self.items, self.page),
            view=self,
        )

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        self.page = (self.page + 1) % self.total_pages

        await interaction.response.edit_message(
            embed=build_inventory_embed(self.member, self.items, self.page),
            view=self,
        )


class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="inventory",
        description="View your items.",
    )
    @app_commands.describe(
        member="Whose inventory to view (defaults to you)",
    )
    async def inventory(
        self,
        interaction: discord.Interaction,
        member: discord.Member | None = None,
    ):
        member = member or interaction.user

        items = get_user_inventory(str(member.id))

        embed = build_inventory_embed(member, items, 0)

        if len(items) > ITEMS_PER_PAGE:
            view = InventoryView(member, items)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Inventory(bot)
    )
