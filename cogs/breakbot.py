from discord.ext import commands

ROLE_ID = 1517782104531009607

class BreakBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def breakbot(self, ctx, option=None):
        # Cek role
        if not any(role.id == ROLE_ID for role in ctx.author.roles):
            await ctx.send("❌ You don't have permission to use this command.")
            return

        if option is None:
            await ctx.send(
                "⚠️ **Are you sure?**\n\n"
                "If yes, type `!breakbot yes`\n"
                "If no, type `!breakbot no`"
            )
            return

        option = option.lower()

        if option == "yes":
            await ctx.send(
                "🚨 **BOT BREAKING WARNING!!!** 🚨\n"
                "Emergency shutdown confirmed.\n"
                "The bot is now shutting down..."
            )

            await self.bot.close()

        elif option == "no":
            await ctx.send("✅ Shutdown cancelled.")

        else:
            await ctx.send(
                "❌ Invalid option.\n"
                "Use `!breakbot yes` or `!breakbot no`."
            )

async def setup(bot):
    await bot.add_cog(BreakBot(bot))