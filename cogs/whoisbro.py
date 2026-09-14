import discord
from discord.ext import commands

class WhoIsBro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if "who is bro" in message.content.lower():
            await message.channel.send("no it's me guys")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot:
            return

        # Cuma balas kalau sebelumnya belum mengandung "who is bro"
        # lalu setelah diedit menjadi mengandung "who is bro"
        if (
            "who is bro" not in before.content.lower()
            and "who is bro" in after.content.lower()
        ):
            await after.channel.send("no it's me guys")

async def setup(bot):
    await bot.add_cog(WhoIsBro(bot))