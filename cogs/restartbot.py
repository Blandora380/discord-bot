import os
import sys
import discord
from discord.ext import commands


class RestartBot(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="restartbot")
    @commands.is_owner()
    async def restartbot(self, ctx: commands.Context):
        await ctx.send("🔄 Restarting bot...")
        await self.bot.close()
        # Re-exec the current Python process with the same args.
        # This replaces the running process in place, so Termux doesn't
        # need any external supervisor to bring it back up.
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @restartbot.error
    async def restartbot_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.NotOwner):
            await ctx.send("❌ Only the bot owner can use this command.")
        else:
            await ctx.send(f"⚠️ Error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(RestartBot(bot))
