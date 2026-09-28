import discord
from discord import app_commands
from discord.ext import commands

HELP_TEXT = (
    "**📋 Command List**\n"
    "\n"
    "**Prefix commands (`!`)**\n"
    "• `!thehelp` — help\n"
    "• `!uptime` — check how long the boat has been on\n"
    "• `!join` — bot join your joined voice channel\n"
    "• `!playpigeon` — bot join a voice channel and plays pigeon.mp3\n"
    "• `!pigeon` — pigeon\n"
    "• `!play <song title or link>` — play songs from YouTube\n"
    "• `!ipgrabber <user>` — grab ip\n"
    "• `!imagine <prompt>` — imagine an image\n"
    "• `!breakbot` — don't.\n"
    "• `!roast <@user>` — roast someone with AI\n"
    "• `!gacha [1|10]` — Project Sekai card gacha simulator\n"
    "• `!card <name|id>` — search and view Project Sekai cards\n"
    "• `!searchopenverse <prompt>` — search images with openverse\n"
    "• `!yaoi` — 👀👀👀\n"
    "• `!dm <user> <message>` —  dm anyone\n"
    "• `!porn` —  gay or lesbian\n"
    "**Slash commands (`/`)**\n"
    "• `/uptime`\n"
    "• `/join`\n"
    "• `/playpigeon`\n"
    "• `/play query:<title/link>`\n"
    "• `/gacha`\n"
    "• `/card query:<name|id>`\n"
    "• `/help`\n"
    "• `/yaoi`\n"
    "• `/dm user:<user> message:<message>` \n"
)


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.content.strip() != "!thehelp":
            return

        await message.channel.send(HELP_TEXT)

    @app_commands.command(name="help", description="help")
    async def help_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(HELP_TEXT)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
