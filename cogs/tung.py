import discord
from discord.ext import commands


class Tung(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # cocokin kata "halo" berdiri sendiri (bukan bagian dari kata lain
        # kayak "halogen"), case-insensitive
        words = message.content.lower().split()
        if "tung" in words:
            reply = (
                "<@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982> <@1124791582172925982>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>\n"
                "<@1323673526619865152>"
            )
            await message.channel.send(reply)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tung(bot))
