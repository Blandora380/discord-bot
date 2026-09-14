import discord
from discord.ext import commands

DM_CHANNEL_ID = 1511402934825521174

class DM(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 10, commands.BucketType.user)
    @commands.command()
    async def dm(self, ctx, member: discord.Member, *, message: str):
        if ctx.channel.id != DM_CHANNEL_ID:
            await ctx.send(f"❌ Please use this command in <#{DM_CHANNEL_ID}>.")
            return

        try:
            await member.send(message)
            await ctx.send(f"Successfully sent a DM to {member.mention}.")
        except discord.Forbidden:
            await ctx.send("I couldn't send a DM to that user.")

    @dm.error
    async def dm_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ You're on cooldown. Try again in **{error.retry_after:.1f}s**."
            )

async def setup(bot):
    await bot.add_cog(DM(bot))