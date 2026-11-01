import discord
from discord.ext import commands

from cogs.settings import prefix_allowed

# Ganti teks ini sesuai yang mau dikirim
MESSAGE_TEXT = """aa! mitsukechatta?
nani ka okashii koto!
furafurafura aruite
sugiteku jikan wa
moto ni wa modoranai ne
dandan to nemuku natte
wasurete shimau
jaa! nanzenkai mo omoidasou
wasurechau mae ni
isso dou ni demo nare
jikan ga sugiteku ochiteku

aa ikitomatta
itsu ka sayonara ne
guwaguwaguwa kishinde
nani ka ochita oto
kowarete kietetta yo
saigo no omoide o
mou omoidasenai
mou sanzan furimaita
watashi no shiawase
mou sukuenai kurai
wasurete shimaeba ii no ni

suupaa omoidase taimu
shiranuma ni nani ka ushinattemasen ka
maa ushinatta koto ni sura kizukanai yo ne
tabun
kizukanai koto ni kizukenai mama
datta yo ne
minna ga omoide omoidasu taimu

ne
kore wa sou iu sekai da kara
nankai mo omoide o sore o wasurenai you ni
itsu ka naku naru nara!
aruite kaeroo
kono geemu mo owaru
sono toki egao de ireru you ni
sou! watashi ga ita koto wa
koko ni sonzai shite iru!
baka dekai umi o mitara
mou shineru ne!"""

# Path ke file gambar & audio (taruh file-nya di folder assets/, di sebelah bot.py)
IMAGE_PATH = "assets/pigeon.png"
AUDIO_PATH = "assets/pigeon.mp3"


class Pigeon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild):  # rule 3
            return

        if message.content != "the!pigeon":
            return

        files = [
            discord.File(IMAGE_PATH),
            discord.File(AUDIO_PATH),
        ]

        await message.channel.send(content=MESSAGE_TEXT, files=files)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pigeon(bot))
