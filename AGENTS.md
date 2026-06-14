# MiMo Telegram Bot - Agent Instructions

## Overview

Single-file Python Telegram bot that bridges to MiMo Code Agent for AI coding assistance.

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN`
3. Run:
   ```bash
   python bot.py
   ```

## Key Facts

- **Entry point**: `bot.py` (single file, ~245 lines)
- **Python version**: 3.10+ (required)
- **External dependencies**:
  - `ffmpeg` for voice message conversion (must be installed on system)
  - MiMo binary at `~/.mimocode/bin/mimo` (required)
- **Environment variables**:
  - `TELEGRAM_BOT_TOKEN` (required)
  - `MIMO_TIMEOUT` (default: 300 seconds)
  - `ALLOWED_USERS` (comma-separated Telegram user IDs)

## Development

### Linting
```bash
ruff check .
ruff format .
```
Configuration in `pyproject.toml` (line length 88, Python 3.10 target).

### Testing
No tests currently exist.

### Type Checking
No type checking configured.

## Deployment

Systemd service file provided: `mimo-bot.service`
```bash
sudo cp mimo-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mimo-bot
sudo systemctl start mimo-bot
```

## Architecture Notes

- Single-user concurrency protection via `asyncio.Lock` per user
- Voice messages: OGG → WAV via ffmpeg, then Google STT
- MiMo responses parsed as JSON lines, session persistence per user
- All user interactions in Chinese (help messages, error responses)
- Long replies truncated at 4000 characters

## Conventions

- No comments in code (follow existing style)
- Use `log.info()`/`log.error()` for logging
- Temporary files cleaned up in `finally` blocks
- All async functions use `asyncio.create_subprocess_exec` for subprocess calls