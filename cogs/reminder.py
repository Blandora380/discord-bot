import re
import asyncio
import discord
from discord.ext import commands

DURATION_RE = re.compile(
    r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", re.IGNORECASE
)

MAX_SECONDS = 30 * 86400  # cap at 30 days max


def parse_duration(text: str) -> int | None:
    """Parse a string like '1d2h30m' or '45s' into total seconds.
    Returns None if the format is invalid / has no numbers at all."""
    match = DURATION_RE.fullmatch(text.strip())
    if not match or not any(match.groups()):
        return None

    days, hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_duration(total_seconds: int) -> str:
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts)


class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="reminder")
    @commands.cooldown(1, 30, commands.BucketType.user)  # 1 use per 30s per user
    async def reminder(
        self,
        ctx: commands.Context,
        duration: str = None,
        *,
        message: str = None,
    ):
        if not duration or not message:
            await ctx.send(
                "❌ Usage: `!reminder <duration> <message>`\n"
                "Example: `!reminder 30m drink water`"
            )
            return

        total_seconds = parse_duration(duration)

        if total_seconds is None or total_seconds <= 0:
            await ctx.send(
                "❌ Invalid duration. Use a format like `30m`, `2h`, `1d`, or combined like `1d2h30m`."
            )
            return

        if total_seconds > MAX_SECONDS:
            await ctx.send("❌ The maximum reminder duration is 30 days.")
            return

        await ctx.send(
            f"⏰ Got it, I'll remind you in **{format_duration(total_seconds)}**: {message}"
        )

        async def send_reminder():
            await asyncio.sleep(total_seconds)
            try:
                await ctx.send(f"⏰ {ctx.author.mention} reminder: {message}")
            except discord.HTTPException:
                pass

        # fire-and-forget: if the bot restarts/reloads before the timer is
        # up, this reminder is lost (in-memory only, not persistent)
        self.bot.loop.create_task(send_reminder())

    @reminder.error
    async def reminder_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Slow down — try again in {error.retry_after:.1f}s."
            )
        else:
            await ctx.send(f"⚠️ Error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
