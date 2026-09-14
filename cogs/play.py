import asyncio
import discord
import yt_dlp
from discord.ext import commands

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "cookies.txt",
    "remote_components": ["ejs:github"],
    "js_runtimes": ["deno"],
}

FFMPEG_OPTIONS = {
    # reconnect flags so the stream survives brief network hiccups
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -b:a 192k",
}

# 1.0 = normal, 1.5 = 150%, 2.0 = 200%, etc.
VOLUME = 1.5

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class Play(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.content.startswith("!theplay"):
            return

        if message.guild is None:
            return

        query = message.content[len("!theplay"):].strip()
        if not query:
            await message.channel.send("❌ Please provide a link or song title. Example: `!theplay song title` or `!theplay sc:song title` to search SoundCloud")
            return

        # "sc:" prefix forces a SoundCloud search instead of the default YouTube search
        if query.lower().startswith("sc:"):
            query = "scsearch:" + query[3:].strip()

        member = message.author
        if member.voice is None or member.voice.channel is None:
            await message.channel.send("❌ You need to join a voice channel first.")
            return

        voice_channel = member.voice.channel

        voice_client = discord.utils.get(self.bot.voice_clients, guild=message.guild)
        try:
            if voice_client is None:
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        except Exception as e:
            await message.channel.send(f"⚠️ Failed to join voice: {e}")
            return

        await message.channel.send(f"🔎 Searching: `{query}` ...")

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None, lambda: ytdl.extract_info(query, download=False)
            )
        except Exception as e:
            await message.channel.send(f"⚠️ Failed to fetch: {e}")
            return

        if "entries" in data:
            data = data["entries"][0]

        stream_url = data["url"]
        title = data.get("title", "Unknown")

        if voice_client.is_playing():
            voice_client.stop()

        def after_playing(error):
            if error:
                print(f"Player error: {error}")

        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=VOLUME)
        voice_client.play(source, after=after_playing)

        await message.channel.send(f"▶️ Now playing: **{title}**")


async def setup(bot: commands.Bot):
    await bot.add_cog(Play(bot))
