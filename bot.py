#!/usr/bin/env python3
"""Telegram Bot that bridges to MiMo Code Agent."""

import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from collections import defaultdict

import speech_recognition as sr
from duckduckgo_search import DDGS
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── Config ───────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    sys.exit("FATAL: TELEGRAM_BOT_TOKEN environment variable not set")

MIMO_BIN = os.path.expanduser("~/.mimocode/bin/mimo")
MIMO_TIMEOUT = int(os.environ.get("MIMO_TIMEOUT", "300"))
if MIMO_TIMEOUT <= 0:
    sys.exit("FATAL: MIMO_TIMEOUT must be a positive integer")
MAX_REPLY_LEN = 4000
ALLOWED_USERS = os.environ.get(
    "ALLOWED_USERS", ""
)  # comma-separated user IDs, empty = allow all
STT_LANGUAGE = os.environ.get("STT_LANGUAGE", "zh-CN")
MAX_RETRIES = 2
RETRY_DELAY = 1  # seconds

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)
log = logging.getLogger("mimo-bot")

# ─── Startup Checks ───────────────────────────────────────────────────────────


def check_ffmpeg():
    if shutil.which("ffmpeg") is None:
        log.error("ffmpeg not found in PATH. Voice messages will fail.")
        return False
    return True


def check_mimo_bin():
    if not os.path.isfile(MIMO_BIN):
        log.error("MiMo binary not found at %s", MIMO_BIN)
        return False
    if not os.access(MIMO_BIN, os.X_OK):
        log.error("MiMo binary at %s is not executable", MIMO_BIN)
        return False
    return True


if not check_ffmpeg():
    log.warning("Continuing without ffmpeg – voice messages will be unavailable")
if not check_mimo_bin():
    log.warning("Continuing without MiMo binary – text/voice processing will fail")

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
        "/status - 查看当前会话状态\n"
        "/ping - 检查机器人是否在线\n"
        "/version - 查看版本信息\n"
        "/search <关键词> - 使用 DuckDuckGo 搜索"
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


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong")


async def cmd_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("MiMo Telegram Bot v1.0.0")


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("用法: /search <关键词>")
        return

    query = " ".join(context.args)
    status_msg = await update.message.reply_text(f"搜索中: {query}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        if not results:
            await status_msg.edit_text("未找到相关结果。")
            return

        reply = f"搜索结果: {query}\n\n"
        for i, r in enumerate(results, 1):
            reply += f"{i}. {r['title']}\n{r['href']}\n{r['body'][:200]}\n\n"

        if len(reply) > MAX_REPLY_LEN:
            reply = reply[:MAX_REPLY_LEN] + "\n... (内容过长已截断)"

        await status_msg.edit_text(reply)
    except Exception as e:
        log.exception("Search error")
        await status_msg.edit_text(f"搜索出错: {e}")


# ─── Voice ────────────────────────────────────────────────────────────────────


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        return

    status_msg = await update.message.reply_text("正在识别语音...")

    file = await context.bot.get_file(update.message.voice.file_id)
    ogg_path = None
    wav_path = None

    try:
        # Download OGG from Telegram
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            ogg_path = tmp.name

        # Convert OGG → WAV (SpeechRecognition needs WAV/AIFF/FLAC)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-i",
            ogg_path,
            "-ar",
            "16000",
            "-ac",
            "1",
            "-f",
            "wav",
            wav_path,
            "-y",
            "-loglevel",
            "error",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error("ffmpeg conversion failed: %s", stderr.decode())
            await status_msg.edit_text("语音格式转换失败，请重试。")
            return

        # Recognize speech with retry
        recognizer = sr.Recognizer()
        user_text = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                with sr.AudioFile(wav_path) as source:
                    audio = recognizer.record(source)
                user_text = recognizer.recognize_google(audio, language=STT_LANGUAGE)
                break
            except sr.RequestError as e:
                if attempt < MAX_RETRIES:
                    log.warning("STT request failed (attempt %d): %s", attempt + 1, e)
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    log.error("STT request failed after %d retries: %s", MAX_RETRIES, e)
                    await status_msg.edit_text(f"语音识别服务出错: {e}")
                    return
            except sr.UnknownValueError:
                await status_msg.edit_text("无法识别语音内容，请重试或发送文本。")
                return
            except Exception as e:
                log.exception("Voice processing error")
                await status_msg.edit_text(f"语音处理出错: {e}")
                return
        if user_text is None:
            await status_msg.edit_text("语音识别失败，请重试。")
            return

        await status_msg.edit_text(f"识别结果: {user_text}\n\n思考中...")
    finally:
        if ogg_path:
            os.unlink(ogg_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)

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

        output = None
        for attempt in range(MAX_RETRIES + 1):
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
                break
            except asyncio.TimeoutError:
                log.warning(
                    "user=%s timeout after %ds (attempt %d)",
                    user_id,
                    MIMO_TIMEOUT,
                    attempt + 1,
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    await status_msg.edit_text(
                        f"处理超时（{MIMO_TIMEOUT}s），请重试或缩短消息长度。"
                    )
                    return
            except Exception as e:
                log.exception("user=%s mimo error (attempt %d)", user_id, attempt + 1)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    await status_msg.edit_text(f"MiMo 执行出错: {e}")
                    return

        if output is None:
            await status_msg.edit_text("MiMo 执行失败，请重试。")
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
    import signal

    log.info("Starting MiMo Telegram Bot...")
    log.info("MiMo binary: %s", MIMO_BIN)
    log.info("Timeout: %ds", MIMO_TIMEOUT)
    log.info("STT language: %s", STT_LANGUAGE)
    log.info("Max retries: %d", MAX_RETRIES)

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("version", cmd_version))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    def _shutdown_handler(signum, frame):
        sig_name = signal.Signals(signum).name
        log.info("Received %s, shutting down gracefully...", sig_name)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    log.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)
    log.info("Bot shut down.")


if __name__ == "__main__":
    main()
