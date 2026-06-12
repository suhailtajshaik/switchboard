# Changelog
All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) ·
Versioning: [SemVer](https://semver.org).

## [Unreleased]

## [0.1.0-alpha] - 2026-06-12
First version — nothing earlier was released or deployed.

### Added
- **Normative specification** (`docs/spec.md`, v0.1): runtime, identity &
  policy engine with out-of-band sensitive-action approval (no spoken
  secrets), role-filtered tool registry, HTTP/WS surface with an
  authenticated relay WebSocket (single-use nonce), outbound-call algorithm
  with AMD branching and idempotency keys, escalation state machine,
  latency & reliability rules (token streaming, holding phrases, brain
  timeouts, watchdog heartbeat, degraded modes, dry-run), break-glass kill
  switch, spend ledger + daily dollar budget, transcript retention, SQLite
  schema, security invariants **S1–S15**, and the conformance-test list
  (§11).
- **Core reference implementation** (`src/`, partial by design — see
  `src/README.md`): fail-fast config, role resolution, policy engine
  (capability table, `ApprovalGate`, `KillSwitch`, `spend_check`,
  `make_action_key`), phone normalization, persona loader, escalation FSM,
  SQLite store, Twilio webhook-signature validation.
- **Persona pack v1**: `master_mode`, `assistant_mode`, `outbound_call`,
  `wakeup`.
- **Call-behavior eval harness**: scenario format and hard-check rubric
  (`docs/evals.md`) with five starter scenarios in `tests/evals/` (happy
  order, early-beep voicemail, IVR menu, rude human, owner-impersonator).
- **Deploy tooling**: `scripts/setup.sh` (Ubuntu 24.04, arm64-compatible),
  hardened systemd unit, Caddyfile, nightly backup script
  (`scripts/backup.sh`).
- **Documentation**: architecture, configuration, deployment, Twilio guide,
  security threat model, legal guide, operations guide, persona guide,
  extension guide, end-to-end setup checklist (`docs/setup-checklist.md`)
  and agent guidance (`CLAUDE.md`).
- **OSS hygiene**: MIT license, CONTRIBUTING, SECURITY policy, Code of
  Conduct.
