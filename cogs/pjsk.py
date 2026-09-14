"""
cogs/pjsk.py
-------------
!pjsk <song title>                       -> replies with song name, difficulty levels, jacket, and MP3 link
!pjskchart <title|romaji|ID> [difficulty] -> replies with a rendered chart preview image

Data source: Sekai-World master DB mirror (community-maintained, unofficial)
  - https://sekai-world.github.io/sekai-master-db-diff/musics.json
  - https://sekai-world.github.io/sekai-master-db-diff/musicDifficulties.json
  - https://sekai-world.github.io/sekai-master-db-diff/musicVocals.json
Assets:
  - https://storage.sekai.best/sekai-jp-assets/music/jacket/{ab}/{ab}.webp
  - https://storage.sekai.best/sekai-jp-assets/music/long/{ab}/{ab}.mp3

Notes / things you may need to tweak:
- The jacket/audio hosts occasionally rate-limit or go down. This cog tries a
  couple of known mirrors before giving up.
- Discord's non-nitro upload limit is 25MB (10MB on some old servers, 500MB
  with boost tier 3). Full PJSK songs are usually well under 25MB, but if a
  guild's limit is lower, we fall back to uploading to catbox.moe and posting
  the link instead of attaching the file directly - same pattern you're
  already using in your media downloader cog.
- Install deps: pip install aiohttp --break-system-packages (discord.py already needs aiohttp)
"""

import asyncio
import difflib
import io
import json
import logging
import time
from pathlib import Path

import aiohttp
from pykakasi import kakasi
import discord
from discord.ext import commands

log = logging.getLogger("pjsk_cog")

MASTER_DB_BASE = "https://sekai-world.github.io/sekai-master-db-diff"
ASSET_BASES = [
    "https://storage.sekai.best/sekai-jp-assets",
    "https://storage.sekai.best/sekai-assets",
]

# chart preview images - already rendered as PNG by this server, path shape:
# jp/{music_id:04d}/{difficulty}.png
CHART_BASE = "https://storage.sekai.best/sekai-music-charts/jp"

CACHE_DIR = Path("cache/pjsk")
CACHE_TTL = 60 * 60 * 6  # refresh master db every 6 hours

DIFF_ORDER = ["easy", "normal", "hard", "expert", "master", "append"]
DIFF_LABEL = {
    "easy": "EASY",
    "normal": "NORMAL",
    "hard": "HARD",
    "expert": "EXPERT",
    "master": "MASTER",
    "append": "APPEND",
}
DIFF_COLOR = {
    "easy": 0x63C25A,
    "normal": 0x4A8FE7,
    "hard": 0xF2A93B,
    "expert": 0xE0524B,
    "master": 0xA85CE0,
    "append": 0xF25C9E,
}

# Discord attachment size limits by boost tier (bytes), used as a safety margin
DEFAULT_UPLOAD_LIMIT = 25 * 1024 * 1024


class PjskCog(commands.Cog, name="Project SEKAI"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self._musics: list[dict] = []
        self._difficulties: dict[int, list[dict]] = {}
        self._vocals: dict[int, list[dict]] = {}
        self._last_refresh: float = 0
        self._refresh_lock = asyncio.Lock()
        self._kks = kakasi()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        await self._ensure_data()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    # ---------------------------------------------------------------- #
    # Data loading
    # ---------------------------------------------------------------- #
    async def _fetch_json(self, name: str) -> list:
        cache_path = CACHE_DIR / name
        url = f"{MASTER_DB_BASE}/{name}"
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
            cache_path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as e:
            log.warning("Failed to fetch %s (%s), falling back to cache", url, e)
            if cache_path.exists():
                return json.loads(cache_path.read_text(encoding="utf-8"))
            raise

    async def _ensure_data(self, force: bool = False):
        async with self._refresh_lock:
            if not force and time.time() - self._last_refresh < CACHE_TTL and self._musics:
                return
            musics, difficulties, vocals = await asyncio.gather(
                self._fetch_json("musics.json"),
                self._fetch_json("musicDifficulties.json"),
                self._fetch_json("musicVocals.json"),
            )
            self._musics = musics

            diff_map: dict[int, list[dict]] = {}
            for d in difficulties:
                diff_map.setdefault(d["musicId"], []).append(d)
            self._difficulties = diff_map

            vocal_map: dict[int, list[dict]] = {}
            for v in vocals:
                vocal_map.setdefault(v["musicId"], []).append(v)
            self._vocals = vocal_map

            self._last_refresh = time.time()
            log.info("pjsk cog: loaded %d songs", len(musics))

    # ---------------------------------------------------------------- #
    # Search
    # ---------------------------------------------------------------- #
    def _romanize(self, value: str) -> str:
        """Convert Japanese kana/kanji text to lowercase romaji."""
        try:
            result = self._kks.convert(value)
            return "".join(item["hepburn"] for item in result).lower()
        except Exception:
            return value.lower()

    def _find_song(self, query: str) -> dict | None:
        query = query.strip()

        if not query:
            return None

        query_l = query.lower()
        query_romaji = self._romanize(query)

        # 1. Search by music ID
        music_id_query = query_l.removeprefix("id:").strip()

        if music_id_query.isdigit():
            music_id = int(music_id_query)

            for m in self._musics:
                if m.get("id") == music_id:
                    return m

        # 2. Exact title match
        for m in self._musics:
            title = str(m.get("title", "")).strip()
            pronunciation = str(m.get("pronunciation", "")).strip()

            if (
                title.lower() == query_l
                or pronunciation.lower() == query_l
                or self._romanize(title) == query_romaji
                or self._romanize(pronunciation) == query_romaji
            ):
                return m

        # 3. Substring match, including romaji
        matches = []

        for m in self._musics:
            title = str(m.get("title", ""))
            pronunciation = str(m.get("pronunciation", ""))

            title_l = title.lower()
            pronunciation_l = pronunciation.lower()

            title_romaji = self._romanize(title)
            pronunciation_romaji = self._romanize(pronunciation)

            if (
                query_l in title_l
                or query_l in pronunciation_l
                or query_romaji in title_romaji
                or query_romaji in pronunciation_romaji
            ):
                matches.append(m)

        if matches:
            return min(
                matches,
                key=lambda m: len(m.get("title", ""))
            )

        # 4. Fuzzy match against both Japanese and romaji titles
        candidates = []

        for m in self._musics:
            title = str(m.get("title", ""))
            pronunciation = str(m.get("pronunciation", ""))

            candidates.extend([
                (title, m),
                (self._romanize(title), m),
                (pronunciation, m),
                (self._romanize(pronunciation), m),
            ])

        candidate_names = [name for name, _ in candidates]

        close = difflib.get_close_matches(
            query_l,
            [name.lower() for name in candidate_names],
            n=1,
            cutoff=0.5
        )

        if close:
            matched = close[0]
            for name, song in candidates:
                if name.lower() == matched:
                    return song

        close = difflib.get_close_matches(
            query_romaji,
            [self._romanize(name) for name in candidate_names],
            n=1,
            cutoff=0.5
        )

        if close:
            matched = close[0]
            for name, song in candidates:
                if self._romanize(name) == matched:
                    return song

        return None

    def _pick_vocal(self, music_id: int) -> dict | None:
        vocals = self._vocals.get(music_id, [])
        if not vocals:
            return None
        # Prefer the original song vocal version over another/collab versions
        for v in vocals:
            if v.get("musicVocalType") == "original_song":
                return v
        return vocals[0]

    # ---------------------------------------------------------------- #
    # Asset fetching with mirror fallback
    # ---------------------------------------------------------------- #
    async def _download_audio_to_file(self, path: str) -> Path | None:
        """Stream audio to disk instead of loading the whole MP3 into RAM."""
        for base in ASSET_BASES:
            url = f"{base}/{path}"
            try:
                async with self.session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        continue

                    content_length = resp.headers.get("Content-Length")
                    if content_length and int(content_length) <= 0:
                        continue

                    audio_dir = CACHE_DIR / "audio"
                    audio_dir.mkdir(parents=True, exist_ok=True)

                    safe_name = path.replace("/", "_")
                    audio_file = audio_dir / safe_name

                    # Reuse an already downloaded song.
                    if audio_file.exists() and audio_file.stat().st_size > 0:
                        return audio_file

                    with audio_file.open("wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 1024):
                            f.write(chunk)

                    if audio_file.exists() and audio_file.stat().st_size > 0:
                        return audio_file

            except Exception as e:
                log.debug("streaming audio fetch failed %s: %s", url, e)
                continue

        return None

    async def _try_get_bytes(
        self, path: str, bases: list[str] | None = None
    ) -> tuple[bytes | None, list[str]]:
        """Returns (bytes_or_none, attempts) where attempts is a list of
        'url -> status/error' strings, useful for surfacing to the user when
        every mirror fails."""
        attempts: list[str] = []
        for base in bases or ASSET_BASES:
            url = f"{base}/{path}"
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    attempts.append(f"{url} -> HTTP {resp.status}")
                    if resp.status == 200:
                        return await resp.read(), attempts
            except Exception as e:
                attempts.append(f"{url} -> {type(e).__name__}: {e}")
                log.warning("asset fetch failed %s: %s", url, e)
                continue
        return None, attempts

    async def _resolve_working_url(self, path: str) -> str | None:
        """Return the first mirror base where a HEAD/GET succeeds, for embed thumbnails."""
        for base in ASSET_BASES:
            url = f"{base}/{path}"
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return url
            except Exception:
                continue
        return None

    async def _upload_to_catbox(self, data: bytes, filename: str) -> str | None:
        form = aiohttp.FormData()
        form.add_field("reqtype", "fileupload")
        form.add_field("fileToUpload", data, filename=filename, content_type="audio/mpeg")
        try:
            async with self.session.post(
                "https://catbox.moe/user/api.php", data=form, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 200:
                    text = (await resp.text()).strip()
                    if text.startswith("http"):
                        return text
        except Exception as e:
            log.warning("catbox upload failed: %s", e)
        return None

    # ---------------------------------------------------------------- #
    # Command
    # ---------------------------------------------------------------- #
    @commands.command(name="pjsk", help="Look up a Project SEKAI song by title, romaji, or music ID")
    async def pjsk(self, ctx: commands.Context, *, title: str):
        await self._ensure_data()

        song = self._find_song(title)
        if not song:
            await ctx.reply(f"Couldn't find a song matching **{title}**. Check the spelling and try again.")
            return

        music_id = song["id"]
        ab_name = song.get("assetbundleName")
        jacket_path = f"music/jacket/{ab_name}/{ab_name}.webp"

        async with ctx.typing():
            # Difficulties
            diffs = self._difficulties.get(music_id, [])
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

            jacket_url = await self._resolve_working_url(jacket_path)
            if jacket_url:
                embed.set_thumbnail(url=jacket_url)
            else:
                embed.add_field(name="Jacket", value="⚠️ Jacket image unavailable right now.", inline=False)

            # Build direct MP3 URL.
            vocal = self._pick_vocal(music_id)

            if vocal:
                vocal_ab = vocal.get("assetbundleName")

                if vocal_ab:
                    audio_path = f"music/long/{vocal_ab}/{vocal_ab}.mp3"
                    audio_url = await self._resolve_working_url(audio_path)

                    if audio_url:
                        embed.add_field(
                            name="Audio",
                            value=f"[🎵 Download MP3]({audio_url})",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="Audio",
                            value="⚠️ Audio URL unavailable right now.",
                            inline=False
                        )
                else:
                    embed.add_field(
                        name="Audio",
                        value="⚠️ Audio asset data is missing.",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Audio",
                    value="⚠️ No audio data found for this song.",
                    inline=False
                )

            # Send everything in ONE Discord message.
            await ctx.reply(embed=embed)

    @pjsk.error
    async def pjsk_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Usage: `!pjsk <song title | romaji | music ID>`")
        else:
            log.exception("pjsk command error", exc_info=error)
            await ctx.reply("Something went wrong looking that up.")

    @commands.command(
        name="pjskchart",
        help="Chart preview image: !pjskchart <song title | romaji | music ID> [difficulty]",
    )
    async def pjskchart(self, ctx: commands.Context, *, query: str):
        await self._ensure_data()

        # optional trailing difficulty word, e.g. "!pjskchart tell your world master"
        parts = query.strip().split()
        requested_diff = None
        if len(parts) > 1 and parts[-1].lower() in DIFF_ORDER:
            requested_diff = parts[-1].lower()
            query = " ".join(parts[:-1])

        song = self._find_song(query)
        if not song:
            await ctx.reply(f"Couldn't find a song matching **{query}**. Check the spelling/ID and try again.")
            return

        music_id = song["id"]
        diffs = self._difficulties.get(music_id, [])
        if not diffs:
            await ctx.reply("No difficulty/chart data found for this song.")
            return

        available = {d["musicDifficulty"] for d in diffs}

        if requested_diff and requested_diff not in available:
            avail_str = ", ".join(DIFF_LABEL[d] for d in DIFF_ORDER if d in available)
            await ctx.reply(f"This song has no **{DIFF_LABEL.get(requested_diff)}** chart. Available: {avail_str}")
            return

        if not requested_diff:
            # default to the hardest available difficulty (append > master > expert > ...)
            for pref in reversed(DIFF_ORDER):
                if pref in available:
                    requested_diff = pref
                    break

        async with ctx.typing():
            chart_path = f"{music_id:04d}/{requested_diff}.png"
            png_bytes, attempts = await self._try_get_bytes(chart_path, bases=[CHART_BASE])
            if not png_bytes:
                attempts_str = "\n".join(attempts) if attempts else "no mirrors were reachable"
                log.warning("pjskchart: chart fetch failed for %s:\n%s", chart_path, attempts_str)
                await ctx.reply(
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

            await ctx.reply(embed=embed, file=file)

    @pjskchart.error
    async def pjskchart_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply("Usage: `!pjskchart <song title | romaji | music ID> [difficulty]`")
        else:
            log.exception("pjskchart command error", exc_info=error)
            await ctx.reply("Something went wrong rendering that chart.")

    @commands.command(name="pjskrefresh", hidden=True)
    @commands.is_owner()
    async def pjsk_refresh(self, ctx: commands.Context):
        await self._ensure_data(force=True)
        await ctx.reply(f"Refreshed song database: {len(self._musics)} songs loaded.")


async def setup(bot: commands.Bot):
    await bot.add_cog(PjskCog(bot))
