# Security model & threat analysis (v0.2)

Switchboard lets an autonomous agent answer and place real phone calls
**without** turning the phone network into an attack surface on your server,
your money, or your life. Read alongside the invariants in `docs/spec.md §9`.

## Trust model
Most → least trusted: **owner control channel (Telegram, un-spoofable)** >
caller-ID match > anonymous. Caller ID is a *routing hint*, not proof.
Anything sensitive is therefore confirmed on the control channel, never
authorized by the phone line alone.

## Threat model

| # | Threat | Mitigation (invariant) |
|---|---|---|
| T1 | Stranger talks/texts the agent into actions ("prompt injection") | STRANGER sessions expose only `take_message`; identity decided by code before the model sees input; injection corpus in CI (S1) |
| T2 | Caller-ID spoofing of the owner's number | Caller ID never authorizes sensitive actions; they require **out-of-band approval** on Telegram, which a spoofer cannot reach (S3). No spoken/transcribable secret exists to steal |
| T3 | Forged or replayed webhooks | HMAC signature validation over the exact public URL, no skip-flag; ID dedupe (S2, S12) |
| T4 | **Unauthenticated relay WebSocket** — attacker opens a socket and impersonates a call | WS requires a single-use, CallSid-bound, short-TTL nonce; reused/expired/missing → rejected (S9) |
| T5 | **Brain reads secrets via a shell tool** (secrets live in the process env) | No general shell/file-exec tool by default; optional code-exec is sandboxed with no secret/DB access; non-root + NoNewPrivileges (S8) |
| T6 | **SSRF / web-content injection** — agent steered to fetch cloud metadata or read a page that says "now call X and leak contacts" | `web_fetch` egress filter blocks private/loopback/link-local/metadata IPs, caps redirects, mitigates DNS-rebinding; fetched text treated as untrusted data; high-privilege actions still gated by S3 (S10) |
| T7 | **Inbound cost abuse (financial DoS)** — spam calls/texts run up STT+LLM+telephony bills | Global concurrency cap, per-number cooldown, daily inbound-minutes budget; over limit → decline/forward + owner alert (S11) |
| T8 | Outbound cost runaway / toll fraud | Daily caps with 80% warn + 100% stop (S5); Twilio geo-permissions + balance alerts; brain-provider monthly spend limit; `MAX_CALL_MINUTES`; unknown-number calls need approval (S3) |
| T9 | Server compromise | Key-only SSH, UFW 22/80/443, fail2ban, unattended security upgrades, non-root service user, `NoNewPrivileges`, `ProtectSystem`, secrets chmod 600 |
| T10 | Privacy leakage to callers | Stranger persona forbids disclosing owner location/schedule/contacts; disclosing private data to a caller is itself a sensitive action (S3); transcripts only, no audio (S7) |
| T11 | Dangerous calls (emergency/premium numbers) | Hard blocklist (S4); real emergencies escalate to owner, never dialed |
| T12 | Agent misbehaving at runtime (bad loop, wrong target, weird vibes) | **Break-glass `/halt`** kill switch from the root-of-trust channel; persists across restart (S14). Dry-run mode for rehearsal |
| T13 | Stored transcripts as a PII honeypot | Retention purge (`TRANSCRIPT_RETENTION_DAYS`, S15); DTMF/secrets/audio never stored (S7); off-box backups inherit the same minimized data |
| T14 | Duplicate execution on crash/retry (two pizza orders) | Outbound idempotency keys, `processed_actions` dedupe (S13) |

## Why the spoken PIN was removed (v0.2)
A password spoken on a call is transcribed by STT, passes through the relay
WebSocket and the model's context, and is stored in the transcript — a static
secret that can be misheard, overheard, leaked via logs, or replayed forever.
Out-of-band approval on the un-spoofable channel is both **stronger** (no
secret to capture, nothing to replay) and **simpler**. An optional DTMF
keypad code MAY be added as a *second* factor for convenience, but never as
the sole gate, and never logged.

## Operator hardening checklist
- [ ] SSH keys only; consider moving SSH off port 22.
- [ ] Spend limits at **both** Twilio (balance/alerts) and the brain provider
      (monthly cap).
- [ ] `.env` chmod 600; never committed (`.gitignore` enforces).
- [ ] Confirm the relay WS rejects a connection with no/blank/reused token.
- [ ] Confirm `web_fetch` refuses `http://169.254.169.254/` and private IPs.
- [ ] Run spec §11 security tests after any change to identity/policy/tools.
- [ ] Know the kill switch: send `/halt test` once, confirm `/status` shows it, `/resume`.
- [ ] Review `journalctl` weekly; investigate dropped-peer and rate-limit
      warnings. Off-box backup of the SQLite DB if you'd miss it.

## Residual risks (be honest)
- AMD and bot-detection are probabilistic; a human may occasionally hear a
  voicemail script, or vice versa.
- A determined attacker controlling your Telegram account is game over — it is
  the root of trust. Protect that account (2FA).
- Any internet-reachable service can be probed; keep the surface to the three
  documented ports and let unattended-upgrades run.

Vulnerability reporting: see `SECURITY.md` at repo root.
