# MiMo Telegram Bot

Telegram Bot that bridges to [MiMo Code Agent](https://github.com/nicepkg/mimocode), enabling AI-powered coding assistance directly from Telegram.

## Features

- Text conversation with MiMo Code Agent
- Voice message support (Google STT)
- Session persistence across messages
- Per-user concurrency protection
- Auto-restart via systemd
- Access control via allowed user list

## Quick Start

### 1. Clone

```bash
git clone https://github.com/yourname/mimo-bot.git
cd mimo-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your Telegram Bot Token
```

Get your bot token from [@BotFather](https://t.me/BotFather).

### 4. Run

```bash
python bot.py
```

## systemd Deployment

```bash
# Install service
sudo cp mimo-bot.service /etc/systemd/system/
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable mimo-bot
sudo systemctl start mimo-bot

# Check status
sudo systemctl status mimo-bot

# View logs
journalctl -u mimo-bot -f
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | - | Telegram Bot API token |
| `MIMO_TIMEOUT` | No | `300` | MiMo execution timeout (seconds) |
| `ALLOWED_USERS` | No | - | Comma-separated Telegram user IDs (empty = allow all) |

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Show help message |
| `/clear` | Clear current session |
| `/status` | Show current session ID |

## License

MIT
