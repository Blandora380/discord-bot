import discord
from discord.ext import commands


class Ping(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # `pong`, not `ping` — Shigure Ui already owns `ping` (rule 4a).
    @commands.command(name="pong")
    async def ping(self, ctx: commands.Context):
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! `{latency_ms}ms`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
