# the — Discord Bot

A feature-rich Discord bot with AI chat, music playback, Project Sekai gacha simulation, leveling system, and more.

## Features

### AI Chat (`cogs/ai.py`)
- **Model**: Google Gemini 3.5 Flash Lite via OpenAI-compatible endpoint
- **Commands**: `the!ai <question>`, `the!resetai`, `the!model`
- **Auto-reply**: Replies in configured channel (set via `/the-settings ai`)
- **Tools**: Web search (Tavily), file creation, image generation (Cloudflare FLUX.2), text-to-speech (ElevenLabs)
- **Context**: Remembers last 4 turns per user, includes recent channel history
- **Safety**: NSFW/harmful content refusal with regex backstop

### Music (`cogs/play.py`, `cogs/playpigeon.py`)
- **Source**: YouTube via `yt-dlp`
- **Commands**: `the!play <title|url>`, `the!playpigeon` (plays pigeon.mp3)
- **Voice**: Joins user's voice channel, auto-leaves when queue ends

### Project Sekai (`cogs/gacha.py`, `cogs/card.py`, `cogs/pjsk.py`)
- **Gacha**: `the!gacha [1|10]` — simulates card pulls with rarity rates
- **Card search**: `the!card <name|id>` — view card details and images
- **Data**: Local card database with character/unit info

### Leveling (`cogs/leveling.py`)
- **XP**: Gains XP from messages (cooldown-protected)
- **Commands**: `the!rank`, `the!top` — rank cards with rendered images
- **Roles**: Auto-assigns level roles (configurable via settings)

### Utilities
| Command | Description |
|---------|-------------|
| `the!cmds` | Show help |
| `the!online` / `/the-uptime` | Bot uptime |
| `the!come` / `/the-join` | Join voice channel |
| `the!pigeon` | Pigeon 🕊️ |
| `the!ipgrabber <user>` | Grab IP (joke) |
| `the!roast <@user>` | AI roast |
| `the!yaoi` | 👀 |
| `the!dm <user> <msg>` | DM someone |
| `the!remind <time> <text>` | Set reminder |
| `the!summarize` | Summarize recent messages |
| `the!quote` | Save/display quotes |
| `the!shitreact` | Auto-react to messages |
| `the!think` | Thinking animation |
| `the!whoisbro <user>` | User info |
| `the!bestgirl` | Best girl vote |
| `the!forward` | Forward messages |
| `the!download` | Download media |
| `the!listemojis` | List server emojis |
| `the!ping` | Latency check |
| `the!restartbot` | Restart bot (owner only) |

### Settings (`cogs/settings.py`, `cogs/slash.py`)
- `/the-settings` — Admin panel for:
  - AI channel toggle
  - Prefix commands toggle
  - Level role configuration
  - Welcome/leave messages

## Architecture

```
bot.py                 # Entry point, auto-discovers cogs/, hot-reloads on file change
botchat.py             # Local GPT model (standalone, not used by main bot)
cogs/                  # 28 feature modules (auto-loaded)
helpers/
  └── prefix.py        # Shared "the!" prefix & mention policy
services/              # External service wrappers
database/              # SQLite databases (levels, reminders, quotes, etc.)
data/                  # Static assets (card images, audio, etc.)
assets/                # Fonts, images for rank cards
```

### Key Design Rules (from code comments)
1. **Unique prefix**: `the!`
2. **No unwanted pings**: `@everyone`/`@here`/role mentions blocked globally
3. **Admin control**: Prefix commands & AI features toggleable per-server
4. **Slash commands exempt** from prefix toggle (controlled via Discord Integrations)
5. **Hot-reload**: Cogs auto-reload on file change; new cogs auto-load
6. **Command sync debounce**: 5-minute cooldown on `tree.sync()` to respect Discord quota
7. **Error handling**: User-facing messages are friendly; full traces logged only
8. **IPv4 forced**: All connections use IPv4 to avoid WiFi IPv6 issues
9. **Minimal permissions**: Invite requests only 10 specific permissions (see `INVITE.md`)
10. **Safety gates**: AI refuses NSFW/harmful content at prompt & generation level

## Requirements
- Python 3.10+
- `discord.py`, `requests`, `PyNaCl`, `yt-dlp`, `yt-dlp-ejs`, `python-dotenv`, `google-genai`, `pykakasi`, `rapidfuzz`, `PyYAML`, `numpy`, `Pillow`, `davey`
- FFmpeg (for voice playback)
- API keys in `.env` (see `.env.example` below)

## Setup

```bash
# Clone
git clone <repo-url>
cd bot

# Create .env with your tokens
cp .env.example .env
# Edit .env with your keys

# Install dependencies
pip install -r requirements.txt
# Also need system packages: ffmpeg, libopus

# Run
python bot.py
```

### Required `.env` keys
```env
DISCORD_TOKEN=your_bot_token
GEMINI_API_KEY=...
TAVILY_API_KEY=...          # web search (optional)
CLOUDFLARE_API_TOKEN=...    # image generation
CLOUDFLARE_ACCOUNT_ID=...
ELEVENLABS_API_KEY=...      # TTS (optional)
# Other optional keys: MISTRAL, HF, NVIDIA, DEEPSEEK, POLLINATIONS, OPENROUTER, etc.
```

### Invite the bot
Use the link in `INVITE.md` — requests minimal permissions (no Administrator, no message management).

## Development

### Adding a cog
1. Create `cogs/your_feature.py` with a `setup(bot)` async function
2. Bot auto-loads it on next file-change poll (or restart)

### Hot-reload
Edit any `cogs/*.py` — changes apply within ~2 seconds (no restart needed).

### Project structure conventions
- Listener-style commands (e.g., `the!cmds`) check `prefix_allowed(guild)` first
- Slash commands use `@app_commands.command(name="the-...")`
- Shared constants in `helpers/` to prevent drift
- Database access via `services/database.py` helpers
