import discord
from discord.ext import commands


class Nickname(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="nickname")
    async def nickname(self, ctx: commands.Context, *, name: str = None):
        if ctx.guild is None:
            await ctx.send("❌ This command only works in a server.")
            return

        try:
            await ctx.guild.me.edit(nick=name)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to change my nickname here.")
            return
        except discord.HTTPException as e:
            await ctx.send(f"⚠️ Failed to change nickname: {e}")
            return

        if name:
            await ctx.send(f"✅ Nickname changed to **{name}**")
        else:
            await ctx.send("✅ Nickname reset to default.")

    @nickname.error
    async def nickname_error(self, ctx: commands.Context, error: Exception):
        await ctx.send(f"⚠️ Error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Nickname(bot))
