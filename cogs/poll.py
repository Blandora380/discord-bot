import re
import asyncio
from datetime import datetime, timedelta
import discord
from discord import app_commands
from discord.ext import commands

NUMBER_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

DURATION_RE = re.compile(
    r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", re.IGNORECASE
)

def parse_duration(text: str) -> int | None:
    match = DURATION_RE.fullmatch(text.strip())
    if not match or not any(match.groups()):
        return None

    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds

class Poll(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _create_poll(self, destination, author: discord.User | discord.Member, question: str, options: str = None, duration: str = None):
        if options:
            if "|" in options:
                choice_list = [opt.strip() for opt in options.split("|") if opt.strip()]
            else:
                choice_list = [opt.strip() for opt in options.split(",") if opt.strip()]
        else:
            choice_list = ["Yes", "No"]

        if len(choice_list) < 2:
            return "❌ A poll needs at least 2 options."

        if len(choice_list) > len(NUMBER_EMOJIS):
            return f"❌ You can have a maximum of {len(NUMBER_EMOJIS)} options."

        duration_seconds = None
        if duration:
            duration_seconds = parse_duration(duration)
            if not duration_seconds or duration_seconds <= 0:
                return "❌ Invalid duration format! Use e.g. `30s`, `5m`, `1h`, `2h30m`."
            if duration_seconds > 7 * 86400:
                return "❌ Poll duration cannot exceed 7 days."

        # Build embed
        embed = discord.Embed(
            title="📊 Poll",
            description=f"**{question}**",
            color=discord.Color.blurple()
        )

        footer_text = f"Poll created by {author.display_name}"
        unix_end = None
        if duration_seconds:
            import time
            unix_end = int(time.time() + duration_seconds)
            footer_text += f" • Ends: <t:{unix_end}:R>"
            embed.timestamp = discord.utils.utcnow() + timedelta(seconds=duration_seconds)

        embed.set_footer(text=footer_text, icon_url=author.display_avatar.url)

        description_lines = []
        for idx, option in enumerate(choice_list):
            description_lines.append(f"{NUMBER_EMOJIS[idx]} {option}")

        embed.add_field(name="Choices", value="\n".join(description_lines), inline=False)

        if duration_seconds and unix_end:
            embed.add_field(name="Status", value=f"⏳ Voting ends <t:{unix_end}:R>", inline=False)

        # Send message
        message = await destination.send(embed=embed)

        # Add reactions
        for idx in range(len(choice_list)):
            try:
                await message.add_reaction(NUMBER_EMOJIS[idx])
            except discord.HTTPException:
                pass

        # If duration is set, schedule tally task
        if duration_seconds:
            self.bot.loop.create_task(self._tally_poll(message.channel.id, message.id, choice_list, duration_seconds))

        return None

    @app_commands.command(name="poll", description="Create a timed poll with automatic winner announcement.")
    @app_commands.describe(
        question="The question for the poll",
        options="Comma or pipe-separated options (leave blank for Yes/No)",
        duration="Duration like 30s, 5m, 1h, 1d (leave blank for no timer)"
    )
    async def slash_poll(self, interaction: discord.Interaction, question: str, options: str = None, duration: str = None):
        await interaction.response.defer(thinking=True)

        if options:
            if "|" in options:
                choice_list = [opt.strip() for opt in options.split("|") if opt.strip()]
            else:
                choice_list = [opt.strip() for opt in options.split(",") if opt.strip()]
        else:
            choice_list = ["Yes", "No"]

        if len(choice_list) < 2:
            await interaction.followup.send("❌ A poll needs at least 2 options.", ephemeral=True)
            return

        if len(choice_list) > len(NUMBER_EMOJIS):
            await interaction.followup.send(f"❌ You can have a maximum of {len(NUMBER_EMOJIS)} options.", ephemeral=True)
            return

        duration_seconds = None
        if duration:
            duration_seconds = parse_duration(duration)
            if not duration_seconds or duration_seconds <= 0:
                await interaction.followup.send("❌ Invalid duration format! Use e.g. `30s`, `5m`, `1h`, `2h30m`.", ephemeral=True)
                return
            if duration_seconds > 7 * 86400:
                await interaction.followup.send("❌ Poll duration cannot exceed 7 days.", ephemeral=True)
                return

        embed = discord.Embed(
            title="📊 Poll",
            description=f"**{question}**",
            color=discord.Color.blurple()
        )

        footer_text = f"Poll created by {interaction.user.display_name}"
        unix_end = None
        if duration_seconds:
            import time
            unix_end = int(time.time() + duration_seconds)
            footer_text += f" • Ends: <t:{unix_end}:R>"
            embed.timestamp = discord.utils.utcnow() + timedelta(seconds=duration_seconds)

        embed.set_footer(text=footer_text, icon_url=interaction.user.display_avatar.url)

        description_lines = []
        for idx, option in enumerate(choice_list):
            description_lines.append(f"{NUMBER_EMOJIS[idx]} {option}")

        embed.add_field(name="Choices", value="\n".join(description_lines), inline=False)

        if duration_seconds and unix_end:
            embed.add_field(name="Status", value=f"⏳ Voting ends <t:{unix_end}:R>", inline=False)

        message = await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ Poll created!", ephemeral=True)

        for idx in range(len(choice_list)):
            try:
                await message.add_reaction(NUMBER_EMOJIS[idx])
            except discord.HTTPException:
                pass

        if duration_seconds:
            self.bot.loop.create_task(self._tally_poll(message.channel.id, message.id, choice_list, duration_seconds))

    @commands.command(name="poll")
    async def text_poll(self, ctx: commands.Context, *, content: str = None):
        """Create a poll using !poll Question | Option1, Option2 | 5m"""
        if not content:
            await ctx.send("❌ Usage: `!poll Question | Option1, Option2 | 5m` (or `!poll Question`)")
            return

        parts = [p.strip() for p in content.split("|")]
        question = parts[0]
        options = None
        duration = None

        if len(parts) >= 2:
            if parse_duration(parts[1]):
                duration = parts[1]
            else:
                options = parts[1]

        if len(parts) >= 3:
            duration = parts[2]

        err = await self._create_poll(ctx.channel, ctx.author, question, options, duration)
        if err:
            await ctx.send(err)
        else:
            try:
                await ctx.message.delete()
            except Exception:
                pass

    async def _tally_poll(self, channel_id: int, message_id: int, choice_list: list[str], duration_seconds: int):
        await asyncio.sleep(duration_seconds)

        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            message = await channel.fetch_message(message_id)
        except Exception:
            return

        votes = []
        for idx, option in enumerate(choice_list):
            emoji = NUMBER_EMOJIS[idx]
            count = 0
            for reaction in message.reactions:
                if str(reaction.emoji) == emoji:
                    count = max(0, reaction.count - 1)
                    break
            votes.append((option, count, emoji))

        max_votes = max(v[1] for v in votes) if votes else 0

        result_lines = []
        winners = []
        for option, count, emoji in votes:
            result_lines.append(f"{emoji} **{option}**: {count} vote(s)")
            if count == max_votes and max_votes > 0:
                winners.append(option)

        embed = message.embeds[0] if message.embeds else discord.Embed(title="📊 Poll Ended")
        embed.color = discord.Color.green()

        embed.clear_fields()
        embed.add_field(name="Choices & Results", value="\n".join(result_lines), inline=False)

        if max_votes == 0:
            winner_text = "🤝 No votes were cast!"
        elif len(winners) == 1:
            winner_text = f"🏆 **Winner:** {winners[0]} with {max_votes} vote(s)!"
        else:
            winner_text = f"🤝 **Tie:** {', '.join(winners)} with {max_votes} vote(s) each!"

        embed.add_field(name="Poll Results", value=winner_text, inline=False)

        try:
            await message.edit(embed=embed)
            await message.reply(f"📊 **Poll Ended!** {winner_text}")
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))
