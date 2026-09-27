import html
import random
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

FALLBACK_QUESTIONS = [
    {
        "question": "Which programming language was created by Guido van Rossum?",
        "correct": "Python",
        "incorrect": ["Java", "C++", "Ruby"]
    },
    {
        "question": "What is the capital of Japan?",
        "correct": "Tokyo",
        "incorrect": ["Kyoto", "Osaka", "Hiroshima"]
    },
    {
        "question": "Which protocol is used to securely browse websites?",
        "correct": "HTTPS",
        "incorrect": ["FTP", "HTTP", "SMTP"]
    },
    {
        "question": "What does API stand for in software development?",
        "correct": "Application Programming Interface",
        "incorrect": ["Advanced Program Integration", "Automated Protocol Interaction", "Application Process Integration"]
    },
    {
        "question": "Which planet in our solar system is known as the Red Planet?",
        "correct": "Mars",
        "incorrect": ["Venus", "Jupiter", "Saturn"]
    }
]

class TriviaView(discord.ui.View):
    def __init__(self, correct_answer: str, all_options: list[str]):
        super().__init__(timeout=20.0)
        self.correct_answer = correct_answer
        self.answered = False
        self.winner = None

        for idx, option in enumerate(all_options):
            label = f"{['A', 'B', 'C', 'D'][idx]}: {option}"
            if len(label) > 80:
                label = label[:77] + "..."

            button = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.secondary,
                custom_id=f"trivia_{idx}"
            )
            button.option_value = option
            button.callback = self.create_callback(option, button)
            self.add_item(button)

    def create_callback(self, clicked_option: str, clicked_button: discord.ui.Button):
        async def callback(interaction: discord.Interaction):
            if self.answered:
                await interaction.response.send_message("❌ This trivia question has already been answered!", ephemeral=True)
                return

            self.answered = True
            self.winner = interaction.user

            is_correct = (clicked_option == self.correct_answer)

            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    if getattr(child, "option_value", None) == self.correct_answer:
                        child.style = discord.ButtonStyle.success
                    elif child == clicked_button and not is_correct:
                        child.style = discord.ButtonStyle.danger
                    else:
                        child.style = discord.ButtonStyle.secondary

            color = discord.Color.green() if is_correct else discord.Color.red()
            if is_correct:
                result_text = f"🎉 **{interaction.user.display_name}** got it right! The answer was **{self.correct_answer}**."
            else:
                result_text = f"❌ **{interaction.user.display_name}** guessed wrong! The correct answer was **{self.correct_answer}**."

            embed = interaction.message.embeds[0]
            embed.color = color
            embed.add_field(name="Result", value=result_text, inline=False)

            await interaction.response.edit_message(embed=embed, view=self)
            self.stop()

        return callback

class Trivia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _fetch_question(self) -> dict:
        url = "https://opentdb.com/api.php?amount=1&type=multiple"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("results"):
                            q_data = data["results"][0]
                            question = html.unescape(q_data["question"])
                            correct = html.unescape(q_data["correct_answer"])
                            incorrect = [html.unescape(ans) for ans in q_data["incorrect_answers"]]
                            return {
                                "question": question,
                                "correct": correct,
                                "incorrect": incorrect
                            }
        except Exception:
            pass

        q = random.choice(FALLBACK_QUESTIONS)
        return q

    async def _start_trivia(self, destination, author):
        q_data = await self._fetch_question()
        question = q_data["question"]
        correct = q_data["correct"]
        options = q_data["incorrect"] + [correct]
        random.shuffle(options)

        embed = discord.Embed(
            title="🧠 Trivia Challenge",
            description=f"**{question}**",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"Requested by {author.display_name} • You have 20 seconds to answer!")

        view = TriviaView(correct, options)
        message = await destination.send(embed=embed, view=view)

        await view.wait()

        if not view.answered:
            view.answered = True
            for child in view.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
                    if getattr(child, "option_value", None) == correct:
                        child.style = discord.ButtonStyle.success

            embed.color = discord.Color.orange()
            embed.add_field(name="Result", value=f"⏰ **Time's up!** Nobody answered in time. The correct answer was **{correct}**.", inline=False)
            try:
                await message.edit(embed=embed, view=view)
            except Exception:
                pass

    @app_commands.command(name="trivia", description="Play a quick interactive trivia game!")
    async def slash_trivia(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self._start_trivia(interaction.channel, interaction.user)
        await interaction.followup.send("🎮 Trivia started!", ephemeral=True)

    @commands.command(name="thetrivia")
    async def text_trivia(self, ctx: commands.Context):
        """Text command version: !thetrivia"""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await self._start_trivia(ctx.channel, ctx.author)

async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))
