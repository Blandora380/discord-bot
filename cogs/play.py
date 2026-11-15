import asyncio
import logging
import os
import discord
import yt_dlp
from discord.ext import commands

from cogs.settings import prefix_allowed, voice_allowed

log = logging.getLogger("play")

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": False,
    "verbose": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "cookies.txt",
    "js_runtimes": {
        "deno": {}
    },
    "remote_components": ["ejs:github"],
    "outtmpl": "~/tmp/%(id)s.%(ext)s",
}

FFMPEG_OPTIONS = {
    "options": "-vn -b:a 192k",
}

VOLUME = 1.5

print("yt-dlp:", yt_dlp.version.__version__)

import shutil
print("deno:", shutil.which("deno"))
print("ffmpeg:", shutil.which("ffmpeg"))

ytdl = yt_dlp.YoutubeDL(YTDL_OPTIONS)


class Play(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild) or not voice_allowed(message.guild):  # rule 3
            return

        # `the!playpigeon` also starts with `the!play`, so require the
        # command to end there — a bare `the!play` or `the!play <query>` only.
        cmd = "the!play"
        content = message.content
        if content != cmd and not content.startswith(cmd + " "):
            return

        if message.guild is None:
            return

        query = content[len(cmd):].strip()

        if not query:
            await message.channel.send(
                "❌ Please provide a link or song title."
            )
            return

        if query.lower().startswith("sc:"):
            query = "scsearch:" + query[3:].strip()

        member = message.author

        if member.voice is None or member.voice.channel is None:
            await message.channel.send(
                "❌ You need to join a voice channel first."
            )
            return

        voice_channel = member.voice.channel

        voice_client = discord.utils.get(
            self.bot.voice_clients,
            guild=message.guild
        )

        try:
            if voice_client is None:
                voice_client = await voice_channel.connect()
            elif voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)

        except Exception:
            log.exception("joining voice channel failed")
            await message.channel.send(
                "⚠️ Failed to join that voice channel. Please try again."
            )
            return

        await message.channel.send(
            f"🔎 Searching: `{query}` ..."
        )

        loop = asyncio.get_event_loop()

        try:
            # download audio ke file lokal
            data = await loop.run_in_executor(
                None,
                lambda: ytdl.extract_info(
                    query,
                    download=True
                )
            )

        except Exception:
            # yt-dlp errors embed the full URL and yt's error body — log only.
            log.exception("yt-dlp download failed")
            await message.channel.send(
                "⚠️ Couldn't download that. Please check the link and try again."
            )
            return

        if "entries" in data:
            entries = data.get("entries")

            if not entries:
                await message.channel.send(
                    "⚠️ No results found."
                )
                return

            data = entries[0]

        title = data.get("title", "Unknown")

        # lokasi file hasil download yt-dlp
        file_path = ytdl.prepare_filename(data)

        if not os.path.exists(file_path):
            await message.channel.send(
                "⚠️ Audio file was not found."
            )
            print("file tidak ditemukan:", file_path)
            return

        print("audio file:", file_path)

        if voice_client.is_playing():
            voice_client.stop()

        def after_playing(error):
            if error:
                print(f"Player error: {error}")

            # hapus file setelah selesai
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print("deleted:", file_path)
            except Exception as e:
                print("failed to delete:", e)

        try:
            source = discord.FFmpegPCMAudio(
                file_path,
                **FFMPEG_OPTIONS
            )

            source = discord.PCMVolumeTransformer(
                source,
                volume=VOLUME
            )

            voice_client.play(
                source,
                after=after_playing
            )

        except Exception:
            log.exception("ffmpeg/play failed")
            await message.channel.send(
                "⚠️ Couldn't play that track. Please try another one."
            )
            return

        await message.channel.send(
            f"▶️ Now playing: **{title}**"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Play(bot))
