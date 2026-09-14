import discord
from discord.ext import commands


class NitroView(discord.ui.View):
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary)
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "https://i.imgur.com/yed5Zfk.gif",
            ephemeral=True
        )


class FreeNitro(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def freenitro(self, ctx):
        await ctx.send(
            "omg free nitro click this button for free nitro!!!1!!1!",
            view=NitroView()
        )


async def setup(bot):
    await bot.add_cog(FreeNitro(bot))