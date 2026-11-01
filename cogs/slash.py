import time
import asyncio
import io
import logging
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("slash")

from cogs.uptime import format_uptime
from cogs.playpigeon import TARGET_VOICE_CHANNEL_ID, AUDIO_PATH as PIGEON_AUDIO_PATH
from cogs.play import ytdl, FFMPEG_OPTIONS, VOLUME
from cogs.pjsk import DIFF_ORDER, DIFF_LABEL, DIFF_COLOR, CHART_BASE
from cogs.settings import voice_allowed

DM_CHANNEL_ID = 1511402934825521174

async def _get_or_join_voice(interaction: discord.Interaction, voice_channel: discord.VoiceChannel):
    voice_client = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_client.channel != voice_channel:
        await voice_client.move_to(voice_channel)
    return voice_client


class SlashCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="the-uptime", description="Check how long bot has been on.")
    async def uptime(self, interaction: discord.Interaction):
        uptime_cog = self.bot.get_cog("Uptime")
        uptime_str = format_uptime(time.time() - uptime_cog.start_time)
        await interaction.response.send_message(f"🟢 Uptime: {uptime_str}")

    @app_commands.command(name="the-join", description="Bot join your joined voice channel")
    async def join(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be executed on a server.", ephemeral=True)
            return

        # Rule 3: an admin must be able to switch voice features off, and to
        # make the bot leave a voice channel (/the-settings leavevoice).
        if not voice_allowed(interaction.guild):
            await interaction.response.send_message(
                "⚠️ Voice features are switched off in this server.", ephemeral=True
            )
            return

        member = interaction.user
        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message("❌ You must join a voice channel", ephemeral=True)
            return

        voice_channel = member.voice.channel

        try:
            await _get_or_join_voice(interaction, voice_channel)
        except Exception as e:
            await interaction.response.send_message("⚠️ Couldn't join the voice channel. Please try again.", ephemeral=True)
            return

        await interaction.response.send_message(f"hop on {voice_channel.name}")

    @app_commands.command(name="playpigeon", description="Plays pigeon song in a voice channel")
    async def playpigeon(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be executed on a server.", ephemeral=True)
            return

        # Rule 3: an admin must be able to switch voice features off, and to
        # make the bot leave a voice channel (/the-settings leavevoice).
        if not voice_allowed(interaction.guild):
            await interaction.response.send_message(
                "⚠️ Voice features are switched off in this server.", ephemeral=True
            )
            return

        voice_channel = self.bot.get_channel(TARGET_VOICE_CHANNEL_ID)
        if voice_channel is None:
            await interaction.response.send_message("⚠️ Voice channel target not found.", ephemeral=True)
            return

        try:
            voice_client = await _get_or_join_voice(interaction, voice_channel)
        except Exception as e:
            await interaction.response.send_message("⚠️ Couldn't join the voice channel. Please try again.", ephemeral=True)
            return

        await interaction.response.send_message(f"hop on {voice_channel.name}")

        if voice_client.is_playing():
            voice_client.stop()

        source = discord.FFmpegPCMAudio(PIGEON_AUDIO_PATH)
        voice_client.play(source)

    @app_commands.command(name="play", description="Play songs from YouTube (link or song title)")
    @app_commands.describe(query="Link YouTube or song title")
    async def play(self, interaction: discord.Interaction, query: str):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be executed on a server.", ephemeral=True)
            return

        # Rule 3: an admin must be able to switch voice features off, and to
        # make the bot leave a voice channel (/the-settings leavevoice).
        if not voice_allowed(interaction.guild):
            await interaction.response.send_message(
                "⚠️ Voice features are switched off in this server.", ephemeral=True
            )
            return

        member = interaction.user
        if member.voice is None or member.voice.channel is None:
            await interaction.response.send_message("❌ You must join a voice channel.", ephemeral=True)
            return

        voice_channel = member.voice.channel

        await interaction.response.defer()

        try:
            voice_client = await _get_or_join_voice(interaction, voice_channel)
        except Exception as e:
            await interaction.followup.send("⚠️ Couldn't join the voice channel. Please try again.")
            return

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
        except Exception as e:
            log.exception("yt-dlp extract failed")
            await interaction.followup.send("⚠️ Couldn't search for that. Please try another query.")
            return

        if "entries" in data:
            data = data["entries"][0]

        stream_url = data["url"]
        title = data.get("title", "Unknown")

        if voice_client.is_playing():
            voice_client.stop()

        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=VOLUME)
        voice_client.play(source)

        await interaction.followup.send(f"▶️ Now playing: **{title}**")

    @app_commands.command(
        name="yaoi",
        description="Check your DMs 🤤🤤🤤"
    )
    async def yaoi(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"{interaction.user.mention} check dms 🤤🤤🤤"
        )

        try:
            files = [
                discord.File("assets/yaoi.jpg"),
                discord.File("assets/yaoi2.jpg"),
                # Tambah file lain di sini
            ]

            await interaction.user.send(
                content="check dms 🤤🤤🤤",
                files=files
            )

        except discord.Forbidden:
            await interaction.followup.send(
                "your dms are disabled fuck you"
            )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="dm", description="Send a DM to a user")
    @app_commands.describe(user="The user to DM", message="The message to send")
    @app_commands.checks.cooldown(1, 5.0, key=lambda i: (i.guild_id, i.user.id))
    async def dm(self, interaction: discord.Interaction, user: discord.User, message: str):
        if interaction.channel_id != DM_CHANNEL_ID:
            await interaction.response.send_message(
                f"This command can only be used in <#{DM_CHANNEL_ID}>.",
                ephemeral=True
            )
            return

        try:
            await user.send(message)
        except discord.Forbidden:
            await interaction.response.send_message(
                f"Couldn't DM {user.mention} — they may have DMs disabled.",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                "Failed to send that DM — the target may have DMs disabled.",
                ephemeral=True
            )
            return

        # Ephemeral ack, only visible to the person who ran the command
        await interaction.response.send_message("Sent.", ephemeral=True)

        # Public message, sent as a normal bot message (no "used /dm" header)
        await interaction.channel.send(f"dm'ed {user.mention}")

    @dm.error
    async def dm_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Slow down! Try again in {error.retry_after:.1f}s.",
                ephemeral=True
            )
        else:
            raise error

    # ---------------------------------------------------------------- #
    # PJSK slash commands
    # These reuse the PjskCog instance's data/helpers so there's one
    # source of truth for song lookup, difficulty data, and asset fetching
    # shared between the !pjsk prefix commands and these / commands.
    # ---------------------------------------------------------------- #
    def _get_pjsk_cog(self):
        return self.bot.get_cog("Project SEKAI")

    @app_commands.command(name="pjsk", description="Look up a Project SEKAI song by title, romaji, or music ID")
    @app_commands.describe(title="Song title, romaji, or music ID")
    async def pjsk_slash(self, interaction: discord.Interaction, title: str):
        cog = self._get_pjsk_cog()
        if cog is None:
            await interaction.response.send_message("⚠️ The PJSK cog isn't loaded.", ephemeral=True)
            return

        await interaction.response.defer()
        await cog._ensure_data()

        song = cog._find_song(title)
        if not song:
            await interaction.followup.send(f"Couldn't find a song matching **{title}**. Check the spelling and try again.")
            return

        music_id = song["id"]
        ab_name = song.get("assetbundleName")
        jacket_path = f"music/jacket/{ab_name}/{ab_name}.webp"

        diffs = cog._difficulties.get(music_id, [])
        diffs_sorted = sorted(
            diffs, key=lambda d: DIFF_ORDER.index(d["musicDifficulty"]) if d["musicDifficulty"] in DIFF_ORDER else 99
        )

        embed = discord.Embed(title=song.get("title", "Unknown"), color=0x33AADD)
        if song.get("pronunciation"):
            embed.set_author(name=song["pronunciation"])

        level_lines = []
        for d in diffs_sorted:
            label = DIFF_LABEL.get(d["musicDifficulty"], d["musicDifficulty"].upper())
            level_lines.append(f"**{label}** — Lv. {d.get('playLevel', '?')}")
        embed.add_field(name="Difficulty Levels", value="\n".join(level_lines) or "No data", inline=False)

        jacket_url = await cog._resolve_working_url(jacket_path)
        if jacket_url:
            embed.set_thumbnail(url=jacket_url)
        else:
            embed.add_field(name="Jacket", value="⚠️ Jacket image unavailable right now.", inline=False)

        vocal = cog._pick_vocal(music_id)
        if vocal:
            vocal_ab = vocal.get("assetbundleName")
            if vocal_ab:
                audio_path = f"music/long/{vocal_ab}/{vocal_ab}.mp3"
                audio_url = await cog._resolve_working_url(audio_path)
                if audio_url:
                    embed.add_field(name="Audio", value=f"[🎵 Download MP3]({audio_url})", inline=False)
                else:
                    embed.add_field(name="Audio", value="⚠️ Audio URL unavailable right now.", inline=False)
            else:
                embed.add_field(name="Audio", value="⚠️ Audio asset data is missing.", inline=False)
        else:
            embed.add_field(name="Audio", value="⚠️ No audio data found for this song.", inline=False)

        await interaction.followup.send(embed=embed)

    @app_commands.command(name="pjskchart", description="Show a chart preview image for a Project SEKAI song")
    @app_commands.describe(
        query="Song title, romaji, or music ID",
        difficulty="Chart difficulty (defaults to the hardest one available)"
    )
    @app_commands.choices(difficulty=[
        app_commands.Choice(name=DIFF_LABEL[d], value=d) for d in DIFF_ORDER
    ])
    async def pjskchart_slash(
        self,
        interaction: discord.Interaction,
        query: str,
        difficulty: app_commands.Choice[str] | None = None,
    ):
        cog = self._get_pjsk_cog()
        if cog is None:
            await interaction.response.send_message("⚠️ The PJSK cog isn't loaded.", ephemeral=True)
            return

        await interaction.response.defer()
        await cog._ensure_data()

        song = cog._find_song(query)
        if not song:
            await interaction.followup.send(f"Couldn't find a song matching **{query}**. Check the spelling/ID and try again.")
            return

        music_id = song["id"]
        diffs = cog._difficulties.get(music_id, [])
        if not diffs:
            await interaction.followup.send("No difficulty/chart data found for this song.")
            return

        available = {d["musicDifficulty"] for d in diffs}
        requested_diff = difficulty.value if difficulty else None

        if requested_diff and requested_diff not in available:
            avail_str = ", ".join(DIFF_LABEL[d] for d in DIFF_ORDER if d in available)
            await interaction.followup.send(
                f"This song has no **{DIFF_LABEL.get(requested_diff)}** chart. Available: {avail_str}"
            )
            return

        if not requested_diff:
            for pref in reversed(DIFF_ORDER):
                if pref in available:
                    requested_diff = pref
                    break

        chart_path = f"{music_id:04d}/{requested_diff}.png"
        png_bytes, attempts = await cog._try_get_bytes(chart_path, bases=[CHART_BASE])
        if not png_bytes:
            attempts_str = "\n".join(attempts) if attempts else "no mirrors were reachable"
            await interaction.followup.send(
                "⚠️ Couldn't fetch the chart preview right now.\n"
                f"Tried:\n```\n{attempts_str[:1500]}\n```"
            )
            return

        level_entry = next((d for d in diffs if d["musicDifficulty"] == requested_diff), None)
        level = level_entry.get("playLevel", "?") if level_entry else "?"

        filename = f"{song.get('title', 'chart')}_{requested_diff}.png".replace("/", "_").replace(" ", "_")
        file = discord.File(io.BytesIO(png_bytes), filename=filename)

        embed = discord.Embed(
            title=f"{song.get('title', 'Unknown')} — {DIFF_LABEL.get(requested_diff)} (Lv. {level})",
            color=DIFF_COLOR.get(requested_diff, 0x33AADD),
        )
        embed.set_image(url=f"attachment://{filename}")
        avail_str = ", ".join(DIFF_LABEL[d] for d in DIFF_ORDER if d in available)
        embed.set_footer(text=f"Available difficulties: {avail_str}")

        await interaction.followup.send(embed=embed, file=file)

    @app_commands.command(name="pjskrefresh", description="[Owner] Refresh the cached PJSK song database")
    async def pjskrefresh_slash(self, interaction: discord.Interaction):
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("⛔ Owner only.", ephemeral=True)
            return

        cog = self._get_pjsk_cog()
        if cog is None:
            await interaction.response.send_message("⚠️ The PJSK cog isn't loaded.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await cog._ensure_data(force=True)
        await interaction.followup.send(f"Refreshed song database: {len(cog._musics)} songs loaded.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SlashCommands(bot))
