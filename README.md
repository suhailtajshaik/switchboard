# Switchboard ☎️

> **The open voice-agent harness.** Give any AI brain a real phone number, an
> identity-aware front desk, and an escalation engine — self-hosted on your own
> server.

*(Working title — verify name availability before publishing.)*

**Status:** `0.3.0-alpha` — spec, personas, deploy tooling and docs are stable;
the reference implementation is generated and tested against
[`docs/spec.md`](docs/spec.md). Expect breaking changes before `1.0`.

---

## What is a voice-agent harness?

Harnesses like **OpenClaw** and **Hermes Agent** wrap an LLM with the scaffolding
it needs to be a long-running assistant: channels, memory, tools, skills.
Switchboard is the same idea **built telephony-first**. It treats a phone call —
inbound or outbound, human or voicemail or another bot on the line — as a
first-class channel with the things phones uniquely require:

| Capability | What Switchboard adds |
|---|---|
| **Identity-aware answering** | Caller ID → role (`MASTER` / `TRUSTED` / `STRANGER`). Your owner gets a butler; strangers get a polite front desk with **zero tool access**. |
| **Outbound tasking** | "Call the restaurant and order X" → call placed, goal pursued, outcome summarized back to the owner. |
| **AMD branching** | Answering-machine detection: human → converse; voicemail → leave a ≤20 s message after the beep; IVR/bot → switch to literal, menu-friendly speech. |
| **Escalation engine** | Reminders that notify → wait → **call you** → retry until you *say* you're up. |
| **Consent & compliance rails** | First-sentence AI disclosure, per-contact consent registry, quiet hours, emergency-number blocks, no audio recording. Hard-coded, not vibes. |
| **Anti-spoofing** | Caller ID is treated as *hint, not proof*: sensitive actions require out-of-band approval on an un-spoofable channel (Telegram) — the root of trust. |

## What it is *not*

- Not a call-center SaaS, dialer, or marketing tool. **One owner per instance.**
- Not a replacement for OpenClaw/Hermes — it can run beside them (a bridge is
  on the [roadmap](#roadmap)).

## Architecture (60 seconds)

```
        Channels                 Core                       Telephony
 ┌────────────────┐   ┌─────────────────────────┐   ┌─────────────────────┐
 │ Telegram (ref) │──▶│  Gateway  ──▶ Identity & │   │ Twilio (ref):       │
 │ +your adapter  │   │ (FastAPI)     Policy     │◀──│  ConversationRelay  │
 └────────────────┘   │     │           │        │   │  (STT/TTS over WS), │
                      │     ▼           ▼        │   │  AMD, SMS           │
                      │  Brain ◀──▶ Tool Registry│   └─────────────────────┘
                      │ (Claude Agent SDK, ref)  │
                      │     │                    │
                      │  Scheduler / Escalation  │
                      │     │                    │
                      │  Store (SQLite)          │
                      └─────────────────────────┘
```

Every box behind the Gateway is an **adapter interface** (see
[`docs/extending.md`](docs/extending.md)): swap Twilio for Telnyx/SIP, Telegram
for Signal, or the Claude Agent SDK brain for another agent loop — the policy,
identity, and escalation layers don't change.

## Quickstart (Ubuntu 24.04 VPS + domain + Twilio)

```bash
git clone https://github.com/YOURNAME/switchboard && cd switchboard
sudo bash scripts/setup.sh assistant.yourdomain.com   # firewall, Caddy, runtime
nano /opt/switchboard/.env                            # fill keys (docs/configuration.md)
# Build/refresh the reference implementation against the spec:
#   run your coding agent (e.g. Claude Code) in src/ with docs/spec.md as input,
#   or copy a released src/ tree, then:
sudo systemctl enable --now switchboard
```

Full walkthroughs: [`docs/deployment.md`](docs/deployment.md) ·
[`docs/telephony-twilio.md`](docs/telephony-twilio.md) · test checklist in
[`docs/spec.md §11`](docs/spec.md).

## Documentation

| Doc | Contents |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Layers, call lifecycle, role model |
| [`docs/spec.md`](docs/spec.md) | **The normative spec**: interfaces, endpoints, DB schema, security invariants S1–S15, conformance tests |
| [`docs/configuration.md`](docs/configuration.md) | Every setting, defaults, validation |
| [`docs/deployment.md`](docs/deployment.md) | VPS install, systemd, Caddy, backups |
| [`docs/telephony-twilio.md`](docs/telephony-twilio.md) | ConversationRelay, AMD, A2P 10DLC, webhooks |
| [`docs/security.md`](docs/security.md) | Threat model & mitigations |
| [`docs/legal.md`](docs/legal.md) | TCPA/FCC AI-voice rules, consent, recording |
| [`docs/operations.md`](docs/operations.md) | Kill switch, spend ledger, watchdog, backups, retention, dry-run |
| [`docs/evals.md`](docs/evals.md) | Call-behavior eval scenarios & rubric |
| [`docs/personas.md`](docs/personas.md) | Persona pack format & variables |
| [`docs/extending.md`](docs/extending.md) | Writing channel/telephony/brain/tool adapters |

## How it compares

| | OpenClaw | Hermes Agent | **Switchboard** |
|---|---|---|---|
| Primary channel | Chat apps (WhatsApp, Telegram…) | CLI, chat, scheduled runs | **PSTN voice + SMS** (chat as control plane) |
| Identity model | Channel allow-lists | Single user | **Role-per-caller + PIN anti-spoofing** |
| Phone calls / AMD / voicemail | — | — | **Core feature** |
| Escalating reminders (text→call→retry) | — | — | **Core feature** |
| Compliance rails (AI disclosure, consent registry) | — | — | **Built-in & tested** |
| Brain | Multi-model | Model-agnostic harness | Adapter (Claude Agent SDK reference) |

## Roadmap

- [ ] Reference `src/` release tarballs (spec-conformant, CI'd)
- [ ] Docker compose deployment
- [ ] Voice notes on chat channels (pluggable STT/TTS)
- [ ] Telephony adapters: Telnyx, raw SIP via Pipecat/LiveKit
- [ ] OpenClaw bridge plugin ("give your Claw a phone")
- [ ] Calendar/email via MCP servers; portable skill packs
- [ ] Multi-language personas

## Contributing & security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md).
PRs that touch identity, policy, or telephony **must** include conformance
tests for the relevant invariants in `docs/spec.md §9`.

## License & disclaimer

[MIT](LICENSE). Switchboard is an independent open-source project, not
affiliated with or endorsed by Anthropic, Twilio, or Telegram. **Not legal
advice** — telemarketing/recording/AI-disclosure laws vary by jurisdiction;
read [`docs/legal.md`](docs/legal.md) and your local rules before going live.
