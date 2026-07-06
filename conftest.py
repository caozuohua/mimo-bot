"""Test configuration - set env before bot.py import."""

import os

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token:fake")
os.environ.setdefault("ALLOWED_USERS", "")
