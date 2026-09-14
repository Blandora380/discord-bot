import discord
from discord.ext import commands

AUDIO_PATH = "assets/pigeon.mp3"

# Ganti dengan ID voice channel tujuan (klik kanan voice channel -> Copy Channel ID)
TARGET_VOICE_CHANNEL_ID = 1511402934825521180


class PlayPigeon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.content != "!playpigeon":
            return

        print("playpigeon triggered")

        if message.guild is None:
            print("guild is None")
            return

        voice_channel = self.bot.get_channel(TARGET_VOICE_CHANNEL_ID)
        print(f"voice_channel = {voice_channel}")
        if voice_channel is None:
            return

        voice_client = discord.utils.get(self.bot.voice_clients, guild=message.guild)
        print(f"voice_client (before) = {voice_client}")

        try:
            if voice_client is None:
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        except Exception as e:
            print(f"CONNECT ERROR: {e}")
            return

        await message.channel.send(f"hop on https://discord.com/channels/1511402930417307668/1511402934825521180 for pigeon")

        if voice_client.is_playing():
            voice_client.stop()

        source = discord.FFmpegPCMAudio(AUDIO_PATH)
        voice_client.play(source)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayPigeon(bot))
