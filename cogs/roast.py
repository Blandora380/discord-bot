import os
import asyncio
import requests
import discord
from discord.ext import commands

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.5-flash-lite"


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
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def handle_roast(self, channel, target: discord.User | discord.Member):
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
        except Exception as e:
            await thinking_msg.edit(content=f"⚠️ Failed to roast: {e}")

    @commands.command(name="roast", help="Roast a user with AI")
    async def roast_prefix(self, ctx: commands.Context, target: discord.Member = None):
        if target is None:
            if ctx.message.mentions:
                target = ctx.message.mentions[0]
            else:
                await ctx.send("❌ Ping someone to roast! Usage: `!roast @user`")
                return
        await self.handle_roast(ctx.channel, target)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.content.lower().startswith("!roast"):
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        if not message.mentions:
            await message.channel.send("❌ Ping someone to roast! Usage: `!roast @user`")
            return

        target = message.mentions[0]
        await self.handle_roast(message.channel, target)


async def setup(bot: commands.Bot):
    await bot.add_cog(Roast(bot))
