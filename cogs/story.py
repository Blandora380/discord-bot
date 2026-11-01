import asyncio
from discord.ext import commands
import storygen

MAX_PROMPT = 128

class Story(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.lock = asyncio.Lock()

    @commands.hybrid_command(name="story", description="Write a tiny story")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def story(self, ctx, *, prompt: str = ""):
        if len(prompt) > MAX_PROMPT:
            ctx.command.reset_cooldown(ctx)
            return await ctx.send(
                f"Prompt too long ({len(prompt)}/{MAX_PROMPT} characters).",
                ephemeral=True,
            )
        await ctx.defer()
        await ctx.defer()
        msg = await ctx.send("✍️ ...")
        buf = [prompt if prompt else ""]

        def run():
            for chunk in storygen.stream_story(prompt):
                buf.append(chunk)

        async with self.lock:
            task = asyncio.create_task(asyncio.to_thread(run))
            last = ""
            while not task.done():
                await asyncio.sleep(1)
                text = "".join(buf)
                if text != last:
                    await msg.edit(content=text[:1990] + " ▌")
                    last = text
            await task
        await msg.edit(content="".join(buf).strip()[:2000])

async def setup(bot):
    await bot.add_cog(Story(bot))
