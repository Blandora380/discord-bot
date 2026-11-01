import logging

import discord
from discord.ext import commands

from cogs.settings import prefix_allowed, voice_allowed

log = logging.getLogger("join")


class Join(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild) or not voice_allowed(message.guild):  # rule 3
            return

        if message.content != "the!come":
            return

        if message.guild is None:
            return

        member = message.author
        if member.voice is None or member.voice.channel is None:
            await message.channel.send("❌ You have to join a voice channel first")
            return

        voice_channel = member.voice.channel

        voice_client = discord.utils.get(self.bot.voice_clients, guild=message.guild)

        try:
            if voice_client is None:
                await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        except Exception as e:
            print(f"JOIN ERROR: {e}")
            log.exception("joining voice channel failed")
            await message.channel.send("⚠️ Couldn't join the voice channel. Please try again.")
            return

        await message.channel.send(f"hop on {voice_channel.name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Join(bot))
