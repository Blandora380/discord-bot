import discord
from discord.ext import commands

class ExampleSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="gay",
                value="first-option",
                description="twink, bara, daddy, bear"
            ),
            discord.SelectOption(
                label="lesbian",
                value="second-option",
                description="curvy, milf, athletic"
            ),
        ]
        super().__init__(
            placeholder="which porn",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        if self.values[0] == "first-option":
            await interaction.response.send_message(
                f"{user.mention} gay? ok check dms 🤤🤤🤤"
            )
        elif self.values[0] == "second-option":
            await interaction.response.send_message(
                f"{user.mention} lesbian? ok check dms 🤤🤤🤤"
            )


class ExampleView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ExampleSelect())


# Example command to trigger it
class ExampleCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="porn")
    async def example(self, ctx):
        await ctx.send("Pick one:", view=ExampleView())


async def setup(bot):
    await bot.add_cog(ExampleCog(bot))