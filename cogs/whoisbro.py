"""Auto-reply to the "who is bro" bait phrase.

Rule 7: automatic posts are rate-limited so a member repeating the trigger
phrase can't flood a channel. The limit is per channel, not global, so
conversations in other channels are unaffected.
"""

import time

import discord
from discord.ext import commands

from cogs.settings import passive_allowed

RESPONSE = "no it's me guys"
RATE_LIMIT_S = 30.0


class WhoIsBro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_post: dict[int, float] = {}

    def _allowed(self, guild, channel_id: int) -> bool:
        # Rule 3: admins must be able to switch auto-replies off entirely.
        if not passive_allowed(guild):
            return False
        now = time.monotonic()
        if now - self._last_post.get(channel_id, 0.0) < RATE_LIMIT_S:
            return False
        self._last_post[channel_id] = now
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if "who is bro" in message.content.lower() and self._allowed(
            message.guild, message.channel.id
        ):
            await message.channel.send(RESPONSE)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return

        # Cuma balas kalau sebelumnya belum mengandung "who is bro"
        # lalu setelah diedit menjadi mengandung "who is bro"
        if (
            "who is bro" not in before.content.lower()
            and "who is bro" in after.content.lower()
            and self._allowed(after.guild, after.channel.id)
        ):
            await after.channel.send(RESPONSE)


async def setup(bot):
    await bot.add_cog(WhoIsBro(bot))
