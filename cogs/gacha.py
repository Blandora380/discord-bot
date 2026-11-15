import asyncio
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
from PIL import Image, ImageDraw, ImageFont

from cogs.settings import prefix_allowed
from bot import get_shared_session
from shared.cards import (
    ATTR_COLORS,
    ATTR_EMOJIS,
    CHARACTERS,
    GACHA_IMAGE_CACHE_DIR as IMAGE_CACHE_DIR,
    RARITY_BORDER_COLORS,
    RARITY_STARS,
    card_data,
    get_rarity_num,
)

log = logging.getLogger("gacha_cog")


class GachaView(discord.ui.View):
    def __init__(self, cog: "Gacha", author_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.author_id = author_id

    @discord.ui.button(label="Pull 10x 🎲", style=discord.ButtonStyle.primary)
    async def pull_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, file = await self.cog.perform_gacha(interaction.user, pulls=10)
        if file:
            await interaction.followup.send(embed=embed, file=file, view=GachaView(self.cog, interaction.user.id))
        else:
            await interaction.followup.send(embed=embed, view=GachaView(self.cog, interaction.user.id))

    @discord.ui.button(label="Pull 1x 🎯", style=discord.ButtonStyle.secondary)
    async def pull_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed, file = await self.cog.perform_gacha(interaction.user, pulls=1)
        if file:
            await interaction.followup.send(embed=embed, file=file, view=GachaView(self.cog, interaction.user.id))
        else:
            await interaction.followup.send(embed=embed, view=GachaView(self.cog, interaction.user.id))


class Gacha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        # Use shared session
        self.session = get_shared_session()
        # Preload card data in background
        asyncio.create_task(card_data.ensure_loaded())

    async def _fetch_cutout(self, assetbundle_name: str) -> Optional[Image.Image]:
        url = f"https://storage.sekai.best/sekai-jp-assets/character/member_cutout/{assetbundle_name}/normal.png"
        try:
            assert self.session is not None
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    raw = await resp.read()
                    return Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            pass
        return None

    def _render_10pull_grid(self, cards: list[dict], cutouts: list[Optional[Image.Image]]) -> io.BytesIO:
        """Stitches 10 cards into a stylish 5x2 grid with rarity borders."""
        card_w, card_h = 140, 140
        padding = 14
        cols, rows = 5, 2
        total_w = cols * card_w + (cols + 1) * padding
        total_h = rows * card_h + (rows + 1) * padding

        canvas = Image.new("RGBA", (total_w, total_h), (24, 26, 32, 255))
        draw = ImageDraw.Draw(canvas)

        for idx, (card, cutout) in enumerate(zip(cards, cutouts)):
            col = idx % cols
            row = idx // cols
            x = padding + col * (card_w + padding)
            y = padding + row * (card_h + padding)

            rarity = card.get("cardRarityType", "rarity_2")
            border_color = RARITY_BORDER_COLORS.get(rarity, (150, 150, 150))
            stars = get_rarity_num(rarity)

            # Draw tile background
            draw.rectangle([x, y, x + card_w, y + card_h], fill=(36, 39, 48, 255))

            # Paste cutout image
            if cutout:
                resized_cutout = cutout.resize((card_w - 8, card_h - 8), Image.Resampling.LANCZOS)
                canvas.paste(resized_cutout, (x + 4, y + 4), resized_cutout)

            # Draw rarity border
            border_width = 4 if stars >= 4 else (3 if stars == 3 else 2)
            for b in range(border_width):
                draw.rectangle([x + b, y + b, x + card_w - b, y + card_h - b], outline=border_color)

            # Draw star badge background and stars text at bottom
            badge_h = 24
            badge_y = y + card_h - badge_h
            draw.rectangle([x, badge_y, x + card_w, y + card_h], fill=(0, 0, 0, 180))

            star_symbols = "⭐" * stars
            draw.text((x + 8, badge_y + 4), star_symbols, fill=border_color)

        output = io.BytesIO()
        canvas.save(output, format="PNG")
        output.seek(0)
        return output

    async def perform_gacha(self, user: discord.User | discord.Member, pulls: int = 10) -> tuple[discord.Embed, Optional[discord.File]]:
        await card_data.ensure_loaded()

        if pulls == 1:
            card = card_data.roll_one_card(guaranteed_3star=False)
            rarity = card.get("cardRarityType", "rarity_2")
            stars = get_rarity_num(rarity)
            char_id = card.get("characterId", 1)
            char_name = CHARACTERS.get(char_id, "Unknown")
            attr = card.get("attr", "cool")
            attr_emoji = ATTR_EMOJIS.get(attr, "")
            color = ATTR_COLORS.get(attr, 0x5865F2)
            prefix = card.get("prefix", "")
            asset = card.get("assetbundleName", "")

            title = f"{'⭐' * stars} {attr_emoji} [{prefix}] {char_name}"
            embed = discord.Embed(
                title=title,
                description=f"**{user.display_name}** pulled a **{stars}★** card!",
                color=color,
            )

            # Try after_training for 3★/4★ or normal for 2★
            img_type = "card_after_training" if stars >= 3 and random.random() > 0.3 else "card_normal"
            img_url = f"https://storage.sekai.best/sekai-jp-assets/character/member_small/{asset}/{img_type}.webp"
            embed.set_image(url=img_url)
            embed.set_footer(text=f"Attribute: {attr.capitalize()} | ID: {card.get('id', '-')}")
            return embed, None

        # 10-Pull
        cards = []
        for i in range(9):
            cards.append(card_data.roll_one_card(guaranteed_3star=False))
        # 10th pull guaranteed 3★+
        cards.append(card_data.roll_one_card(guaranteed_3star=True))

        # Count rarities
        count_4 = sum(1 for c in cards if get_rarity_num(c.get("cardRarityType", "")) >= 4)
        count_3 = sum(1 for c in cards if get_rarity_num(c.get("cardRarityType", "")) == 3)
        count_2 = sum(1 for c in cards if get_rarity_num(c.get("cardRarityType", "")) == 2)

        # Download cutouts concurrently
        cutout_tasks = [self._fetch_cutout(c.get("assetbundleName", "")) for c in cards]
        cutouts = await asyncio.gather(*cutout_tasks)

        # Generate Pillow grid in executor to avoid blocking event loop
        loop = asyncio.get_running_loop()
        img_buffer = await loop.run_in_executor(None, self._render_10pull_grid, cards, cutouts)
        file = discord.File(fp=img_buffer, filename="gacha_result.png")

        # Select highest card for embed highlight
        sorted_cards = sorted(cards, key=lambda c: get_rarity_num(c.get("cardRarityType", "")), reverse=True)
        top_card = sorted_cards[0]
        top_stars = get_rarity_num(top_card.get("cardRarityType", ""))
        top_char = CHARACTERS.get(top_card.get("characterId", 1), "Unknown")
        top_prefix = top_card.get("prefix", "")
        top_attr = top_card.get("attr", "cool")

        embed_color = 0xFFD700 if count_4 > 0 else (0xE6A100 if count_3 > 0 else 0x5865F2)
        summary_lines = [
            f"**Results:** {'🌈' if count_4 else '⭐'} **{count_4}x** 4★ | 🌟 **{count_3}x** 3★ | ⚪ **{count_2}x** 2★",
            f"**Best Pull:** {'⭐' * top_stars} [{top_prefix}] **{top_char}** {ATTR_EMOJIS.get(top_attr, '')}",
        ]

        embed = discord.Embed(
            title=f"🎲 Gacha 10-Pull for {user.display_name}",
            description="\n".join(summary_lines),
            color=embed_color,
        )
        embed.set_image(url="attachment://gacha_result.png")
        embed.set_footer(text="Project Sekai Gacha Simulator • 4★: 3% | 3★: 8.5% | Guaranteed 3★+")

        return embed, file

    async def handle_gacha_request(self, destination, user, pulls: int = 10):
        try:
            embed, file = await self.perform_gacha(user, pulls=pulls)
            view = GachaView(self, user.id)
            try:
                if file:
                    await destination.send(embed=embed, file=file, view=view)
                else:
                    await destination.send(embed=embed, view=view)
            except discord.Forbidden:
                # If embed links permission is missing, send as normal message
                msg_text = f"🎲 **Gacha Results for {user.display_name}**\n{embed.description or ''}"
                if file:
                    file.fp.seek(0)
                    await destination.send(content=msg_text, file=file, view=view)
                else:
                    await destination.send(content=msg_text, view=view)
        except Exception:
            log.exception("Error handling gacha")
            await destination.send("⚠️ Gacha pull failed. Please try again.")

    @commands.command(name="gacha", help="Pull cards from the Project Sekai gacha simulator")
    async def gacha_prefix(self, ctx: commands.Context, pulls: int = 10):
        pulls = 1 if pulls <= 1 else 10
        async with ctx.typing():
            await self.handle_gacha_request(ctx, ctx.author, pulls=pulls)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild):  # rule 3
            return

        content = message.content.strip()
        if not content.lower().startswith("the!gacha"):
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        parts = content.split()
        pulls = 10
        if len(parts) > 1 and parts[1].isdigit():
            val = int(parts[1])
            pulls = 1 if val <= 1 else 10

        async with message.channel.typing():
            await self.handle_gacha_request(message.channel, message.author, pulls=pulls)

    @app_commands.command(name="gacha", description="Pull cards from the Project Sekai gacha simulator")
    @app_commands.describe(pulls="Choose 10-pull or single pull (default: 10)")
    @app_commands.choices(
        pulls=[
            app_commands.Choice(name="10-Pull (Guaranteed 3★+)", value=10),
            app_commands.Choice(name="1-Pull", value=1),
        ]
    )
    async def gacha_slash(self, interaction: discord.Interaction, pulls: Optional[app_commands.Choice[int]] = None):
        count = pulls.value if pulls else 10
        await interaction.response.defer()
        embed, file = await self.perform_gacha(interaction.user, pulls=count)
        view = GachaView(self, interaction.user.id)
        if file:
            await interaction.followup.send(embed=embed, file=file, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Gacha(bot))