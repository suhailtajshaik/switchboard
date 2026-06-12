# Architecture

## 1. Design principles
1. **Telephony-first.** Phone calls are streaming, interruptible,
   identity-rich and legally regulated; the harness is shaped around that,
   with chat as the control plane.
2. **One owner per instance.** A *personal* agent, like OpenClaw/Hermes.
   Multi-tenancy is out of scope (it changes the whole threat model).
3. **Spec-first, adapter-based.** `docs/spec.md` is normative. Telephony,
   channels, the brain, and storage sit behind small interfaces
   (`docs/extending.md`) so providers can be swapped.
4. **Policy in code; the model is never the security boundary.** Role
   isolation, sensitive-action approval, disclosure, caps, blocked numbers
   and WS auth are enforced by the harness regardless of what the LLM does.

## 2. Layers
```
┌──────────────────────── Gateway (HTTP/WS) ─────────────────────────┐
│ webhook signature (S2) · relay-nonce check (S9) · idempotency (S12)│
│ inbound rate limits (S11) · request parsing · session lookup       │
└──────┬───────────────────────────────────────────────┬────────────┘
       ▼                                               ▼
┌─ Identity & Policy ─────────┐            ┌─ Telephony Adapter ──────┐
│ phone→role (caller-ID=hint) │            │ place_call / TwiML+nonce │
│ sensitive-action gate →     │            │ relay WS / AMD events    │
│   out-of-band approval (S3) │            └──────────────────────────┘
│ consent · quiet hours · caps│
└──────┬──────────────────────┘
       ▼
┌─ Brain Adapter ─────────────┐   ┌─ Tool Registry (role-filtered) ──┐
│ persona+context → tokens    │◀─▶│ make_call, reminders, contacts,  │
│ (ref: Claude Agent SDK)     │   │ take_message, web_search/fetch*  │
│ holding-phrase on tool call │   │ *egress-filtered; NO shell (S8)  │
└──────┬──────────────────────┘   └──────────────────────────────────┘
       ▼
┌─ Scheduler/Escalation ─┐  ┌─ Store (SQLite, WAL) ─┐  ┌─ Channels ──┐
│ notify→wait→call→retry │  │ + pending_approvals,  │  │ Telegram    │
│ (persisted, spec §6)   │  │ relay_nonces, events  │  │ (ref)       │
└────────────────────────┘  └───────────────────────┘  └─────────────┘
```

## 3. Role & trust model

| Role | Established by | Capabilities |
|---|---|---|
| `MASTER` | `OWNER_PHONE`, owner Telegram chat id | Full toolset. Sensitive actions over **phone/SMS** need out-of-band Telegram approval (S3); over Telegram they don't (root of trust) |
| `TRUSTED` | `WHITELIST_PHONES` | Configurable subset; same sensitive-action gate |
| `STRANGER` | everyone else | **`take_message` only** (S1); all input is data, never instructions |

**Trust ladder:** owner Telegram (un-spoofable) > caller-ID match > anonymous.
Caller ID is a routing hint; it never authorizes a sensitive action by itself.

## 4. Authenticating a phone call (two checks)
1. **Inbound webhook** `/twilio/voice` is signature-validated (S2). The
   harness then mints a **single-use relay nonce** bound to the CallSid and
   embeds it in the `wss://…/twilio/relay?token=…` URL it returns in TwiML.
2. **Relay WS connect** validates that nonce (unused, unexpired, matches a
   live CallSid) before accepting the socket (S9). This closes the otherwise
   open WebSocket endpoint.

## 5. Sensitive-action flow (anti-spoofing, no spoken secret)
```
phone caller: "add +1555… to the whitelist"
   policy: sensitive + phone channel  ──▶ create pending_approval
   harness → Telegram(owner): "Approve: add +1555… to whitelist? [yes/no]"
   caller hears: "I've sent that to Suhail to approve."
   owner taps yes  ──▶ action executes; deny/expiry(5m) ──▶ dropped
```

## 6. Call hot path (latency budget, §7 of spec)
```
caller speech ─STT(Twilio)─▶ relay WS ─▶ brain(LLM) ═tokens═▶ relay WS ─TTS─▶ caller
                                   ▲ holding phrase emitted the instant a tool call starts
```
Rules: stream tokens (don't await full completion); never block the event
loop (async LLM/REST/DB, SQLite WAL); barge-in interruptible; brain turn that
exceeds `BRAIN_RESPONSE_TIMEOUT_SECONDS` → graceful fallback line + clean
hangup, never silence; pick a low-latency conversational model.

## 7. Sessions & memory
One brain session per `(channel, peer)` with a bounded rolling window
persisted in the store; call sessions also carry live state (nonce, AMD
result, elapsed time, persona, task brief). Long-term memory (preferences,
contacts) lives in the store and is injected via prompt variables — keeping
the brain adapter swappable.
