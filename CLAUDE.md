# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- **Run Bot:** `python bot.py` or `./start.sh` (installs Deno and starts `python bot.py`)
- **Install Dependencies:** `pip install -r requirements.txt`

## Architecture & Big Picture

This is a modular Discord bot built with `discord.py`.

- **Entry Point (`bot.py`):**
  - Initializes the bot with `discord.ext.commands.Bot`, enforcing IPv4 connections (`aiohttp.TCPConnector(family=socket.AF_INET)`).
  - Dynamically discovers and loads all non-underscore Python modules from the `cogs/` directory.
  - Runs a background task (`watch_cogs_for_changes()`) that continuously polls `cogs/` files to automatically load new cogs, reload modified cogs, and unload deleted cogs on the fly without manual restarts.

- **Cogs (`cogs/`):**
  - Modular command extensions handling features such as slash commands, audio streaming/music (`yt-dlp`), AI integration (`google-genai`), utilities, fun commands, and messaging hooks.

- **Helpers, Services & Database (`helpers/`, `services/`, `database/`):**
  - `helpers/`: UI views, autocomplete providers, embeds, image processing, logging, text command utilities, and timezones.
  - `services/`: Business logic and external service wrappers (leaderboards, graph generation, media clipping, data handling).
  - `database/`: Database connection pooling and query management.

- **Scripts & Deployment (`scripts/`, `nixpacks.toml`, `start.sh`):**
  - Setup scripts for database initialization and emoji uploads.
  - Deployment configured via Nixpacks (`nixpacks.toml`) and startup script (`start.sh`) installing Deno and running the Python bot.
