"""Shared command prefix and mention policy.

Kept in its own module because two different places need the same value:
`bot.py` passes it to `commands.Bot(...)`, while the listener-style commands
(`the!cmds`, `the!play`, ...) compare against `message.content` as a raw
string. Sharing one constant stops the two from drifting apart.

Rule 5 — the prefix must be unique: not `ui!`, not a bare `!`, not `/`.
Rule 6 — @everyone / @here / role pings must be impossible even when a
          user's input or an AI reply contains them.
"""

from __future__ import annotations

import discord

COMMAND_PREFIX = "the!"

# Role/group mentions off entirely; user mentions stay on so commands that are
# genuinely about a member (`the!roast @user`) can still address them.
ALLOWED_MENTIONS = discord.AllowedMentions(everyone=False, roles=False, users=True)
