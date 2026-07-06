# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2026-07-06

### Fixed
- Kill timed-out MiMo subprocesses to prevent orphan process accumulation
- Sync `pyproject.toml` dependencies with `requirements.txt`

### Added
- `/ping`, `/version`, `/search` commands
- Graceful shutdown signal handling (SIGTERM/SIGINT)
- Unit tests (21 tests covering core functionality)
- CONTRIBUTING.md, CHANGELOG.md, SECURITY.md
- DuckDuckGo web search via `/search`

### Changed
- README updated with badges, architecture diagram, development guide
- AGENTS.md updated with current project state

## [1.0.0] - 2026-07-05

### Added
- Initial release
- Text conversation with MiMo Code Agent
- Voice message support (OGG → WAV via ffmpeg, Google STT)
- Session persistence across messages
- Per-user concurrency protection
- Access control via allowed user list
- Systemd service for deployment
