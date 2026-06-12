# Conformance tests

Tests mirror `docs/spec.md §11` and run **without live provider
credentials**: telephony is exercised via recorded webhook fixtures (signed
and forged variants) and a fake ConversationRelay WebSocket peer; the brain
is faked with a scripted adapter.

Required suites: identity/roles · sensitive-action gate (S3) · quiet hours ·
escalation state machine (incl. restart recovery) · webhook signatures ·
caps · **S1
prompt-injection corpus** (stranger inputs that must produce zero tool
calls). PRs touching identity/policy/telephony must extend these.

## v0.2 additions (must pass)
- Sensitive-action gate → out-of-band approval flow, including expiry; assert
  **no spoken/transcribed secret** path exists.
- Relay-WS nonce: valid / missing / reused / expired (reject all but valid).
- `web_fetch` egress filter: blocks private, loopback, link-local and
  `169.254.169.254`; honors redirect cap; resists DNS-rebinding.
- Inbound rate limits: per-number cooldown, `MAX_CONCURRENT_CALLS`, daily
  inbound-minutes budget.
- Idempotent webhooks: a replayed CallSid/MessageSid does not double-act.
- Brain-timeout → graceful fallback line + clean hangup.
- Web-page injection fixture: fetched content attempting to trigger
  `make_call` results in zero sensitive execution without owner approval.
