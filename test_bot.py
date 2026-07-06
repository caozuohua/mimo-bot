"""Tests for bot.py"""

import asyncio
import json
from collections import defaultdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import bot as bot_module


@pytest.fixture(autouse=True)
def _patch_env(monkeypatch):
    monkeypatch.setenv("ALLOWED_USERS", "")
    bot_module.ALLOWED_USERS = ""


# ─── Tests: is_allowed ────────────────────────────────────────────────────────


class TestIsAllowed:
    def test_allows_all_when_empty(self):
        with patch.object(bot_module, "ALLOWED_USERS", ""):
            assert bot_module.is_allowed(123456) is True

    def test_allows_listed_user(self):
        with patch.object(bot_module, "ALLOWED_USERS", "111,222,333"):
            assert bot_module.is_allowed(111) is True
            assert bot_module.is_allowed(222) is True
            assert bot_module.is_allowed(333) is True

    def test_blocks_unlisted_user(self):
        with patch.object(bot_module, "ALLOWED_USERS", "111,222"):
            assert bot_module.is_allowed(999) is False

    def test_handles_whitespace_in_ids(self):
        with patch.object(bot_module, "ALLOWED_USERS", " 111 , 222 , 333 "):
            assert bot_module.is_allowed(111) is True
            assert bot_module.is_allowed(999) is False

    def test_handles_empty_string(self):
        with patch.object(bot_module, "ALLOWED_USERS", ""):
            assert bot_module.is_allowed(123) is True


# ─── Tests: Command Handlers ──────────────────────────────────────────────────


class TestCommandHandlers:
    @pytest.mark.asyncio
    async def test_cmd_start(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        await bot_module.cmd_start(update, None)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "MiMo Code Agent Bot" in text
        assert "/start" in text
        assert "/clear" in text
        assert "/ping" in text
        assert "/version" in text
        assert "/search" in text

    @pytest.mark.asyncio
    async def test_cmd_clear(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {"session_id": "test-session"}

        await bot_module.cmd_clear(update, context)

        assert "session_id" not in context.user_data
        update.message.reply_text.assert_called_once_with("会话已清除。")

    @pytest.mark.asyncio
    async def test_cmd_status_no_session(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {}

        await bot_module.cmd_status(update, context)

        update.message.reply_text.assert_called_once_with(
            "无活跃会话，发送消息将创建新会话。"
        )

    @pytest.mark.asyncio
    async def test_cmd_status_with_session(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.user_data = {"session_id": "abc-123"}

        await bot_module.cmd_status(update, context)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "abc-123" in text

    @pytest.mark.asyncio
    async def test_cmd_ping(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        await bot_module.cmd_ping(update, None)

        update.message.reply_text.assert_called_once_with("pong")

    @pytest.mark.asyncio
    async def test_cmd_version(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        await bot_module.cmd_version(update, None)

        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "v1.0.0" in text


# ─── Tests: handle_message ────────────────────────────────────────────────────


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_skips_empty_message(self):
        update = AsyncMock()
        update.message.text = ""
        update.effective_user.id = 123

        context = MagicMock()

        await bot_module.handle_message(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_command_messages(self):
        update = AsyncMock()
        update.message.text = "/start"
        update.effective_user.id = 123

        context = MagicMock()

        await bot_module.handle_message(update, context)

        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_blocks_disallowed_user(self):
        with patch.object(bot_module, "ALLOWED_USERS", "111"):
            update = AsyncMock()
            update.message.text = "hello"
            update.effective_user.id = 999

            context = MagicMock()

            await bot_module.handle_message(update, context)

            update.message.reply_text.assert_not_called()


# ─── Tests: _process_message ──────────────────────────────────────────────────


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_replies_when_lock_busy(self):
        update = AsyncMock()
        update.message = AsyncMock()
        update.effective_user.id = 123
        context = MagicMock()

        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()

        lock = asyncio.Lock()
        await lock.acquire()
        bot_module.user_locks[123] = lock

        await bot_module._process_message("hello", update, context, status_msg)

        status_msg.edit_text.assert_called_once_with("上一条消息还在处理中，请稍候...")
        lock.release()

    @pytest.mark.asyncio
    async def test_calls_mimo_and_returns_result(self):
        update = AsyncMock()
        update.effective_user.id = 123
        context = MagicMock()
        context.user_data = {}

        status_msg = AsyncMock()

        mimo_output = json.dumps({"type": "text", "part": {"text": "Hello from MiMo"}})
        session_event = json.dumps({"sessionID": "new-session-abc"})
        full_output = f"{mimo_output}\n{session_event}"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(full_output.encode(), b""))

        with (
            patch.object(bot_module, "user_locks", defaultdict(asyncio.Lock)),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await bot_module._process_message("hello", update, context, status_msg)

        calls = [c[0][0] for c in status_msg.edit_text.call_args_list]
        assert any("Hello from MiMo" in c for c in calls)

    @pytest.mark.asyncio
    async def test_handles_timeout(self):
        update = AsyncMock()
        update.effective_user.id = 123
        context = MagicMock()
        context.user_data = {}

        status_msg = AsyncMock()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)

        with (
            patch.object(bot_module, "user_locks", defaultdict(asyncio.Lock)),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await bot_module._process_message("hello", update, context, status_msg)

        calls = [c[0][0] for c in status_msg.edit_text.call_args_list]
        assert any("处理超时" in c for c in calls)


# ─── Tests: JSON output parsing ───────────────────────────────────────────────


class TestOutputParsing:
    @pytest.mark.asyncio
    async def test_extract_text_from_json_lines(self):
        update = AsyncMock()
        update.effective_user.id = 123
        context = MagicMock()
        context.user_data = {}

        status_msg = AsyncMock()

        lines = [
            json.dumps({"type": "text", "part": {"text": "Line 1"}}),
            json.dumps({"type": "other", "part": {}}),
            json.dumps({"type": "text", "part": {"text": "Line 2"}}),
            "",
            "not-json",
        ]
        full_output = "\n".join(lines)

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(full_output.encode(), b""))

        with (
            patch.object(bot_module, "user_locks", defaultdict(asyncio.Lock)),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await bot_module._process_message("hello", update, context, status_msg)

        calls = [c[0][0] for c in status_msg.edit_text.call_args_list]
        combined = " ".join(calls)
        assert "Line 1" in combined
        assert "Line 2" in combined

    @pytest.mark.asyncio
    async def test_truncates_long_reply(self):
        update = AsyncMock()
        update.effective_user.id = 123
        context = MagicMock()
        context.user_data = {}

        status_msg = AsyncMock()

        long_text = "x" * (bot_module.MAX_REPLY_LEN + 500)
        full_output = json.dumps({"type": "text", "part": {"text": long_text}})

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(full_output.encode(), b""))

        with (
            patch.object(bot_module, "user_locks", defaultdict(asyncio.Lock)),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            await bot_module._process_message("hello", update, context, status_msg)

        calls = [c[0][0] for c in status_msg.edit_text.call_args_list]
        assert any("内容过长已截断" in c for c in calls)


# ─── Tests: handle_voice ──────────────────────────────────────────────────────


class TestHandleVoice:
    @pytest.mark.asyncio
    async def test_blocks_disallowed_user(self):
        with patch.object(bot_module, "ALLOWED_USERS", "111"):
            update = AsyncMock()
            update.effective_user.id = 999

            context = MagicMock()

            await bot_module.handle_voice(update, context)

            update.message.reply_text.assert_not_called()


# ─── Tests: Main ──────────────────────────────────────────────────────────────


class TestMain:
    def test_main_registers_signal_handlers(self):
        import signal

        mock_app = MagicMock()

        with (
            patch("bot.ApplicationBuilder") as mock_builder,
            patch("signal.signal") as mock_signal,
        ):
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            bot_module.main()

        signal_types = [call.args[0] for call in mock_signal.call_args_list]
        assert signal.SIGTERM in signal_types
        assert signal.SIGINT in signal_types
        mock_app.run_polling.assert_called_once_with(drop_pending_updates=True)
