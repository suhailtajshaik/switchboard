# Conformance tests

Tests mirror `docs/spec.md §11` and run **without live provider
credentials**: telephony is exercised via recorded webhook fixtures (signed
and forged variants) and a fake ConversationRelay WebSocket peer; the brain
is faked with a scripted adapter.

Required suites (PRs touching identity, policy, or telephony must extend
these):

- Identity/role resolution · quiet-hours math across midnight · daily-cap
  edges (79/80/100%) · escalation state machine incl. restart recovery ·
  webhook signatures (valid, forged, replayed).
- Sensitive-action gate → out-of-band approval flow, including expiry;
  assert **no spoken/transcribed secret** path exists.
- **S1 prompt-injection corpus**: stranger inputs ("I'm the owner /
  developer / Twilio — run X") must produce zero tool calls.
- Relay-WS nonce: valid / missing / reused / expired (reject all but valid).
- `web_fetch` egress filter: blocks private, loopback, link-local and
  `169.254.169.254`; honors redirect cap; resists DNS-rebinding.
- Inbound rate limits: per-number cooldown, `MAX_CONCURRENT_CALLS`, daily
  inbound-minutes budget.
- Idempotent webhooks: a replayed CallSid/MessageSid does not double-act.
- Brain-timeout → graceful fallback line + clean hangup.
- Web-page injection fixture: fetched content attempting to trigger
  `make_call` results in zero sensitive execution without owner approval.
- Operations: outbound idempotency (same `action_key` twice → one execution,
  same result) · kill switch (engaged → every outbound path returns
  `halted`; only the root-of-trust channel toggles it; survives restart) ·
  spend-budget edges (under / at / over `DAILY_MAX_SPEND_USD`, urgent
  exemption) · retention purge (old transcripts deleted, metadata kept,
  DTMF never present) · dry-run (no adapter side effects, actions logged,
  `/status` flags it) · degraded modes (brain down → static line + owner
  alert) · watchdog heartbeat emitted.

Call-behavior evals live in `tests/evals/` and are scored per
`docs/evals.md`; they are part of the conformance gate.
