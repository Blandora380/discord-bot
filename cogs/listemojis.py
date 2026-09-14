import discord
from discord.ext import commands


class ListEmojis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="listemojis")
    async def listemojis(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send("❌ This command only works in a server.")
            return

        emojis = ctx.guild.emojis
        if not emojis:
            await ctx.send("Server ini gak punya custom emoji.")
            return

        lines = [f"`{e.name}` {'(animated)' if e.animated else ''}" for e in emojis]
        text = f"**{len(emojis)} custom emoji di server ini:**\n" + "\n".join(lines)

        # Discord message limit 2000 char, potong kalo kepanjangan
        if len(text) > 1900:
            text = text[:1900] + "\n...[truncated]"

        await ctx.send(text)


async def setup(bot: commands.Bot):
    await bot.add_cog(ListEmojis(bot))
