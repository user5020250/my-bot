import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import init_db  # NEW: sets up the persistent SQLite database

load_dotenv()  # reads variables from a local .env file

intents = discord.Intents.default()
intents.members = True          # required for moderation + role assignment
intents.message_content = True  # required for prefix commands and role assignment

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.utility",
    "cogs.server",
    "cogs.message",
    "cogs.role",
    "features.economy",   # NEW: /jobs /trabaho /tambay /sugal /baon
    "features.social",    # NEW: /utang /bayad /budol /karaoke
    "features.admin",     # NEW: /give
    "features.help",      # NEW: /help command
    "features.inventory",
    "features.sideline",
]


@bot.event
async def on_ready():
    print(f"logged in as {bot.user} (id: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"failed to sync slash commands: {e}")


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is not set")

    init_db()  # NEW: creates data/economy.db (or DATA_DIR) if it doesn't exist yet

    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
