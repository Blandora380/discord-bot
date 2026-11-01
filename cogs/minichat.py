import asyncio, random
import discord
from discord.ext import commands
import botchat
import mathcalc

MAX_MSG = 150

class MiniChat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    @commands.command(name="chat")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def chat(self, ctx, *, message: str = ""):
        ref = ctx.message.to_reference(fail_if_not_exists=False)
        quiet = discord.AllowedMentions.none()
        if not message:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send("Say something after the command.", reference=ref, allowed_mentions=quiet)
        if len(message) > MAX_MSG:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"Too long ({len(message)}/{MAX_MSG} characters).",
                reference=ref,
                allowed_mentions=quiet,
            )

        answer = mathcalc.calc(message)
        if answer is not None:
            async with ctx.typing():
                await asyncio.sleep(random.uniform(1.0, 1.8))
            words = answer.split(" ")
            msg = await ctx.send(
                words[0] + (" ▌" if len(words) > 1 else ""),
                reference=ref,
                allowed_mentions=quiet,
            )
            for i in range(1, len(words)):
                await asyncio.sleep(random.uniform(0.6, 0.9))
                part = " ".join(words[: i + 1])
                await msg.edit(
                    content=part + (" ▌" if i < len(words) - 1 else ""),
                    allowed_mentions=quiet,
                )
            return

        msg = await ctx.send("▌", reference=ref, allowed_mentions=quiet)
        buf = {"text": ""}

        def run():
            for t in botchat.stream(message):
                buf["text"] = t

        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(run))
            last = ""
            while not task.done():
                await asyncio.sleep(1.0)
                t = buf["text"]
                if t and t != last:
                    await msg.edit(content=t[:1990] + " ▌", allowed_mentions=quiet)
                    last = t
            await task
        await msg.edit(content=(buf["text"] or "...")[:2000], allowed_mentions=quiet)

async def setup(bot):
    await bot.add_cog(MiniChat(bot))