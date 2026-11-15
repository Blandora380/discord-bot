import asyncio
import datetime
import io
import logging
import os
import random
import time
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from pykakasi import kakasi

from cogs.settings import prefix_allowed
from bot import get_shared_session
from shared.cards import (
    ATTR_COLORS,
    ATTR_EMOJIS,
    CHARACTERS as CHARACTERS_SIMPLE,
    CHARACTERS_DETAILED,
    RARITY_STARS,
    card_data,
)

log = logging.getLogger("card_cog")

CACHE_TTL = 60 * 60 * 24  # 24 hours
IMAGE_CACHE_DIR = Path("cache/pjsk/images")


def format_card_embed(card: dict, index: int, total: int, trained: bool, filename: Optional[str] = None) -> discord.Embed:
    char_id = card.get("characterId", 1)
    char_info = CHARACTERS_DETAILED.get(char_id, {"name": "Unknown", "jp": "不明", "unit": "Unknown"})
    char_name = char_info["name"]
    char_jp = char_info["jp"]
    unit = char_info["unit"]

    prefix = card.get("prefix", "Unknown")
    attr = card.get("attr", "cool")
    attr_emoji = ATTR_EMOJIS.get(attr, "")
    rarity_type = card.get("cardRarityType", "rarity_2")
    stars = RARITY_STARS.get(rarity_type, "⭐")
    asset = card.get("assetbundleName", "")
    card_id = card.get("id", "-")

    has_training = rarity_type in ("rarity_3", "rarity_4", "rarity_birthday")
    actual_trained = trained and has_training
    art_status = "After Training" if actual_trained else "Normal"

    thumb_url = f"https://storage.sekai.best/sekai-jp-assets/character/member_cutout/{asset}/normal.png"

    embed = discord.Embed(
        title=f"{stars} [{prefix}] {char_name}",
        description=f"**Japanese Name:** {char_jp}\n**Unit:** {unit}",
        color=ATTR_COLORS.get(attr, 0x5865F2),
    )

    embed.add_field(name="Attribute", value=f"{attr_emoji} {attr.capitalize()}", inline=True)
    embed.add_field(name="Card ID", value=f"#{card_id}", inline=True)
    embed.add_field(name="Art Version", value=art_status, inline=True)

    skill_name = card.get("cardSkillName")
    if skill_name and skill_name != "-":
        embed.add_field(name="Skill Name", value=skill_name, inline=True)

    release_at = card.get("releaseAt")
    if release_at:
        try:
            rel_date = datetime.datetime.fromtimestamp(release_at / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            embed.add_field(name="Release Date", value=rel_date, inline=True)
        except Exception:
            pass

    if filename:
        embed.set_image(url=f"attachment://{filename}")
    else:
        img_type = "card_after_training" if actual_trained else "card_normal"
        embed.set_image(url=f"https://storage.sekai.best/sekai-jp-assets/character/member/{asset}/{img_type}.webp")

    embed.set_thumbnail(url=thumb_url)
    embed.set_footer(text=f"Card {index + 1} of {total} • Project Sekai Card Viewer")

    return embed


def format_card_text(card: dict, index: int, total: int, trained: bool) -> str:
    char_id = card.get("characterId", 1)
    char_info = CHARACTERS_DETAILED.get(char_id, {"name": "Unknown", "jp": "不明", "unit": "Unknown"})
    char_name = char_info["name"]
    char_jp = char_info["jp"]
    unit = char_info["unit"]

    prefix = card.get("prefix", "Unknown")
    attr = card.get("attr", "cool")
    attr_emoji = ATTR_EMOJIS.get(attr, "")
    rarity_type = card.get("cardRarityType", "rarity_2")
    stars = RARITY_STARS.get(rarity_type, "⭐")
    card_id = card.get("id", "-")

    has_training = rarity_type in ("rarity_3", "rarity_4", "rarity_birthday")
    actual_trained = trained and has_training
    art_status = "After Training" if actual_trained else "Normal"

    lines = [
        f"**{stars} [{prefix}] {char_name}** ({char_jp})",
        f"**Unit:** {unit} • **Attribute:** {attr_emoji} {attr.capitalize()}",
        f"**Card ID:** `#{card_id}` • **Art Version:** {art_status}",
    ]
    skill_name = card.get("cardSkillName")
    if skill_name and skill_name != "-":
        lines.append(f"**Skill:** {skill_name}")

    release_at = card.get("releaseAt")
    if release_at:
        try:
            rel_date = datetime.datetime.fromtimestamp(release_at / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d")
            lines.append(f"**Release Date:** {rel_date}")
        except Exception:
            pass

    lines.append(f"`Card {index + 1} of {total}`")

    return "\n".join(lines)


class CardView(discord.ui.View):
    def __init__(self, cog: "Card", cards: list[dict], author_id: int, use_embed: bool = True):
        super().__init__(timeout=180)
        self.cog = cog
        self.cards = cards
        self.author_id = author_id
        self.use_embed = use_embed
        self.index = 0
        current_card = self.cards[self.index]
        self.trained = current_card.get("cardRarityType") in ("rarity_3", "rarity_4", "rarity_birthday")
        self._update_buttons()

    def _update_buttons(self):
        current_card = self.cards[self.index]
        has_training = current_card.get("cardRarityType") in ("rarity_3", "rarity_4", "rarity_birthday")
        self.btn_art.disabled = not has_training
        self.btn_prev.disabled = len(self.cards) <= 1
        self.btn_next.disabled = len(self.cards) <= 1
        self.btn_random.disabled = len(self.cards) <= 1

    async def update_message(self, interaction: discord.Interaction):
        await interaction.response.defer()
        current_card = self.cards[self.index]
        self._update_buttons()

        has_training = current_card.get("cardRarityType") in ("rarity_3", "rarity_4", "rarity_birthday")
        actual_trained = self.trained and has_training
        asset = current_card.get("assetbundleName", "")

        img_buf, filename = await self.cog.get_card_image(asset, actual_trained)
        file = discord.File(fp=img_buf, filename=filename) if img_buf else None

        if self.use_embed:
            try:
                embed = format_card_embed(current_card, self.index, len(self.cards), actual_trained, filename=filename if file else None)
                if file:
                    await interaction.message.edit(content=None, embed=embed, attachments=[file], view=self)
                else:
                    await interaction.message.edit(content=None, embed=embed, view=self)
                return
            except discord.Forbidden:
                self.use_embed = False
                if file:
                    file.fp.seek(0)

        text = format_card_text(current_card, self.index, len(self.cards), actual_trained)
        if file:
            await interaction.message.edit(content=text, embed=None, attachments=[file], view=self)
        else:
            await interaction.message.edit(content=text, embed=None, view=self)

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index - 1) % len(self.cards)
        current_card = self.cards[self.index]
        if current_card.get("cardRarityType") not in ("rarity_3", "rarity_4", "rarity_birthday"):
            self.trained = False
        await self.update_message(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.index = (self.index + 1) % len(self.cards)
        current_card = self.cards[self.index]
        if current_card.get("cardRarityType") not in ("rarity_3", "rarity_4", "rarity_birthday"):
            self.trained = False
        await self.update_message(interaction)

    @discord.ui.button(label="🎨 Switch Art", style=discord.ButtonStyle.primary)
    async def btn_art(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.trained = not self.trained
        await self.update_message(interaction)

    @discord.ui.button(label="🎲 Random", style=discord.ButtonStyle.secondary)
    async def btn_random(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.cards) > 1:
            candidates = [i for i in range(len(self.cards)) if i != self.index]
            self.index = random.choice(candidates)
        current_card = self.cards[self.index]
        await self.update_message(interaction)


class Card(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None
        self._kks = kakasi()

    async def cog_load(self):
        self.session = get_shared_session()
        asyncio.create_task(card_data.ensure_loaded())

    async def cog_unload(self):
        # Don't close shared session here - bot.py handles it
        pass

    def _romanize(self, text: str) -> str:
        try:
            result = self._kks.convert(text)
            return "".join(item["hepburn"] for item in result).lower()
        except Exception:
            return text.lower()

    async def get_card_image(self, asset: str, trained: bool) -> tuple[Optional[io.BytesIO], str]:
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        img_type = "card_after_training" if trained else "card_normal"
        filename = f"{asset}_{img_type}.webp"
        local_path = IMAGE_CACHE_DIR / filename

        if local_path.exists():
            try:
                data = local_path.read_bytes()
                if len(data) > 0:
                    return io.BytesIO(data), filename
            except Exception as e:
                log.warning(f"Error reading cached image {local_path}: {e}")

        urls = [
            f"https://storage.sekai.best/sekai-jp-assets/character/member/{asset}/{img_type}.webp",
            f"https://storage.sekai.best/sekai-jp-assets/character/member_small/{asset}/{img_type}.webp",
        ]
        if self.session is None or self.session.closed:
            self.session = get_shared_session()

        for url in urls:
            try:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        try:
                            local_path.write_bytes(data)
                        except Exception:
                            pass
                        return io.BytesIO(data), filename
            except Exception as e:
                log.warning(f"Failed to fetch {url}: {e}")

        # If trained image was requested but not found (e.g. 1★ or 2★), fallback to normal
        if trained:
            return await self.get_card_image(asset, trained=False)

        return None, filename

    def search_cards(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []

        query_l = query.lower()
        query_romaji = self._romanize(query)

        # 1. Search by Card ID
        clean_id = query_l.removeprefix("id:").removeprefix("#").strip()
        if clean_id.isdigit():
            target_id = int(clean_id)
            for c in card_data.all_cards:
                if c.get("id") == target_id:
                    return [c]

        # 2. Check if query matches character name / aliases
        matched_char_ids = set()
        for cid, cinfo in CHARACTERS_DETAILED.items():
            if query_l in cinfo["name"].lower():
                matched_char_ids.add(cid)
            elif query_l in cinfo["jp"]:
                matched_char_ids.add(cid)
            elif any(query_l == a or query_l in a for a in cinfo["aliases"]):
                matched_char_ids.add(cid)

        # 3. Match cards
        matches = []
        for c in card_data.all_cards:
            cid = c.get("characterId")
            prefix = str(c.get("prefix", ""))
            prefix_l = prefix.lower()
            prefix_romaji = self._romanize(prefix)
            skill_name = str(c.get("cardSkillName", "")).lower()

            # Priority match by character
            if cid in matched_char_ids:
                matches.append(c)
            # Match by card title / prefix
            elif query_l in prefix_l or query_romaji in prefix_romaji or query_l in skill_name:
                matches.append(c)

        # Sort matches so newest (highest ID) or highest rarity comes first
        def sort_key(card: dict):
            r = card.get("cardRarityType", "")
            rarity_score = 4 if "4" in r or "birthday" in r else (3 if "3" in r else 2)
            return (rarity_score, card.get("id", 0))

        matches.sort(key=sort_key, reverse=True)
        return matches

    async def handle_card_request(self, destination, user_id: int, query: str):
        query = query.strip()
        if not query:
            await destination.send("❌ Please provide a character name, card title, or ID. Example: `the!card miku` or `the!card 4`")
            return

        try:
            await card_data.ensure_loaded()
            matches = self.search_cards(query)

            if not matches:
                await destination.send(f"❌ No cards found matching `{query}`.")
                return

            # Check if destination channel has embed permissions
            can_embed = True
            channel = getattr(destination, "channel", destination)
            guild = getattr(channel, "guild", None)
            if guild and hasattr(channel, "permissions_for"):
                me = guild.me
                if me:
                    can_embed = channel.permissions_for(me).embed_links

            current_card = matches[0]
            view = CardView(self, matches, user_id, use_embed=can_embed)
            has_training = current_card.get("cardRarityType") in ("rarity_3", "rarity_4", "rarity_birthday")
            actual_trained = view.trained and has_training
            asset = current_card.get("assetbundleName", "")

            img_buf, filename = await self.get_card_image(asset, actual_trained)
            file = discord.File(fp=img_buf, filename=filename) if img_buf else None

            if can_embed:
                try:
                    embed = format_card_embed(current_card, 0, len(matches), actual_trained, filename=filename if file else None)
                    if file:
                        await destination.send(embed=embed, file=file, view=view)
                    else:
                        await destination.send(embed=embed, view=view)
                    return
                except discord.Forbidden:
                    view.use_embed = False
                    if file:
                        file.fp.seek(0)

            # Fallback to formatted text with attached file
            text = format_card_text(current_card, 0, len(matches), actual_trained)
            if file:
                await destination.send(content=text, file=file, view=view)
            else:
                await destination.send(content=text, view=view)
        except Exception:
            log.exception("Error handling card request")
            await destination.send("⚠️ Couldn't load that card. Please try again.")

    @commands.command(name="card", help="Search and view Project Sekai cards")
    async def card_prefix(self, ctx: commands.Context, *, query: str = ""):
        async with ctx.typing():
            await self.handle_card_request(ctx, ctx.author.id, query)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild):  # rule 3
            return

        content = message.content.strip()
        if not content.lower().startswith("the!card"):
            return

        # Avoid double-handling if command processor already handled it
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        query = content[len("the!card"):].strip()
        async with message.channel.typing():
            await self.handle_card_request(message.channel, message.author.id, query)

    @app_commands.command(name="card", description="Search and view Project Sekai cards")
    @app_commands.describe(query="Character name (e.g. Miku, Ichika), card title, or card ID")
    async def card_slash(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        try:
            await card_data.ensure_loaded()
            matches = self.search_cards(query)

            if not matches:
                await interaction.followup.send(f"❌ No cards found matching `{query}`.", ephemeral=True)
                return

            can_embed = True
            if interaction.guild and interaction.channel and hasattr(interaction.channel, "permissions_for"):
                me = interaction.guild.me
                if me:
                    can_embed = interaction.channel.permissions_for(me).embed_links

            current_card = matches[0]
            view = CardView(self, matches, interaction.user.id, use_embed=can_embed)
            has_training = current_card.get("cardRarityType") in ("rarity_3", "rarity_4", "rarity_birthday")
            actual_trained = view.trained and has_training
            asset = current_card.get("assetbundleName", "")

            img_buf, filename = await self.get_card_image(asset, actual_trained)
            file = discord.File(fp=img_buf, filename=filename) if img_buf else None

            if can_embed:
                try:
                    embed = format_card_embed(current_card, 0, len(matches), actual_trained, filename=filename if file else None)
                    if file:
                        await interaction.followup.send(embed=embed, file=file, view=view)
                    else:
                        await interaction.followup.send(embed=embed, view=view)
                    return
                except discord.Forbidden:
                    view.use_embed = False
                    if file:
                        file.fp.seek(0)

            text = format_card_text(current_card, 0, len(matches), actual_trained)
            if file:
                await interaction.followup.send(content=text, file=file, view=view)
            else:
                await interaction.followup.send(content=text, view=view)
        except Exception:
            log.exception("Error in card_slash")
            await interaction.followup.send(
                "⚠️ Couldn't load that card. Please try again.", ephemeral=True
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Card(bot))