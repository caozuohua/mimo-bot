# Contributing to MiMo Telegram Bot

Thanks for your interest in contributing!

## Development Workflow

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run lint and tests:
   ```bash
   ruff check .
   ruff format .
   pytest -v
   ```
5. Commit with a clear message
6. Push and open a Pull Request

## Code Style

- Python 3.10+
- Line length: 88 (enforced by ruff)
- No comments unless the why is non-obvious
- Log with `log.info()` / `log.error()`
- Clean up temp files in `finally` blocks

## Testing

Add tests for new features. Tests are in `test_bot.py`.

```bash
pytest -v
```

## Reporting Issues

Use [GitHub Issues](https://github.com/caozuohua/mimo-bot/issues) for bugs and feature requests.

## Security

Report security vulnerabilities privately. See [SECURITY.md](SECURITY.md).
