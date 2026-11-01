import os
import json
import random
import discord
from discord.ext import commands

QUOTES_FILE = "data/quotes.json"

def load_quotes():
    if not os.path.exists(QUOTES_FILE):
        return []
    try:
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_quotes(quotes):
    os.makedirs(os.path.dirname(QUOTES_FILE), exist_ok=True)
    with open(QUOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(quotes, f, ensure_ascii=False, indent=2)

class Quote(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="quote")
    async def get_quote(self, ctx):
        quotes = load_quotes()
        if not quotes:
            await ctx.send("❌ No quotes saved yet! Add one with `the!addquote <message>` or attach a sticker.")
            return

        item = random.choice(quotes)
        text_content = f"\"{item['text']}\" — {item['author']}"
        image_url = item.get("image_url")

        try:
            embed = discord.Embed(
                description=text_content,
                color=discord.Color.blurple()
            )
            if image_url:
                embed.set_image(url=image_url)
            await ctx.send(embed=embed)
        except Exception:
            image_text = f"\n{image_url}" if image_url else ""
            await ctx.send(f"{text_content}{image_text}")

    @commands.command(name="addquote")
    async def add_quote(self, ctx, *, text: str = None):
        image_url = None
        if ctx.message.stickers:
            sticker = ctx.message.stickers[0]
            if not (getattr(sticker, "format", None) and sticker.format.value == 3):
                image_url = sticker.url
            if not text:
                text = f"Sticker: {sticker.name}"

        if not text:
            await ctx.send("❌ Invalid format! Example: `the!addquote Hello world` or attach a sticker.")
            return

        quotes = load_quotes()
        quote_entry = {
            "text": text,
            "author": ctx.author.display_name,
            "author_id": ctx.author.id
        }
        if image_url:
            quote_entry["image_url"] = image_url

        quotes.append(quote_entry)
        save_quotes(quotes)
        await ctx.send(f"✅ Quote added successfully! Total quotes: {len(quotes)}")

    @commands.command(name="quotelist")
    async def quote_list(self, ctx):
        quotes = load_quotes()
        if not quotes:
            await ctx.send("❌ No quotes saved yet.")
            return

        count = len(quotes)
        await ctx.send(f"📜 Total saved quotes: **{count}**. Use `the!quote` to display a random quote.")

async def setup(bot):
    await bot.add_cog(Quote(bot))
