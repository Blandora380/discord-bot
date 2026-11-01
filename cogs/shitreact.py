"""Adds a custom emoji reaction when a message contains "shit".

Rule 7: rate-limited per channel so a member repeating the trigger word can't
make the bot react to an unbroken stream of messages.
"""

import time

import discord
from discord.ext import commands

from cogs.settings import passive_allowed

EMOJI = "<:shit:1518211501813534780>"
RATE_LIMIT_S = 30.0


class ShitReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_react: dict[int, float] = {}

    def _allowed(self, guild, channel_id: int) -> bool:
        # Rule 3: admins must be able to switch auto-reactions off entirely.
        if not passive_allowed(guild):
            return False
        now = time.monotonic()
        if now - self._last_react.get(channel_id, 0.0) < RATE_LIMIT_S:
            return False
        self._last_react[channel_id] = now
        return True

    async def react_if_needed(self, message):
        if message.author.bot:
            return

        if "shit" not in message.content.lower():
            return

        if not self._allowed(message.guild, message.channel.id):
            return

        try:
            await message.add_reaction(discord.PartialEmoji.from_str(EMOJI))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.react_if_needed(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Hanya react kalau sebelumnya belum mengandung "shit"
        if (
            "shit" not in before.content.lower()
            and "shit" in after.content.lower()
        ):
            await self.react_if_needed(after)


async def setup(bot):
    await bot.add_cog(ShitReact(bot))
