# Invite link and permissions

## Link

```
https://discord.com/oauth2/authorize?client_id=1533399924362707056
```

`client_id` is the bot's application ID (from the startup log: `Logged in as the 2#6074 (ID: 1533399924362707056)`).

## Requested permissions

`permissions=277062470720`, which is exactly this set — nothing more:

| Bit value | Permission | Why it is needed |
|---:|---|---|
| 64 | Add Reactions | passive auto-reactions (controlled by `/the-settings passive`) |
| 1024 | View Channels | read the channels it operates in |
| 2048 | Send Messages | reply to commands |
| 274877906944 | Send Messages in Threads | reply inside threads |
| 16384 | Embed Links | command embeds (rank cards, leaderboards) |
| 32768 | Attach Files | send rendered cards and downloaded media |
| 65536 | Read Message History | `the!summarize` and `the!roast` read recent messages |
| 262144 | Use External Emojis | custom emoji in replies (gacha, bestgirl) |
| 2147483648 | Use Application Commands | slash commands |
| 1048576 | Connect | voice features (`/play`, `/the-join`, `/playpigeon`) |
| 2097152 | Speak | voice audio playback |
| 33554432 | Use Voice Activity | voice features |

**Not requested, and deliberately so:** Administrator, Manage Server, Manage Roles,
Manage Channels, Manage Messages, Manage Webhooks, Manage Nicknames, Kick, Ban,
Moderate Members, Move Members, Mute Members, Deafen Members, Mention @everyone,
Mention @here, Mention All Roles.
