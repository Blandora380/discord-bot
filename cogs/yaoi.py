import discord
from discord.ext import commands

class Yaoi(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def yaoi(self, ctx):
        await ctx.send(f"{ctx.author.mention} check dms 🤤🤤🤤")

        try:
            files = [
                discord.File("assets/yaoi.jpg"),
                discord.File("assets/yaoi2.jpg"),
                # Tambah file lain di sini
            ]

            await ctx.author.send(
                content="check dms 🤤🤤🤤",
                files=files
            )

        except discord.Forbidden:
            await ctx.send("your dms are disabled fuck you")

async def setup(bot):
    await bot.add_cog(Yaoi(bot))