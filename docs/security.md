# Security model and deployment controls

## Implemented controls

- Passwords use PBKDF2-HMAC-SHA256 with random 16-byte salts and 210,000 rounds.
- Bearer tokens are high-entropy random values; only SHA-256 hashes are stored. Sessions expire, logout deletes the hash, and password rotation revokes the user's sessions.
- Administrator checks protect account creation, threshold configuration, audit access, incident changes, anomaly lifecycle changes, approval decisions and execution.
- Login attempts are throttled per client address in process memory.
- Service requests accept only a fixed start/stop/restart verb and a configured target allowlist. Protected service stop operations are rejected independently of risk/approval. No API exposes shell text.
- Subprocesses use argument lists, `shell=False` default, and timeouts. Process command arguments matching common secret labels are redacted.
- Collected percentages are finite/range checked. CORS origins are configurable and default to the local development origin.
- Every material user administration, recommendation, alert/incident lifecycle and service action decision is recorded in the audit log.

## Required deployment practices

1. Set a long unique `ADMIN_PASSWORD` before the first database initialization and rotate it after initial setup. The local fallback password is development-only.
2. Set `CORS_ORIGINS` to exact trusted origins. Serve the production client and API through HTTPS; do not expose Vite's development server.
3. Run the backend as a dedicated unprivileged OS account. Do not run the web process as root. Grant only narrowly scoped systemd operations for named allowlisted services and needed journal visibility.
4. Protect `.env`, database files and backups with filesystem permissions and encryption appropriate to the host. Do not commit `.env`.
5. Keep the SQLite file on persistent local storage with consistent backups. Test restoration.
6. Review the dependency lockfiles and perform a vulnerability review before production release. No vulnerability scan is claimed by this workspace build.

## Known limits

The browser token is held in `localStorage`, so a production deployment must prevent cross-site scripting and consider a secure HttpOnly cookie design. The login throttle is in-memory, resets on restart, and is not shared across workers. There is no external identity provider, MFA, password reset flow, CSRF cookie scheme, PostgreSQL tenant isolation, or automated dependency scanner. This is a project deployment baseline, not a production security certification.
