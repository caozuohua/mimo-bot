# MiMo Telegram Bot

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-black.svg)](https://github.com/astral-sh/ruff)

Telegram Bot that bridges to [MiMo Code Agent](https://github.com/nicepkg/mimocode), enabling AI-powered coding assistance directly from Telegram.

[English](#features) · [中文](#功能特性)

## Features / 功能特性

- **Text conversation** — Send text messages, get MiMo Code Agent responses
- **Voice messages** — Send voice, auto-converted via ffmpeg + Google STT
- **Session persistence** — Conversation context maintained across messages
- **Web search** — `/search` command powered by DuckDuckGo
- **Access control** — Restrict bot usage to specific Telegram user IDs
- **Concurrency protection** — Per-user async lock prevents message interleaving
- **Graceful shutdown** — Handles SIGTERM/SIGINT for clean process termination
- **Resilience** — Auto-retry on MiMo timeout or failure, orphan process cleanup

## Architecture

```
Telegram  ──►  bot.py  ──►  MiMo CLI (subprocess)  ──►  Response  ──►  Telegram
                 │
                 ├── Voice: OGG → ffmpeg → WAV → Google STT → text
                 ├── Search: /search → DuckDuckGo API → results
                 └── Session: per-user session_id → MiMo -s flag
```

- **Single-file design**: `bot.py` (~390 lines)
- **No database**: state held in-memory per process (Telegram user_data)
- **Systemd service**: auto-restart on failure, security hardening

## Quick Start

### Prerequisites

- Python 3.10+
- [MiMo Code Agent](https://github.com/nicepkg/mimocode) installed at `~/.mimocode/bin/mimo`
- `ffmpeg` (for voice message support)

### 1. Clone

```bash
git clone https://github.com/caozuohua/mimo-bot.git
cd mimo-bot
```

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env and set TELEGRAM_BOT_TOKEN
```

Get your token from [@BotFather](https://t.me/BotFather).

### 4. Run

```bash
python bot.py
```

## Deployment

### systemd (recommended)

```bash
sudo cp mimo-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mimo-bot
sudo systemctl start mimo-bot
```

### Manage

```bash
sudo systemctl status mimo-bot     # Check status
sudo systemctl restart mimo-bot    # Restart
journalctl -u mimo-bot -f          # Follow logs
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram Bot API token from @BotFather |
| `MIMO_TIMEOUT` | No | `300` | MiMo execution timeout in seconds |
| `ALLOWED_USERS` | No | *(all)* | Comma-separated Telegram user IDs |
| `STT_LANGUAGE` | No | `zh-CN` | Google Speech Recognition language |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help message |
| `/clear` | Clear current session |
| `/status` | Show current session ID |
| `/ping` | Check if bot is online |
| `/version` | Show bot version |
| `/search <keywords>` | Search via DuckDuckGo |

## Development

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt pytest pytest-asyncio
```

### Lint & Format

```bash
ruff check .
ruff format .
```

### Test

```bash
pytest -v
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)
