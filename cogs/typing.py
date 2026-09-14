import asyncio
import discord
from discord.ext import commands

class TypingCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.typing_tasks = {}  # channel_id: asyncio.Task

    @commands.command(name="typing")
    @commands.is_owner()
    async def typing_start(self, ctx: commands.Context, channel_id: int):
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden):
                await ctx.send("Channel gak ketemu (bisa jadi DM yang belum pernah kebuka, atau bot gak punya akses).")
                return

        if channel_id in self.typing_tasks:
            await ctx.send("Bot udah typing di situ.")
            return

        async def typing_loop():
            try:
                while True:
                    async with channel.typing():
                        await asyncio.sleep(8)
            except asyncio.CancelledError:
                pass
            except discord.HTTPException:
                self.typing_tasks.pop(channel_id, None)

        task = self.bot.loop.create_task(typing_loop())
        self.typing_tasks[channel_id] = task
        await ctx.send(f"Mulai typing di `{channel_id}`.")

    @commands.command(name="typingstop")
    @commands.is_owner()
    async def typing_stop(self, ctx: commands.Context, channel_id: int):
        task = self.typing_tasks.pop(channel_id, None)
        if task is None:
            await ctx.send("Gak ada typing yang jalan di situ.")
            return

        task.cancel()
        await ctx.send(f"Stop typing di `{channel_id}`.")

async def setup(bot: commands.Bot):
    await bot.add_cog(TypingCog(bot))