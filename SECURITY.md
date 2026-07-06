# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.1.x   | Yes       |
| < 1.1   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email: [your-email@example.com] or use GitHub's private vulnerability reporting
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Response Timeline

- Acknowledgment: within 48 hours
- Assessment: within 1 week
- Fix release: depends on severity

## Security Considerations

- Bot token is stored in `.env` (git-ignored)
- `ALLOWED_USERS` restricts access to specific Telegram user IDs
- Systemd service runs with `NoNewPrivileges=true` and `ProtectSystem=strict`
- Temporary voice files are cleaned up in `finally` blocks
- Subprocesses are killed on timeout to prevent orphan processes
