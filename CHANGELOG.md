# Changelog
All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org).

## [Unreleased]

## [0.3.0-alpha] - 2026-06-12
### Operations & reliability pass (spec v0.3 — capabilities deferred by design)
- **Call-behavior eval harness**: scenario format, hard-check rubric and
  runner contract (`docs/evals.md`) + five starter scenarios in
  `tests/evals/` (happy order, early-beep voicemail, IVR menu, rude human,
  owner-impersonator). CI gates on hard checks.
- **Dry-run mode** (`DRY_RUN=true`): rehearse the full loop with zero real
  calls/SMS; flagged in `/status`.
- **Outbound idempotency (S13)**: `action_key` + `processed_actions` dedupe —
  a crash/retry can never order two pizzas. `make_action_key()` in core.
- **Break-glass kill switch (S14)**: `/halt` / `/resume` from the owner
  channel only; blocks all outbound + sensitive tools, persists across
  restart (`runtime_flags`), prominent in `/status`. `KillSwitch` in core.
- **Spend ledger + daily $ budget**: per-call `est_cost_usd`, per-day
  `spend_usd` counters, `DAILY_MAX_SPEND_USD` soft budget (80% warn, 100%
  pause for non-urgent; urgent escalations exempt). `spend_check()` in core.
- **Call review**: `/calls [n]` and `/call <id>` owner commands.
- **Watchdog**: `Type=notify` + `WatchdogSec=60` shipped (commented until
  `main.py` implements sd_notify per spec §7) — catches hung processes.
- **Degraded modes**: brain down → static apology line for strangers + owner
  alert; telephony/control-channel failure behavior defined
  (`docs/operations.md §5`).
- **Backups**: `scripts/backup.sh` (live-safe `.backup`, gzip, 14-day prune,
  optional `BACKUP_REMOTE` rclone off-box sync) + cron instructions.
- **Transcript retention / PII minimization (S15)**:
  `TRANSCRIPT_RETENTION_DAYS` nightly purge (0 = never store transcripts).
- **Consent provenance**: contacts gain `consent_method/at/note` —
  answerable consent if a call is ever questioned.
- New docs: `docs/operations.md`, `docs/evals.md`; config/security/deployment
  docs and `.env.example` updated accordingly.

## [0.2.0-alpha] - 2026-06-12
### Security (hardening pass — see docs/spec.md v0.2)
- **Removed the spoken `VOICE_PIN`** as an auth mechanism. A transcribed voice
  password is a static, replayable, overhearable secret. Sensitive actions
  requested over phone/SMS now require **out-of-band approval** on the
  root-of-trust channel (Telegram) — stronger and simpler (S3). Optional DTMF
  second factor only.
- **Authenticated the relay WebSocket** with a single-use, CallSid-bound,
  short-TTL nonce; closes a previously open WS endpoint (S9).
- **Dropped general shell/file-exec from the default brain toolset**; secrets
  live in process env, so a shell tool could read them. Optional code-exec
  must be sandboxed without secret/DB access (S8). Tightened systemd
  sandboxing (ProtectSystem=strict, MemoryDenyWriteExecute, etc.).
- **SSRF / web-content injection defenses** for `web_fetch`: block
  private/loopback/link-local/cloud-metadata IPs, redirect cap, DNS-rebinding
  mitigation, fetched content treated as untrusted data (S10).
- **Inbound abuse limits** (financial DoS): concurrency cap, per-number
  cooldown, daily inbound-minutes budget (S11).
- **Idempotent webhook handling**: dedupe provider IDs so retries/replays
  don't double-act (S12).
- Webhook signature validation can no longer be disabled by config.
### Reliability & latency (new spec §7)
- Explicit call hot-path rules: stream tokens, never block the event loop
  (async I/O, SQLite WAL), barge-in interruptible.
- **Holding phrase** emitted by the harness the instant a tool call starts —
  no dead air.
- **Brain-response timeout** → graceful fallback line + clean hangup instead
  of silence.
- Conversational model is a config choice; guidance to pick a low-latency one.
### Added config
- `APPROVAL_TIMEOUT_MINUTES`, `MAX_CONCURRENT_CALLS`,
  `INBOUND_PER_NUMBER_COOLDOWN_SECONDS`, `DAILY_INBOUND_MINUTES`,
  `BRAIN_RESPONSE_TIMEOUT_SECONDS`, `RELAY_NONCE_TTL_SECONDS`,
  `BLOCKED_PREFIXES`, `BRAIN_BASE_URL`, `BRAIN_MODEL`, optional `DTMF_PIN`.
- Personas bumped to v2 (OOB-approval cooperation + holding-phrase behavior).

## [0.1.0-alpha] - 2026-06-11
### Added
- Normative harness specification (`docs/spec.md`) with security invariants
  S1–S8 and conformance test list.
- Documentation set: architecture, configuration, deployment, Twilio guide,
  security threat model, legal guide, persona format, extension guide.
- Persona pack v1: `master_mode`, `assistant_mode`, `outbound_call`, `wakeup`.
- Deploy tooling: `scripts/setup.sh` (Ubuntu 24.04), systemd unit, Caddyfile.
- OSS hygiene: MIT license, CONTRIBUTING, SECURITY policy, Code of Conduct.
