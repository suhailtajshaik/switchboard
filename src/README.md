# Reference implementation (status: partial)

This directory holds the spec-conformant reference implementation
(Python 3.12 / FastAPI). It is **built and verified against
[`../docs/spec.md`](../docs/spec.md)** — the spec is normative; this code is
one conformant expression of it.

## What's here now (pure, unit-testable core logic)
- `core/config.py` — fail-fast config load; **no `VOICE_PIN`** (deliberate —
  spec §2.1); refuses to boot if signature validation is disabled (S2).
- `core/identity.py` — role resolution; caller ID is a hint, not auth.
- `core/policy.py` — capability table (S1), quiet hours, number blocklist
  (S4), daily caps (S5), **inbound rate limiting (S11)**, and the
  **`ApprovalGate` out-of-band approval model (S3)** that replaced the spoken
  PIN. Sensitive-action classifier + unknown-number gate included.
- `core/phones.py`, `core/personas.py`, `core/escalation.py`, `core/store.py`,
  `adapters/twilio_signature.py` — supporting logic.
- `core/policy.py` also carries the **`KillSwitch`** (S14, owner-
  channel-only, restorable from `runtime_flags`), **`spend_check`** (daily $
  budget with urgent/override exemptions), and **`make_action_key`** (S13
  outbound idempotency). `core/config.py` covers the operations settings
  (`DAILY_MAX_SPEND_USD`, `TRANSCRIPT_RETENTION_DAYS`, `DRY_RUN`).

## What still needs wiring to be a running, secure system
These invariants require the event loop, DB, and adapters — implement them
when you stand the service up (generate against the spec, then run the
conformance tests in §11 until green):
- **S9** relay-WS nonce: persist `relay_nonces`, mint on TwiML emit, validate
  + single-use on WS connect. *(The WebSocket is unauthenticated until this
  exists — do not expose it publicly without it.)*
- **S10** `web_fetch` egress filter (block private/loopback/link-local/
  metadata IPs, redirect cap, DNS-rebinding) + untrusted-content handling.
- **S12** idempotent webhook dedupe (`processed_events`).
- **§7** holding-phrase emission, token streaming, brain-response timeout +
  graceful fallback, non-blocking event loop (the store already enables
  SQLite WAL).
- Persistence for `pending_approvals`, `counters` (incl. inbound minutes and
  `spend_usd`), the contacts consent-provenance and calls cost/task columns
  (spec §8), `processed_actions` (S13), `runtime_flags` (S14), the
  Telegram approve/deny round-trip that drives `ApprovalGate`, the
  `/halt /resume /calls /status /override` commands, the nightly retention
  purge (S15) + backup cron, the sd_notify watchdog heartbeat, dry-run
  plumbing in the adapters, and the eval runner for `tests/evals/`
  (`docs/evals.md`).

## Two supported ways to complete it
1. Copy a tagged release of `src/`.
2. Generate the remaining adapters/wiring with a coding agent (e.g. Claude
   Code) on your own server using `docs/spec.md` + `docs/configuration.md` as
   the instruction. Generating on-host means signature validation, the relay
   WebSocket nonce, AMD branches, and the egress filter get verified against
   *real* provider traffic before you trust the system.

Expected layout:
```
src/
  main.py            # process entry: gateway + control channel + scheduler
  core/              # identity, policy, sessions, escalation, store (here)
  adapters/          # telephony_twilio.py, channel_telegram.py, brain_claude.py
  requirements.txt   # pinned
```
