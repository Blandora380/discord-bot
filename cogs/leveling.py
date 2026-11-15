"""Server leveling: XP on messages, a rendered rank card, and a leaderboard.

Storage is SQLite (`data/levels.db`) rather than the asyncpg layer in
`database/` — that layer needs `config.yml` + a running Postgres, neither of
which this bot has, so nothing else uses it. The schema is created lazily on
`cog_load`, so there is no setup script to remember to run.

Design notes:
  * Level is DERIVED from XP (never stored), so the two can't drift apart.
  * XP uses a per-level quadratic curve; thresholds are precomputed once into
    `_CUM` so a lookup is a bisect, not a loop over the sum.
  * `helpers.embeds` is deliberately NOT used here: `HoloEmbed.set_footer`
    reads `get_config()["discord"]["name"]`, and without `config.yml` that
    raises FileNotFoundError. Plain `discord.Embed` is what the other cogs do.
"""

from __future__ import annotations

import asyncio
import bisect
import io
import logging
import random
import sqlite3
import threading
import time
from functools import lru_cache
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from cogs.settings import passive_allowed
from bot import get_shared_session

log = logging.getLogger("leveling")

DB_PATH = "data/levels.db"

XP_MIN, XP_MAX = 15, 25   # XP granted per awardable message
XP_COOLDOWN = 30           # seconds between XP grants for the same user
MAX_LEVEL = 1000
LB_SIZE = 10

# --- XP curve -------------------------------------------------------------

def _xp_to_next(level: int) -> int:
    """XP needed to go from `level` to `level + 1`.

    Quadratic so early levels come fast (100 XP for level 1) while later ones
    take real effort (~2.8k for level 20). Monotonic, so prefix sums are valid.
    """
    return 5 * level * level + 50 * level + 100


# _CUM[L] = total XP required to already BE level L. _CUM[0] == 0 by definition.
_CUM = [0] * (MAX_LEVEL + 1)
for _l in range(MAX_LEVEL):
    _CUM[_l + 1] = _CUM[_l] + _xp_to_next(_l)


def level_from_xp(xp: int) -> int:
    """Largest level L whose cumulative threshold is <= xp."""
    if xp <= 0:
        return 0
    # bisect_right gives one past the last threshold <= xp; minus one = the level.
    return min(MAX_LEVEL, bisect.bisect_right(_CUM, xp) - 1)


def progress_from_xp(xp: int) -> tuple[int, int, int]:
    """-> (level, xp_earned_in_level, xp_needed_for_next_level)"""
    level = level_from_xp(xp)
    base = _CUM[level]
    if level >= MAX_LEVEL:
        return level, xp - base, 0
    return level, xp - base, _CUM[level + 1] - base


def _bar(earned: int, needed: int, length: int = 20) -> str:
    if needed <= 0:
        return "▰" * length
    filled = max(0, min(length, round(length * earned / needed)))
    return "▰" * filled + "▱" * (length - filled)


# --- storage --------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER NOT NULL,
    user_id  INTEGER NOT NULL,
    name     TEXT NOT NULL DEFAULT '',
    xp       INTEGER NOT NULL DEFAULT 0,
    msgs     INTEGER NOT NULL DEFAULT 0,
    last_xp  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_levels_lb ON levels (guild_id, xp DESC);
"""

# Display names are SNAPSHOT into the row whenever XP is granted, because this
# bot runs with `intents.members` disabled (a privileged intent) — so
# guild.get_member() can't be trusted to resolve leaderboard entries, and
# falling back to the raw id is what made the board print ids.
_MIGRATE_NAME = "ALTER TABLE levels ADD COLUMN name TEXT NOT NULL DEFAULT ''"


class LevelStore:
    """SQLite-backed XP store.

    One shared connection guarded by a threading.Lock: every statement here is
    an indexed single-row or LIMIT query (sub-millisecond), so running them on
    the event loop is cheaper than paying `asyncio.to_thread` scheduling per
    message. WAL keeps reads from blocking writes if that ever changes.
    """

    def __init__(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            # SQLite has no ADD COLUMN IF NOT EXISTS — check, then add.
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(levels)")}
            if "name" not in cols:
                self._conn.execute(_MIGRATE_NAME)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:
                pass

    def grant_xp(
        self, guild_id: int, user_id: int, now: float, name: str = ""
    ) -> dict | None:
        """Award XP if the cooldown has elapsed; else return None.

        `name` refreshes the stored display-name snapshot on every grant so the
        leaderboard stays current without needing the members intent.
        """
        name = (name or "").strip()[:100]
        with self._lock:
            row = self._conn.execute(
                "SELECT xp, last_xp FROM levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            old_xp = row["xp"] if row else 0
            last = row["last_xp"] if row else 0
            if now - last < XP_COOLDOWN:
                return None

            gain = random.randint(XP_MIN, XP_MAX)
            new_xp = old_xp + gain
            self._conn.execute(
                """
                INSERT INTO levels (guild_id, user_id, name, xp, msgs, last_xp)
                VALUES (?, ?, ?, ?, 1, ?)
                ON CONFLICT (guild_id, user_id) DO UPDATE SET
                    xp = excluded.xp,
                    name = CASE WHEN excluded.name = '' THEN levels.name
                                ELSE excluded.name END,
                    msgs = msgs + 1,
                    last_xp = excluded.last_xp
                """,
                (guild_id, user_id, name, new_xp, now),
            )
            self._conn.commit()
        return {"old_xp": old_xp, "new_xp": new_xp, "gain": gain}

    def get(self, guild_id: int, user_id: int) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT xp, msgs FROM levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
        return dict(row) if row else None

    def rank_of(self, guild_id: int, user_id: int) -> tuple[int | None, int]:
        """-> (1-based rank or None if unranked, total ranked members)"""
        with self._lock:
            row = self._conn.execute(
                "SELECT xp FROM levels WHERE guild_id = ? AND user_id = ?",
                (guild_id, user_id),
            ).fetchone()
            total = self._conn.execute(
                "SELECT COUNT(*) AS c FROM levels WHERE guild_id = ?", (guild_id,)
            ).fetchone()["c"]
        if row is None:
            return None, total
        with self._lock:
            above = self._conn.execute(
                "SELECT COUNT(*) AS c FROM levels WHERE guild_id = ? AND xp > ?",
                (guild_id, row["xp"]),
            ).fetchone()["c"]
        return above + 1, total

    def top(self, guild_id: int, limit: int = LB_SIZE) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT user_id, name, xp, msgs FROM levels
                WHERE guild_id = ?
                ORDER BY xp DESC, msgs DESC, user_id ASC
                LIMIT ?
                """,
                (guild_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]


# --- fonts ----------------------------------------------------------------

_BOLD_FONTS = (
    "data/assets/fonts/font-bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
)
_REG_FONTS = (
    "data/assets/fonts/font.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


@lru_cache(maxsize=128)
def _font(size: int, bold: bool = False):
    """truetype from the first available face, else Pillow's scalable default.

    No font ships with this repo, so the chain has to keep working on
    Termux/Ubuntu/Windows without hand-placed assets.
    """
    for path in (_BOLD_FONTS if bold else _REG_FONTS):
        try:
            from PIL import ImageFont

            return ImageFont.truetype(path, size)
        except Exception:
            continue
    from PIL import ImageFont

    try:
        return ImageFont.load_default(size)  # pillow >= 10.1, returns FreeTypeFont
    except Exception:
        return ImageFont.load_default()


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# --- card rendering -------------------------------------------------------

CARD_W, CARD_H = 720, 240
_AVATAR = 160
_PAD = 40


def _fit_avatar(raw: bytes, size: int):
    """Center-crop to a square, resize, and apply a circular alpha mask."""
    from PIL import Image, ImageDraw, ImageOps

    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im = ImageOps.fit(im, (size, size), Image.Resampling.LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    im.putalpha(mask)
    return im


def _fallback_avatar(size: int):
    from PIL import Image, ImageDraw

    # transparent base so the corners outside the circle stay corners
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse((0, 0, size - 1, size - 1), fill=(120, 132, 255, 255))
    return im


def _round_to(text: str, font, max_w: float, draw) -> str:
    if draw.textlength(text, font=font) <= max_w:
        return text
    while text and draw.textlength(text + "…", font=font) > max_w:
        text = text[:-1]
    return text + "…"


def render_rank_card(
    *,
    name: str,
    avatar_raw: bytes | None,
    level: int,
    earned: int,
    needed: int,
    rank: int | None,
    total: int,
    msgs: int,
) -> bytes:
    """Render the rank card. Raises on failure — caller falls back to an embed."""
    from PIL import Image, ImageDraw

    S = 2  # supersample for clean edges
    w, h = CARD_W * S, CARD_H * S

    card = Image.new("RGBA", (w, h), (26, 28, 34, 255))
    draw = ImageDraw.Draw(card)

    # rounded mask on the whole card
    radius = 24 * S
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    card.putalpha(mask)
    draw = ImageDraw.Draw(card)

    # subtle top accent line
    draw.rectangle((0, 0, w - 1, 5 * S), fill=(255, 200, 60, 255))

    # avatar
    av_size = _AVATAR * S
    av = _fit_avatar(avatar_raw, av_size) if avatar_raw else _fallback_avatar(av_size)
    card.alpha_composite(av, (_PAD * S, (_PAD + 8) * S))
    draw = ImageDraw.Draw(card)

    text_x = (_PAD + _AVATAR + 28) * S
    right = (CARD_W - 40) * S

    # Layout the level block FIRST: its width varies (2 digits vs 4 at MAX), and
    # both text lines must stop short of it or a 4-digit level collides with the
    # name. Measuring after the fact is what let "MAXED_PLAYER" run into "1000".
    f_lvl_lbl = _font(15 * S, bold=True)
    f_lvl = _font(52 * S, bold=True)
    lvl_str = str(level)
    lvl_w = draw.textlength(lvl_str, font=f_lvl)
    lbl = "LEVEL"
    lbl_w = draw.textlength(lbl, font=f_lvl_lbl)
    # widest of the two right-aligned pieces sets how far left the level block reaches
    level_block_left = right - max(lvl_w, lbl_w)
    text_budget = max(40 * S, level_block_left - text_x - 24 * S)

    # name
    f_name = _font(34 * S, bold=True)
    name = _round_to(name, f_name, text_budget, draw)
    draw.text((text_x, 46 * S), name, font=f_name, fill=(245, 246, 250, 255))

    # rank / messages sub-line — drop the message count rather than cut a number
    # in half, which reads as a rendering bug ("1,00,00…").
    f_sub = _font(19 * S)
    rank_txt = f"#{rank}" if rank else "unranked"
    sub = f"Rank {rank_txt} of {total}   •   {msgs:,} messages"
    if draw.textlength(sub, font=f_sub) > text_budget:
        sub = f"Rank {rank_txt} of {total}"
    sub = _round_to(sub, f_sub, text_budget, draw)
    draw.text((text_x, 96 * S), sub, font=f_sub, fill=(150, 155, 170, 255))

    # big level number, right-aligned
    draw.text((level_block_left, 34 * S), lbl, font=f_lvl_lbl, fill=(255, 200, 60, 255))
    draw.text((right - lvl_w, 54 * S), lvl_str, font=f_lvl, fill=(255, 200, 60, 255))

    # progress bar
    bar_x, bar_y = text_x, 158 * S
    bar_w, bar_h = right - text_x, 22 * S
    pct = 1.0 if needed <= 0 else max(0.0, min(1.0, earned / needed))

    bar = Image.new("RGBA", (bar_w, bar_h), (52, 55, 64, 255))
    fill_w = int(bar_w * pct)
    if fill_w > 0:
        c0, c1 = (255, 176, 32), (255, 224, 100)
        grad = Image.new("RGB", (fill_w, bar_h))
        gd = ImageDraw.Draw(grad)
        for i in range(fill_w):
            gd.line([(i, 0), (i, bar_h)], fill=_lerp(c0, c1, i / max(1, fill_w - 1)))
        bar.paste(grad.convert("RGBA"), (0, 0))

    bmask = Image.new("L", (bar_w, bar_h), 0)
    ImageDraw.Draw(bmask).rounded_rectangle(
        (0, 0, bar_w - 1, bar_h - 1), radius=bar_h // 2, fill=255
    )
    bar.putalpha(bmask)
    card.alpha_composite(bar, (bar_x, bar_y))
    draw = ImageDraw.Draw(card)

    # bar labels
    f_small = _font(17 * S)
    need_txt = "MAX" if needed <= 0 else f"{earned:,} / {needed:,} XP"
    draw.text((bar_x, 190 * S), need_txt, font=f_small, fill=(150, 155, 170, 255))
    pct_txt = "100%" if needed <= 0 else f"{int(pct * 100)}%"
    pw = draw.textlength(pct_txt, font=f_small)
    draw.text((right - pw, 190 * S), pct_txt, font=f_small, fill=(150, 155, 170, 255))

    # Re-apply the rounded mask AFTER all drawing: `draw.rectangle` for the gold
    # accent above writes opaque alpha, which would otherwise leave the card's
    # top corners square and poking out.
    card.putalpha(mask)

    out = card.resize((CARD_W, CARD_H), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# --- cog ------------------------------------------------------------------

class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store: LevelStore | None = None
        self.session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self.store = await asyncio.to_thread(LevelStore, DB_PATH)
        self.session = get_shared_session()
        log.info("Leveling ready (SQLite at %s)", DB_PATH)

    async def cog_unload(self) -> None:
        # Don't close shared session - bot.py handles it
        if self.store:
            await asyncio.to_thread(self.store.close)
            self.store = None

    # --- XP on messages ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        # Rule 3: XP and level-up posts are passive behaviour, so an admin can
        # switch them off. Prefix commands have their own switch, checked by
        # the global check in bot.py.
        if not passive_allowed(message.guild):
            return
        if not (message.content.strip() or message.attachments or message.stickers):
            return
        store = self.store
        if store is None:
            return

        try:
            result = await asyncio.to_thread(
                store.grant_xp,
                message.guild.id,
                message.author.id,
                time.time(),
                getattr(message.author, "display_name", "") or "",
            )
        except Exception:
            log.exception("XP grant failed for %s", message.author.id)
            return

        if not result:
            return  # still on cooldown

        old_level = level_from_xp(result["old_xp"])
        new_level = level_from_xp(result["new_xp"])
        if new_level > old_level:
            await self._announce_level_up(message, new_level, result["new_xp"])

    async def _announce_level_up(
        self, message: discord.Message, level: int, xp: int
    ) -> None:
        """Embeds never ping, so announcing in-channel can't spam notifications."""
        earned, needed = progress_from_xp(xp)[1:]
        embed = discord.Embed(
            title="🎉 Level Up!",
            description=(
                f"**{message.author.display_name}** reached **level {level}**!\n"
                f"`{_bar(earned, needed, 22)}` "
                + ("MAX" if needed <= 0 else f"{earned:,}/{needed:,} XP")
            ),
            color=discord.Color.gold(),
        )
        avatar = message.author.display_avatar.replace(size=64).url
        embed.set_thumbnail(url=avatar)
        try:
            await message.channel.send(embed=embed)
        except discord.Forbidden:
            # no embed_links/send_messages here — fall back to plain text
            try:
                await message.channel.send(
                    f"🎉 **{message.author.display_name}** reached **level {level}**!"
                )
            except discord.Forbidden:
                pass
        except discord.HTTPException:
            pass

    # --- avatar helper ---

    async def _avatar_bytes(self, user: discord.abc.User) -> bytes | None:
        if not self.session or self.session.closed:
            self.session = get_shared_session()
        url = user.display_avatar.replace(size=256, static_format="png").url
        try:
            async with self.session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
        except Exception:
            log.debug("avatar fetch failed for %s", user.id, exc_info=True)
        return None

    async def _resolve(self, guild: discord.Guild, user_id: int, cached_name: str = "") -> str:
        """Best available display name. `cached_name` (from the DB) wins because
        it needs no intents — see _MIGRATE_NAME for why the cache can't be
        trusted here."""
        if cached_name:
            return cached_name
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        user = self.bot.get_user(user_id)
        if user:
            return user.display_name
        try:  # legacy rows predate the name snapshot; one REST call each
            member = await guild.fetch_member(user_id)
            if member:
                return member.display_name
        except Exception:
            pass
        return f"User {user_id}"

    # --- rank ---

    async def _rank_embed(
        self, target: discord.abc.User, guild: discord.Guild
    ) -> discord.Embed:
        store = self.store
        data = (store.get(guild.id, target.id) if store else None) or {"xp": 0, "msgs": 0}
        xp = data["xp"]
        level, earned, needed = progress_from_xp(xp)
        rank, total = store.rank_of(guild.id, target.id) if store else (None, 0)

        embed = discord.Embed(
            title=f"{target.display_name}'s Rank",
            color=discord.Color.blurple(),
        )
        embed.set_thumbnail(url=target.display_avatar.replace(size=256).url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(
            name="Rank",
            value=(f"**#{rank}** / {total}" if rank else f"unranked / {total}"),
            inline=True,
        )
        embed.add_field(name="Total XP", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Messages", value=f"**{data['msgs']:,}**", inline=True)
        need = "MAX" if needed <= 0 else f"{earned:,} / {needed:,} XP"
        embed.add_field(
            name=f"Progress to level {level + 1 if needed else level}",
            value=f"`{_bar(earned, needed)}` **{need}**",
            inline=False,
        )
        return embed

    async def _send_rank(self, destination, target: discord.abc.User, guild: discord.Guild):
        """Rendered card when possible, plain embed when rendering fails."""
        store = self.store
        data = (store.get(guild.id, target.id) if store else None) or {"xp": 0, "msgs": 0}
        xp = data["xp"]
        level, earned, needed = progress_from_xp(xp)
        rank, total = store.rank_of(guild.id, target.id) if store else (None, 0)

        member = guild.get_member(target.id)
        name = member.display_name if member else target.display_name

        raw = await self._avatar_bytes(target)
        try:
            loop = asyncio.get_running_loop()
            png = await loop.run_in_executor(
                None,
                lambda: render_rank_card(
                    name=name,
                    avatar_raw=raw,
                    level=level,
                    earned=earned,
                    needed=needed,
                    rank=rank,
                    total=total,
                    msgs=data["msgs"],
                ),
            )
            file = discord.File(fp=io.BytesIO(png), filename="rank.png")
            embed = discord.Embed(color=discord.Color.blurple())
            embed.set_image(url="attachment://rank.png")
            await destination.send(embed=embed, file=file)
            return
        except Exception:
            log.warning("rank card render failed, falling back to embed", exc_info=True)

        await destination.send(embed=await self._rank_embed(target, guild))

    @commands.command(name="rank")
    async def rank_prefix(self, ctx: commands.Context, *, user: discord.Member = None):
        """Show your (or another member's) rank card."""
        target = user or ctx.author
        await self._send_rank(ctx, target, ctx.guild)

    @app_commands.command(name="rank", description="Show your level, XP and server rank.")
    @app_commands.describe(user="Whose rank card to show (defaults to you)")
    async def rank_slash(
        self, interaction: discord.Interaction, user: discord.Member | None = None
    ):
        await interaction.response.defer()
        target = user or interaction.user
        await self._send_rank(interaction.followup, target, interaction.guild)

    # --- leaderboard ---

    async def _leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        store = self.store
        rows = store.top(guild.id) if store else []
        if not rows:
            return discord.Embed(
                title="🏆 Leaderboard",
                description="No one has earned XP yet. Send some messages!",
                color=discord.Color.gold(),
            )

        lines = []
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        for i, row in enumerate(rows, start=1):
            name = await self._resolve(guild, row["user_id"], row.get("name", ""))
            level = level_from_xp(row["xp"])
            badge = medals.get(i, f"`{i}.`")
            lines.append(f"{badge} **{name}** — Lv. **{level}** · `{row['xp']:,}` XP")

        embed = discord.Embed(
            title=f"🏆 {guild.name} Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )

        # show where the caller lands if they didn't make the top cut
        return embed

    async def _send_leaderboard(self, destination, guild: discord.Guild, user_id: int):
        embed = await self._leaderboard_embed(guild)
        store = self.store
        if store:
            rows = store.top(guild.id)
            in_top = any(r["user_id"] == user_id for r in rows)
            if not in_top:
                rank, total = store.rank_of(guild.id, user_id)
                if rank:
                    me = store.get(guild.id, user_id) or {"xp": 0}
                    name = await self._resolve(guild, user_id)
                    embed.add_field(
                        name="Your position",
                        value=(
                            f"**#{rank}** / {total} — {name} · "
                            f"Lv. **{level_from_xp(me['xp'])}** · `{me['xp']:,}` XP"
                        ),
                        inline=False,
                    )
        await destination.send(embed=embed)

    # `top`, not `leaderboard` — Shigure Ui already owns `leaderboard` (rule 4a).
    @commands.command(name="top")
    async def lb_prefix(self, ctx: commands.Context):
        """Show the server's top 10 by XP."""
        await self._send_leaderboard(ctx, ctx.guild, ctx.author.id)

    @app_commands.command(name="the-leaderboard", description="Top 10 members by XP in this server.")
    async def lb_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._send_leaderboard(interaction.followup, interaction.guild, interaction.user.id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
