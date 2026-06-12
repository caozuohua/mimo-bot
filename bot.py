#!/usr/bin/env python3
"""Telegram Bot that bridges to MiMo Code Agent."""

import asyncio
import json
import logging
import os
import sys
import tempfile
from collections import defaultdict

import speech_recognition as sr
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("FATAL: TELEGRAM_BOT_TOKEN environment variable not set")

MIMO_BIN = os.path.expanduser("~/.mimocode/bin/mimo")
MIMO_TIMEOUT = int(os.environ.get("MIMO_TIMEOUT", "300"))
MAX_REPLY_LEN = 4000
ALLOWED_USERS = os.environ.get("ALLOWED_USERS", "")  # comma-separated user IDs, empty = allow all

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
log = logging.getLogger("mimo-bot")

# ─── State ────────────────────────────────────────────────────────────────────

user_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    allowed = {int(uid.strip()) for uid in ALLOWED_USERS.split(",") if uid.strip()}
    return user_id in allowed


# ─── Commands ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "MiMo Code Agent Bot\n\n"
        "发送文本或语音消息，我会转发给 MiMo Code 并返回结果。\n\n"
        "命令:\n"
        "/start - 显示此帮助\n"
        "/clear - 清除当前会话\n"
        "/status - 查看当前会话状态"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("session_id", None)
    await update.message.reply_text("会话已清除。")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sid = context.user_data.get("session_id")
    if sid:
        await update.message.reply_text(f"当前会话: `{sid}`", parse_mode="Markdown")
    else:
        await update.message.reply_text("无活跃会话，发送消息将创建新会话。")


# ─── Voice ────────────────────────────────────────────────────────────────────

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    status_msg = await update.message.reply_text("正在识别语音...")

    file = await context.bot.get_file(update.message.voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        await file.download_to_drive(tmp.name)
        tmp_path = tmp.name

    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        user_text = recognizer.recognize_google(audio, language="zh-CN")
        await status_msg.edit_text(f"识别结果: {user_text}\n\n思考中...")
    except sr.UnknownValueError:
        await status_msg.edit_text("无法识别语音内容，请重试或发送文本。")
        return
    except sr.RequestError as e:
        log.error("STT request failed: %s", e)
        await status_msg.edit_text(f"语音识别服务出错: {e}")
        return
    finally:
        os.unlink(tmp_path)

    await _process_message(user_text, update, context, status_msg)


# ─── Text ─────────────────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    user_text = update.message.text
    if not user_text or user_text.startswith("/"):
        return

    status_msg = await update.message.reply_text("思考中...")
    await _process_message(user_text, update, context, status_msg)


# ─── Core ─────────────────────────────────────────────────────────────────────

async def _process_message(
    user_text: str,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    status_msg,
):
    user_id = update.effective_user.id
    lock = user_locks[user_id]

    if lock.locked():
        await status_msg.edit_text("上一条消息还在处理中，请稍候...")
        return

    async with lock:
        cmd = [MIMO_BIN, "run", user_text, "--format", "json"]
        sid = context.user_data.get("session_id")
        if sid:
            cmd.extend(["-s", sid])

        log.info("user=%s session=%s text=%s", user_id, sid, user_text[:80])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "MIMOCODE_NON_INTERACTIVE": "1"},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=MIMO_TIMEOUT
            )
            output = stdout.decode("utf-8", errors="replace")
        except asyncio.TimeoutError:
            log.warning("user=%s timeout after %ds", user_id, MIMO_TIMEOUT)
            await status_msg.edit_text(
                f"处理超时（{MIMO_TIMEOUT}s），请重试或缩短消息长度。"
            )
            return
        except Exception as e:
            log.exception("user=%s mimo error", user_id)
            await status_msg.edit_text(f"MiMo 执行出错: {e}")
            return

        texts = []
        new_sid = None
        for line in output.strip().split("\n"):
            if not line:
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "text" and "text" in event.get("part", {}):
                    texts.append(event["part"]["text"])
                if event.get("sessionID"):
                    new_sid = event["sessionID"]
            except json.JSONDecodeError:
                continue

        if new_sid:
            context.user_data["session_id"] = new_sid

        reply = "\n".join(texts) if texts else "无响应内容"
        if len(reply) > MAX_REPLY_LEN:
            reply = reply[:MAX_REPLY_LEN] + "\n... (内容过长已截断)"

        log.info("user=%s reply_len=%d", user_id, len(reply))

        try:
            await status_msg.edit_text(reply)
        except Exception:
            await update.message.reply_text(reply)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting MiMo Telegram Bot...")
    log.info("MiMo binary: %s", MIMO_BIN)
    log.info("Timeout: %ds", MIMO_TIMEOUT)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
