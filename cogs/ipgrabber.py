import discord
from discord.ext import commands

FAKE_IP = "147.235.192.41"


class IPGrabber(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if "!ipgrabber" not in message.content:
            return

        if message.mentions:
            target = message.mentions[0]
            await message.channel.send(f"{target.mention}'s ip grabbed: {FAKE_IP}")
        else:
            await message.channel.send(f"ip grabbed: {FAKE_IP}")


async def setup(bot: commands.Bot):
    await bot.add_cog(IPGrabber(bot))
