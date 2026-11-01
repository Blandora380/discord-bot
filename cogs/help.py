import discord
from discord import app_commands
from discord.ext import commands

from cogs.settings import prefix_allowed

HELP_TEXT = (
    "**📋 Command List**\n"
    "\n"
    "**Prefix commands (`the!`)**\n"
    "• `the!cmds` — help\n"
    "• `the!online` — check how long the bot has been on\n"
    "• `the!come` — bot join your joined voice channel\n"
    "• `the!playpigeon` — bot join a voice channel and plays pigeon.mp3\n"
    "• `the!pigeon` — pigeon\n"
    "• `the!play <song title or link>` — play songs from YouTube\n"
    "• `the!ipgrabber <user>` — grab ip\n"
    "• `the!roast <@user>` — roast someone with AI\n"
    "• `the!gacha [1|10]` — Project Sekai card gacha simulator\n"
    "• `the!card <name|id>` — search and view Project Sekai cards\n"
    "• `the!yaoi` — 👀👀👀\n"
    "• `the!dm <user> <message>` — dm anyone\n"
    "• `the!rank` / `the!top` — levels\n"
    "• `the!remind <time> <text>` — set a reminder\n"
    "**Slash commands (`/`)**\n"
    "• `/the-help`\n"
    "• `/the-uptime`\n"
    "• `/the-join`\n"
    "• `/playpigeon`\n"
    "• `/play query:<title/link>`\n"
    "• `/gacha`\n"
    "• `/card query:<name|id>`\n"
    "• `/yaoi`\n"
    "• `/dm user:<user> message:<message>`\n"
)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not prefix_allowed(message.guild):  # rule 3
            return

        if message.content.strip() != "the!cmds":
            return

        await message.channel.send(HELP_TEXT)

    @app_commands.command(name="the-help", description="help")
    async def help_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(HELP_TEXT)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
