import asyncio
import discord
from discord.ext import commands

PREFIX = "+"
SELF_DESTRUCT_PREFIX = "-"

# Ganti dengan ID channel tujuan (klik kanan channel -> Copy Channel ID)
TARGET_CHANNEL_ID = 1511402934825521173


class Forward(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # HANYA jalan kalau ini DM (bukan pesan di server)
        if not isinstance(message.channel, discord.DMChannel):
            return

        if message.content.startswith(SELF_DESTRUCT_PREFIX):
            prefix = SELF_DESTRUCT_PREFIX
            self_destruct = True
        elif message.content.startswith(PREFIX):
            prefix = PREFIX
            self_destruct = False
        else:
            return

        # strip the prefix and leading space, e.g. "+ halo" -> "halo"
        text_to_send = message.content[len(prefix):].strip()

        if not text_to_send:
            return

        target_channel = self.bot.get_channel(TARGET_CHANNEL_ID)
        if target_channel is None:
            return

        sent = await target_channel.send(text_to_send)

        if self_destruct:
            await asyncio.sleep(0.1)
            try:
                await sent.delete()
            except discord.HTTPException:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Forward(bot))