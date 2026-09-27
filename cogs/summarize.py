import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional

from cogs.ai import stream_gemini, GEMINI_MODEL

class Summarize(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _summarize_channel(self, channel: discord.abc.Messageable, limit: int = 50, invoking_msg_id: int = None) -> str:
        """Fetch recent messages and return a summary via Gemini, excluding the command invocation."""
        messages = []
        fetch_limit = min(limit + 5, 200)

        async for msg in channel.history(limit=fetch_limit, oldest_first=False):
            if invoking_msg_id and msg.id == invoking_msg_id:
                continue
            if msg.content and (msg.content.startswith("!summarize") or msg.content.startswith("/summarize")):
                continue
            if msg.author.id == self.bot.user.id and ("Summary" in msg.content or "Summarizing" in msg.content):
                continue

            author = msg.author.display_name
            content = msg.content
            if not content:
                content = f"[Message with {len(msg.attachments)} attachment(s) and {len(msg.embeds)} embed(s)]"
            messages.append(f"{author}: {content}")

            if len(messages) >= limit:
                break

        messages.reverse()

        if not messages:
            return "No messages found in the channel history to summarize."

        chat_log = "\n".join(messages)

        system_prompt = (
            "You are a helpful assistant that summarizes Discord chat conversations. "
            "Provide a concise summary of the key points, topics discussed, and any decisions or action items. "
            "Do not include every single detail; focus on the main ideas. "
            "Provide ONLY the summary text. Do not include any title, heading, introductory sentence, or fluff (like 'Here is a summary:')."
        )

        gemini_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please summarize the following Discord chat:\n\n{chat_log}"}
        ]

        full_text = ""
        try:
            for kind, payload in stream_gemini(gemini_messages, tools=None, max_tokens=1000):
                if kind == "content":
                    full_text = payload
            return full_text.strip() if full_text else "⚠️ No summary generated."
        except Exception as e:
            return f"⚠️ Failed to generate summary: {e}"

    @app_commands.command(name="summarize", description="Summarize recent messages in this channel.")
    @app_commands.describe(limit="Number of recent messages to summarize (default 50, max 200)")
    async def slash_summarize(self, interaction: discord.Interaction, limit: Optional[int] = 50):
        await interaction.response.defer(thinking=True)

        if limit is None or limit < 1:
            limit = 50
        if limit > 200:
            limit = 200

        summary = await self._summarize_channel(interaction.channel, limit)

        if len(summary) > 1900:
            chunks = [summary[i:i+1900] for i in range(0, len(summary), 1900)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await interaction.followup.send(f"**Summary (part {i+1}/{len(chunks)}):**\n{chunk}")
                else:
                    await interaction.followup.send(f"**Part {i+1}/{len(chunks)}:**\n{chunk}")
        else:
            await interaction.followup.send(summary)

    @commands.command(name="summarize")
    async def text_summarize(self, ctx: commands.Context, limit: Optional[int] = 50):
        """Text command version: !summarize [limit]"""
        if limit is None or limit < 1:
            limit = 50
        if limit > 200:
            limit = 200

        invoking_msg = ctx.message
        try:
            await invoking_msg.delete()
        except Exception:
            pass

        summary = await self._summarize_channel(ctx.channel, limit, invoking_msg_id=invoking_msg.id)

        if len(summary) > 1900:
            chunks = [summary[i:i+1900] for i in range(0, len(summary), 1900)]
            for i, chunk in enumerate(chunks):
                if i == 0:
                    await ctx.send(f"**Summary (part {i+1}/{len(chunks)}):**\n{chunk}")
                else:
                    await ctx.send(f"**Part {i+1}/{len(chunks)}:**\n{chunk}")
        else:
            await ctx.send(summary)

async def setup(bot: commands.Bot):
    await bot.add_cog(Summarize(bot))
