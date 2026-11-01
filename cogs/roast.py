import os
import time
import asyncio
import logging
import requests
import discord
from discord.ext import commands

from cogs.settings import ai_prefix_allowed

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.5-flash-lite"

log = logging.getLogger("roast")


def _call_gemini(prompt: str) -> str:
    """Simple one-shot Gemini call, returns the response text."""
    response = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMINI_API_KEY}",
        },
        json={
            "model": GEMINI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a savage, witty roast bot. "
                        "Write a short, funny roast (2–4 sentences max). "
                        "Keep it spicy but not actually hateful or discriminatory. "
                        "You can swear. Be creative and specific."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 200,
            "reasoning_effort": "low",
        },
        timeout=30,
    )

    if not response.ok:
        try:
            err = response.json()
        except ValueError:
            err = response.text[:300]
        raise RuntimeError(f"Gemini API {response.status_code}: {err}")

    return response.json()["choices"][0]["message"]["content"].strip()


class Roast(commands.Cog):
    # Rule 7: this calls a paid Gemini API and posts publicly, so it needs a
    # per-user cooldown. Checked inside handle_roast because the command has two
    # entry points (the registered command and the raw listener fallback) and a
    # decorator would only cover the first.
    COOLDOWN_S = 10.0

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_use: dict[int, float] = {}

    def _rate_limited(self, user_id: int) -> bool:
        now = time.monotonic()
        if now - self._last_use.get(user_id, 0.0) < self.COOLDOWN_S:
            return True
        self._last_use[user_id] = now
        return False

    async def handle_roast(
        self,
        channel,
        target: discord.User | discord.Member,
        invoker: discord.User | discord.Member,
    ):
        # Rule 3: AI features and text commands can each be switched off by an
        # admin, and handle_roast is reached from both a registered prefix
        # command and a raw listener, so the check lives here.
        guild = getattr(channel, "guild", None)
        if not ai_prefix_allowed(guild):
            await channel.send(
                "⚠️ AI features or text commands are switched off in this server."
            )
            return

        if self._rate_limited(invoker.id):
            await channel.send(
                f"⏳ {invoker.mention} slow down — one roast every "
                f"{int(self.COOLDOWN_S)}s.",
                allowed_mentions=discord.AllowedMentions(users=True),
            )
            return

        history_lines = []
        try:
            async for msg in channel.history(limit=50):
                if msg.author.id == target.id and msg.content:
                    history_lines.append(msg.content)
                    if len(history_lines) >= 10:
                        break
        except Exception:
            pass

        display_name = target.display_name

        if history_lines:
            context = "\n".join(reversed(history_lines))
            prompt = (
                f"Roast the Discord user named \"{display_name}\" based on what they've been "
                f"saying in chat recently:\n\n{context}\n\n"
                f"Make the roast personal and reference what they said if possible."
            )
        else:
            prompt = f"Roast the Discord user named \"{display_name}\". Be creative."

        thinking_msg = await channel.send(f"🔥 cooking up a roast for {target.mention}...")

        try:
            roast_text = await asyncio.get_event_loop().run_in_executor(
                None, _call_gemini, prompt
            )
            await thinking_msg.edit(content=f"🔥 {target.mention} {roast_text}")
        except Exception:
            # Exception text can contain upstream error bodies — never show it
            # in the channel (rule 11).
            log.exception("roast failed")
            await thinking_msg.edit(content="⚠️ Failed to roast. Please try again.")

    @commands.command(name="roast", help="Roast a user with AI")
    async def roast_prefix(self, ctx: commands.Context, target: discord.Member = None):
        if target is None:
            if ctx.message.mentions:
                target = ctx.message.mentions[0]
            else:
                await ctx.send("❌ Ping someone to roast! Usage: `the!roast @user`")
                return
        await self.handle_roast(ctx.channel, target, ctx.author)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not ai_prefix_allowed(message.guild):  # rule 3
            return

        if not message.content.lower().startswith("the!roast"):
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        if not message.mentions:
            await message.channel.send("❌ Ping someone to roast! Usage: `the!roast @user`")
            return

        target = message.mentions[0]
        await self.handle_roast(message.channel, target, message.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roast(bot))
