"""
Shared configuration for the bot's cogs.
Edit the values below for your server.
"""

import discord

# The channel where members type a number to self-assign a role.
ROLE_CHANNEL_ID = 1522530868768542760  # replace with your channel ID

ROLE_MAP = {
    "abracadabra": 1523925145482297415,
}

# secs message stays up before deleting itself.
CONFIRMATION_DELETE_AFTER = 5

# secs role-assignment error messages (e.g. "already have this role") stay up.
ERROR_DELETE_AFTER = 5

# Shared embed color used across all moderation + embed commands.
EMBED_COLOR = discord.Color.from_rgb(255, 255, 255)
OWNER_ID = 843377668488429569  # replace with your actual Discord user ID
