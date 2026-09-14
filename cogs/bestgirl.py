import discord
from discord.ext import commands
import random

class Pjsk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bestgirl")
    async def pjsk(self, ctx):
        """Randomly selects the best girl from Project SEKAI."""
        best_girls = [
            "Airiiii <:airilike:1515685884626862090>",
            "Minori <a:MinoriHeartPulse:1515620058729156660>",
            "Hoshino Ruby <:RubyWat:1519024054713979021>",
            "Shizuku <:shizukubelike:1511411707061342472>",
            "Mafuyu <:MafuyuWhat:1514686923808051344>",
            "Ema <:ema_nya:1511411973697310731>",
            "Rin <:aoi_kyun:1522167891871400057>",
            "Luka",
            "Airi <:airilike:1515685884626862090>",
            "Shiho",
            "Mizuki <:MizukiVibin:1518337239342645258>",
            "Yuzu <:YuzuConfused:1519059056248094890>",
            "Chinatsu <:ChinatsuShock:1522167900323057685>",
            "Arisu <:ArisuNom:1522167902940303421>",
            "Rio <:RioDoubt:1522167905146507304>",
            "Ako",
            "Toyama Kasumi",
            "Hanamaki Tsukasa",
            "Yuki Seto",
            "Hoshino Ichika"
        ]

        best_girl = random.choice(best_girls)
        await ctx.send(f"**The best girl from Project SEKAI is...** {best_girl} <a:10173pinkpixelheart:1519414181185720511>")

async def setup(bot):
    await bot.add_cog(Pjsk(bot))