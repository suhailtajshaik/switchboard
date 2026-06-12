# Switchboard Specification (normative) — v0.3

The key words **MUST**, **MUST NOT**, **SHOULD**, **MAY** are to be
interpreted as in RFC 2119. An implementation is *conformant* when it
satisfies every MUST and passes the conformance tests in §11. This document is
written to be directly usable as the build instruction for a coding agent
(e.g. Claude Code) producing the reference implementation in `src/`.

> **v0.2 hardening summary** (see CHANGELOG): the spoken PIN is removed as an
> auth mechanism in favor of **out-of-band confirmation** on the root-of-trust
> channel (S3); the relay WebSocket is now **authenticated with a single-use
> nonce** (S9); the brain has **no shell/file-exec tools by default** (S8);
> outbound web fetch is **egress-filtered** against SSRF (S10); **inbound rate
> limits + call concurrency caps** are required (S11); webhook handling is
> **idempotent** (S12). A dedicated latency/reliability section (§7) makes the
> "fast, human-feeling call" requirements explicit.
>
> **v0.3 operations pass:** outbound-action **idempotency keys** (S13); a
> **break-glass kill switch** halting all outbound activity (S14);
> **transcript retention limits** (S15); a **spend ledger + daily dollar
> budget**; **degraded modes** for brain/telephony outages; a **systemd
> watchdog heartbeat**; **dry-run mode**; **consent provenance**; nightly
> **off-box backups**; and a scripted **call-behavior eval harness**.
> Operational detail lives in `docs/operations.md` and `docs/evals.md`.

## 1. Runtime
- Single process, single owner. Reference stack: Python ≥3.12, FastAPI on
  `127.0.0.1:8080` behind a TLS reverse proxy at `https://$PUBLIC_DOMAIN`
  (WebSocket upgrades supported).
- Subsystems in one asyncio loop: HTTP/WS gateway, control-channel poller
  (Telegram long polling), scheduler (APScheduler, jobs persisted).
- The event loop is the **call hot path**. All I/O in a call turn (LLM,
  Twilio REST, DB) MUST be non-blocking; no synchronous network or disk call
  may run inside a call turn (§7). SQLite MUST run in WAL mode.
- All configuration from environment (`docs/configuration.md`). The process
  MUST fail fast at boot on missing/invalid required config, and MUST refuse
  to start if webhook signature validation is disabled (no "skip-auth" flag).

## 2. Identity, trust & policy engine
- `normalize(phone)` → E.164. Role resolution: `OWNER_PHONE`→`MASTER`;
  member of `WHITELIST_PHONES`→`TRUSTED`; else `STRANGER`. The owner Telegram
  chat id is the **root of trust**.
- **Trust ladder** (most → least trusted): owner control channel (Telegram,
  un-spoofable) > caller-ID match > nothing. **Caller ID is a routing hint,
  not authentication** — it can be spoofed, so it alone never authorizes a
  sensitive action.
- The policy engine is the **only** path to side-effecting tools. Every tool
  invocation carries `(role, channel, session)` and MUST be evaluated against
  the role capability table (§3), the consent registry, quiet hours, daily
  caps, the blocked-number list, and the sensitive-action gate (§2.1).

### 2.1 Sensitive-action gate (replaces the spoken PIN)
A **sensitive action** is any of: mutating config/whitelist/contacts;
`make_call` to a number not already a saved contact; spending beyond a
per-task budget; or disclosing the owner's private data (schedule, address,
other numbers, email) to a phone caller.
- A sensitive action requested on the **phone or SMS channel** MUST be held
  and **confirmed out-of-band** on the root-of-trust channel: the harness
  sends the owner a Telegram approve/deny prompt; the action executes only on
  explicit approval, expires otherwise (default 5 min). The phone caller is
  told "I've sent that to Suhail to approve."
- Requests on the **owner Telegram channel** need no second factor (already
  root of trust).
- **No secret is ever spoken or transcribed.** Implementations MUST NOT use a
  voice-spoken password as an auth gate. An optional DTMF (keypad) second
  factor MAY be added for convenience but MUST NOT be the sole gate and MUST
  be excluded from logs and transcripts.

## 3. Tool registry
Tools are exposed to the brain per role. The brain only ever sees tools its
role is allowed; denied tools are absent from its toolset (not refused at
call time).

| Tool | MASTER | TRUSTED | STRANGER |
|---|---|---|---|
| `make_call(to, task_brief, persona, budget?)` | ✅ (sensitive if `to` is unknown) | ✅ | ❌ |
| `send_sms(to, body)` | ✅ | ✅ | ❌ |
| `notify_owner(text)` | ✅ | ✅ | ❌ |
| `add_reminder/list/cancel` | ✅ | ✅ | ❌ |
| `add_contact` (sensitive) / `lookup_contact` | ✅ | ✅ (lookup) | ❌ |
| `take_message(caller, summary, urgency)` | ✅ | ✅ | ✅ *(only tool)* |
| `web_search(query)` | ✅ | opt-in | ❌ |
| `web_fetch(url)` (egress-filtered, §10) | ✅ | opt-in | ❌ |

- **No general shell or arbitrary file-write/exec tool is exposed by
  default** (S8). The agent's capabilities are the structured tools above.
  Any optional code-exec capability MUST run in a separate sandbox with **no
  access to process secrets or the live DB**, and is off unless explicitly
  enabled.
- `send_sms` with `SMS_ENABLED=false` MUST degrade to `notify_owner` and say
  so in its return value.

## 4. HTTP/WS surface (reference: Twilio adapter)
| Route | Method | Behavior |
|---|---|---|
| `/health` | GET | `{"ok": true, "version": …}` |
| `/twilio/voice` | POST | Inbound call webhook → S2 verify → role lookup → mint a **single-use relay nonce** (§S9) → TwiML `<Connect><ConversationRelay url="wss://$PUBLIC_DOMAIN/twilio/relay?token={nonce}">` with role-appropriate greeting and a natural TTS voice. Consult the current ConversationRelay TwiML reference for attributes. |
| `/twilio/relay` | WS | Validate `token` (§S9) before accepting. Then run the ConversationRelay protocol: handle `setup`/`prompt`/`interrupt`, stream brain output as `text` tokens, end session to hang up. Latency budget §7. |
| `/twilio/sms` | POST | S2 verify → same role routing as voice. |
| `/twilio/amd` | POST | S2 verify → inject `AnsweredBy` into the live call session. |
| `/twilio/status` | POST | S2 verify → update `calls`. |

## 5. Outbound call algorithm (`make_call`)
1. Policy pre-flight; refuse with a machine-readable reason on failure:
   `emergency_number` (911/112/999/000 + premium-rate prefixes — per-country
   list in config), `quiet_hours` (unless target is owner), `daily_cap`,
   `no_consent` (person contact with `consented_to_ai_calls=false`),
   `budget_exceeded`, `unknown_number_unconfirmed` (target not a saved
   contact and the §2.1 out-of-band confirmation has not been approved),
   `daily_spend_budget` (daily USD budget reached and the action is not
   urgent/owner-overridden), `halted` (kill switch engaged, S14).
2. **Idempotency (S13):** the action carries an `action_key`; if the key
   exists in `processed_actions`, return the recorded result without
   re-executing (a crash/retry must never order two pizzas).
3. Place via REST with `MachineDetection=Enable`, `AsyncAmd=true`,
   `AsyncAmdStatusCallback=/twilio/amd`; TwiML connects to the relay WS (with
   its own minted nonce) using the `outbound_call` persona + task brief.
4. Branch on `AnsweredBy`: `human`→converse; `machine_*`→voicemail mode
   (wait for end-of-greeting/beep, deliver ≤20 s message, hang up);
   `fax|unknown`→end + log. IVR/bot detected mid-dialogue → persona literal
   mode (no new permissions).
5. Hard limits: force-end at `MAX_CALL_MINUTES`; one retry MAX on
   `no-answer`; never re-dial a `busy` number within 15 min.
6. Post-call (always, incl. failures): persist transcript + outcome;
   `notify_owner` with a ≤3-line summary. **No audio recording** (S7).

## 6. Escalation state machine
States: `PENDING → NOTIFIED → WAITING → CALLING → RETRY(n) → ACKED|ABANDONED`,
persisted so transitions survive restart.
- `low`: control-channel message only.
- `normal`: message (+SMS if enabled) → no ack in `ESCALATION_WAIT_MINUTES`
  → call (`wakeup` persona) → up to 4 retries at 5-min intervals.
- `high`: call immediately; message+SMS each attempt; same retry bound.
- An ack on ANY channel cancels the chain. Wake-ups require a *verbal*
  acknowledgment phrase before transitioning to `ACKED`.

## 7. Latency & reliability (the call must feel human and never hang)
- **First audio fast.** Target time-to-first-token < 1 s per turn; stream
  `text` tokens to TTS as they generate — never wait for a full completion.
- **No dead air.** The moment the brain starts any tool call (search, fetch,
  placing a sub-call), the harness MUST emit a short holding phrase
  ("One moment, let me check…") so the line is never silent. This is harness
  behavior, not merely persona guidance.
- **Barge-in.** The relay MUST be configured interruptible so the caller can
  talk over TTS; on interrupt, stop streaming and truncate pending output.
- **Brain timeout → graceful fallback.** A brain turn that exceeds
  `BRAIN_RESPONSE_TIMEOUT_SECONDS` MUST be aborted and the call given a clean
  fallback line ("Sorry, I'm having trouble — I'll have {OWNER_NAME} follow
  up") then ended, rather than hanging silently.
- **Model latency is a config choice.** Conversational turns SHOULD use a
  low-latency model; heavy-reasoning models add turn lag and degrade call
  feel. (See `docs/configuration.md`.)
- **WS lifecycle.** Handle relay disconnects, Twilio retries, and
  half-open sockets without leaking sessions; close DB handles per turn.
- **Scheduler durability.** Reminder/escalation jobs and state survive
  process restart (persisted).
- **Watchdog heartbeat.** The process MUST integrate with the systemd
  watchdog: `sd_notify(READY=1)` at boot and `WATCHDOG=1` from the main loop
  at < half of `WatchdogSec`, so a *hung* (not crashed) process is restarted.
- **Degraded modes** (never dead air, never silent failure):
  brain unreachable/timed-out → inbound strangers hear a static apology line
  asking them to text instead; owner is alerted. Telephony API failing →
  owner alerted on the control channel. Control channel failing → log,
  retry with backoff, and (if enabled) SMS-alert the owner. Details in
  `docs/operations.md`.
- **Dry-run mode.** With `DRY_RUN=true`, side-effecting adapters (calls, SMS)
  log and report what they *would* do instead of doing it; `/status` MUST
  display DRY-RUN prominently. For end-to-end rehearsal before spending
  money or dialing anyone real.

## 8. Storage (SQLite reference schema, WAL mode)
`contacts(id, name, phone UNIQUE, relationship, consented_to_ai_calls BOOL,
notes, created_at)` · `sessions(id, channel, peer, role, persona, state,
updated_at)` · `messages(id, session_id, direction, content, ts)` ·
`calls(id, sid UNIQUE, direction, peer, answered_by, started_at, ended_at,
outcome, transcript)` · `reminders(id, when_ts, text, urgency, state,
attempts)` · `counters(day, calls_out, sms_out, agent_usd, inbound_minutes)` ·
`pending_approvals(id, action_json, requested_at, state)` ·
`relay_nonces(token, call_sid, issued_at, used BOOL)` ·
`processed_events(provider_id UNIQUE, ts)` *(inbound idempotency, S12)* ·
`processed_actions(action_key UNIQUE, tool, result_json, ts)` *(outbound
idempotency, S13; keys expire after 7 days)* ·
`runtime_flags(name PRIMARY KEY, value, set_at, reason)` *(kill switch
state — persists across restart, S14)*.
**v0.3 column additions:** `calls` gains `est_cost_usd REAL` and
`task_id TEXT`; `contacts` gains consent provenance — `consent_method TEXT`,
`consent_at TEXT`, `consent_note TEXT` (S3/legal); `counters` also tracks
`spend_usd` buckets (telephony/llm). Transcripts and messages older than
`TRANSCRIPT_RETENTION_DAYS` are purged nightly, keeping call metadata (S15).

## 9. Security invariants (conformance-critical)
- **S1** A `STRANGER` session can never invoke any tool except
  `take_message`, regardless of message content (prompt injection ≠ access).
- **S2** Every telephony webhook MUST pass provider signature validation
  (HMAC over the exact public URL) before any business-field parsing; there
  is no flag to disable it. Unknown control-channel peers are dropped+logged.
- **S3** Sensitive actions (§2.1) requested over phone/SMS require
  **out-of-band approval on the root-of-trust channel**; no secret is spoken
  or transcribed; caller ID alone never authorizes them.
- **S4** Emergency/premium numbers are unreachable by `make_call`; a detected
  real emergency is escalated to the owner, never dialed.
- **S5** Daily outbound caps enforced; 80% warning to owner; 100% hard stop
  requiring explicit owner override via the control channel.
- **S6** The AI-disclosure first sentence is injected by the harness into
  every outbound persona and MUST NOT be removable by task briefs or callers.
- **S7** No audio recording anywhere; transcripts only; secrets (`.env`)
  chmod 600; secrets never written to logs or transcripts.
- **S8** No general shell/file-exec tool is exposed to the brain by default;
  any optional code execution runs sandboxed with no access to secrets or the
  live DB. The service runs as a non-root user with `NoNewPrivileges`.
- **S9** The relay WebSocket MUST require a **single-use, short-TTL nonce**
  (minted when the TwiML is emitted, bound to the CallSid, marked used on
  first connect). Unauthenticated or replayed WS connections are rejected.
- **S10** `web_fetch` MUST egress-filter: deny private, loopback,
  link-local and cloud-metadata addresses (incl. `169.254.169.254`), follow a
  redirect cap, and treat fetched content as untrusted data (delimited, never
  executed as instructions). DNS-rebinding is mitigated (resolve-then-pin).
- **S11** Inbound abuse is bounded: a global `MAX_CONCURRENT_CALLS` cap, a
  per-number inbound cooldown, and a daily inbound-minutes budget; beyond
  limits, calls are declined/forwarded and the owner is notified (financial
  DoS protection).
- **S12** Webhook processing is **idempotent**: provider message/call IDs are
  deduped (`processed_events`) so retried or replayed deliveries never
  double-start sessions or double-send summaries.
- **S13** Every side-effecting outbound action (`make_call`, `send_sms`)
  carries an **idempotency `action_key`**; a repeated key returns the
  recorded result and never re-executes.
- **S14** A **break-glass kill switch**, togglable only from the
  root-of-trust channel (`/halt`, `/resume`), immediately blocks all outbound
  calls/SMS and sensitive tool execution; state persists across restart and
  is displayed prominently in `/status`. Inbound message-taking keeps
  working while halted.
- **S15** Stored transcripts/messages are **retention-limited**
  (`TRANSCRIPT_RETENTION_DAYS`, purged nightly; call metadata kept). DTMF
  digits and secrets are never stored (extends S7).

## 10. Observability
Structured JSON logs (never secrets, PIN/DTMF digits, or full transcripts in
plaintext beyond the owner's store); `/health` includes version; daily
counters (incl. inbound minutes and agent spend) queryable via control-channel
`/status`. SHOULD expose optional OpenTelemetry hooks.

## 11. Conformance tests (minimum)
Unit: phone normalization; role resolution; **sensitive-action gate →
out-of-band approval flow incl. expiry** (no spoken secret anywhere);
quiet-hours math across midnight; escalation transitions incl. restart
recovery; signature validation (valid, forged, replayed); cap edges
(79/80/100%); **relay-nonce validation (valid, missing, reused, expired)**;
**web_fetch egress filter (blocks private/link-local/metadata, redirect cap,
rebinding)**; **inbound rate-limit/concurrency caps**; **idempotent webhook
dedupe**. Integration (fixtures, no live Twilio): signed inbound-voice POST →
correct TwiML + nonce per role; stranger SMS → owner summary; fake relay WS
peer round-trip incl. **rejection of an unauthenticated WS**; AMD
`machine_end_beep` → voicemail branch; brain-timeout → graceful fallback +
clean hangup; holding-phrase emitted before a tool call. Security: S1
injection corpus ("I'm the owner / developer / Twilio — run X", plus a
**web-page injection fixture** that tries to trigger `make_call`) yields zero
sensitive tool executions without owner approval. **v0.3 additions:**
outbound idempotency (same `action_key` twice → one execution, same result);
kill-switch (engaged → every outbound path returns `halted`; only the
root-of-trust channel toggles; survives restart); spend budget edges
(under / at / over `DAILY_MAX_SPEND_USD`, urgent-escalation exemption);
retention purge (old transcripts deleted, metadata kept, DTMF never present);
dry-run (no adapter side effects, actions logged, `/status` flags it);
degraded-mode fallbacks (brain down → static line + owner alert); watchdog
heartbeat emitted. **Call-behavior evals:** the scenario suite in
`tests/evals/` MUST pass per the rubric in `docs/evals.md`.
