import discord
from discord.ext import commands

EMOJI = "<:shit:1518211501813534780>"

class ShitReact(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def react_if_needed(self, message):
        if message.author.bot:
            return

        if "shit" not in message.content.lower():
            return

        try:
            await message.add_reaction(discord.PartialEmoji.from_str(EMOJI))
        except discord.HTTPException:
            pass

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.react_if_needed(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        # Hanya react kalau sebelumnya belum mengandung "shit"
        if (
            "shit" not in before.content.lower()
            and "shit" in after.content.lower()
        ):
            await self.react_if_needed(after)

async def setup(bot):
    await bot.add_cog(ShitReact(bot))