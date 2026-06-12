# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

Switchboard is a self-hosted, **telephony-first voice-agent harness**: Twilio
ConversationRelay (voice/SMS, text-in/text-out over WebSocket) + Telegram
(control channel and root of trust) + a swappable LLM brain (reference:
Claude Agent SDK). Python ≥3.12, FastAPI, SQLite (WAL), single asyncio
process, one owner per instance.

**Spec-first, deliberately partial.** `docs/spec.md` is normative — code
conforms to it, never the reverse. `src/` today contains only the pure,
unit-testable core (`core/`: config, identity, policy, phones, personas,
escalation, store; `adapters/twilio_signature.py`), with unit conformance
suites in `tests/` (run in CI). Everything else — `main.py`, the FastAPI
gateway + relay WS, the Telegram/Twilio-REST/brain adapters, the
integration fixtures (fake relay WS peer, recorded signed webhooks), the
eval runner — is meant to be **generated against the spec** (typically on
the deployment host) and proven with the conformance tests. **Read
`src/README.md` first**: it lists exactly what exists, what's missing, and
the expected final layout.

Version `0.1.0-alpha` — first version; nothing released or deployed yet.
CI (`.github/workflows/ci.yml`) runs `ruff check src tests` + `pytest
tests/` on pushes to master/development and on PRs. If a doc's "§N" pointer
ever disagrees with `docs/spec.md`'s actual headings, **the spec wins**
(security invariants S1–S15 in §9, conformance tests in §11).

## Commands

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements-dev.txt      # pytest + ruff — all the core
                                             # suite needs (it is stdlib-only)
pip install -r src/requirements.txt          # runtime deps (pinned); only
                                             # needed for adapters/gateway work

pytest tests/                                # all conformance tests
pytest tests/test_policy.py -k quiet_hours   # one file / one test
ruff check src tests                         # lint (what CI runs)
```

Tests run **without any live credentials**: telephony is exercised via
recorded webhook fixtures (signed + forged) and a fake ConversationRelay WS
peer; the brain is a scripted adapter. Call-behavior evals
(`tests/evals/*.yaml`) boot the app with `DRY_RUN=true` and score transcripts
against the hard-check rubric in `docs/evals.md`; hard checks gate, soft
LLM-judge scores never do.

## Architecture

```
Telegram poller ─▶ Gateway (FastAPI, 127.0.0.1:8080 behind Caddy TLS)
Twilio webhooks ─▶   S2 signature → role lookup → mint relay nonce → TwiML
relay WS (token) ─▶  Identity & Policy ─▶ Brain (role-filtered ToolSet)
                          │                   │ streams tokens back to TTS
                     Scheduler/Escalation     │ holding phrase on tool calls
                          └── Store (SQLite WAL) ──┘
```

- **Roles:** `OWNER_PHONE`→`MASTER`, `WHITELIST_PHONES`→`TRUSTED`, everyone
  else `STRANGER` (gets `take_message` only — S1). Caller ID is a routing
  hint, **never** authentication.
- **Sensitive actions** requested over phone/SMS are held for **out-of-band
  approval** on the owner's Telegram (expires, default 5 min). No secret is
  ever spoken or transcribed — there is deliberately no `VOICE_PIN`; never
  introduce voice-spoken auth (spec §2.1 forbids it).
- **Policy engine is the only path to side-effecting tools** (`core/policy.py`:
  capability table, `ApprovalGate`, `KillSwitch`, `spend_check`,
  `make_action_key`). The brain only ever *sees* tools its role allows. The
  model is never the security boundary.
- **Relay WS auth (S9):** single-use, CallSid-bound, short-TTL nonce minted
  when TwiML is emitted; reject missing/reused/expired tokens.
- **Call hot path (spec §7):** stream tokens (never await full completions);
  harness emits a holding phrase the instant any tool call starts; barge-in
  interruptible; brain turn over `BRAIN_RESPONSE_TIMEOUT_SECONDS` → fallback
  line + clean hangup. No synchronous I/O in the event loop.
- **Adapters** (Protocols in `docs/extending.md`): Channel, Telephony, Brain,
  Tools. Adapters move data; the core decides. No policy decisions in
  adapters, no cross-adapter imports.
- **Config** is env-only (`docs/configuration.md`), fail-fast at boot;
  signature validation cannot be disabled (boot refuses). Personas
  (`personas/*.md`) hot-reload; config changes need a service restart.

## Rules that govern changes

- Behavior changes start as a PR to `docs/spec.md`; code follows.
- Security invariants **S1–S15** (spec §9) are conformance-critical. PRs
  touching identity, policy, telephony, or tool exposure must keep them green
  and extend the conformance tests. Harness-enforced non-negotiables: no
  shell/file-exec tools for the brain (S8), non-removable first-sentence AI
  disclosure on outbound calls (S6), emergency/premium numbers unreachable
  (S4), `/halt`–`/resume` kill switch owner-only (S14), no audio recording
  (S7).
- Persona or call-loop changes must keep `tests/evals/` green; bug fixes
  should add a regression scenario.
- Conventional Commits; update `CHANGELOG.md`, and `docs/` +
  `.env.example` whenever config changes.

## Installing on a VPS or Raspberry Pi

Target: **Ubuntu 24.04 LTS**, public IPv4, domain A record → host (if
Cloudflare: **DNS-only/grey** — the relay WebSocket needs a direct
connection), ports 80/443 reachable. Details: `docs/deployment.md`.

Automatable end-to-end on the host (Claude Code can run all of this):

```bash
git clone <repo> && cd switchboard
sudo bash scripts/setup.sh assistant.yourdomain.com
# idempotent: updates+unattended-upgrades, UFW(22/80/443)+fail2ban, Node 22 +
# Claude Code, Caddy auto-HTTPS, `switchboard` user, /opt/switchboard/
# {app,personas,workspace,data}, venv with pinned deps, .env (chmod 600),
# systemd unit installed (not started)

# Provide src/ in /opt/switchboard/app: copy a released tree, or generate the
# missing pieces there against docs/spec.md + docs/configuration.md and
# iterate until pytest (spec §11) is green.

sudo nano /opt/switchboard/.env            # human-supplied values, see below
sudo cp -r personas/* /opt/switchboard/personas/
sudo systemctl enable --now switchboard
journalctl -u switchboard -f               # structured JSON logs
curl https://assistant.yourdomain.com/health
```

First run: set `DRY_RUN=true`, rehearse reminder → escalation → approval →
"call" on Telegram, check `/status` and `/calls`, test `/halt` + `/resume`,
then flip it off and restart. Backups: root crontab
`17 3 * * * /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1`
(optional off-box via `BACKUP_REMOTE` rclone remote).

**Raspberry Pi notes** — `scripts/setup.sh` is plain apt + systemd and runs
unmodified on arm64:

- Use a **64-bit OS with Python ≥3.12**: Ubuntu Server 24.04 LTS (arm64,
  official Pi images) is the no-surprises choice. Raspberry Pi OS qualifies
  only on Debian-13/trixie builds (Python 3.13); bookworm ships 3.11 — too
  old. NodeSource (Node 22) and Caddy publish arm64 packages; 32-bit armhf
  is not supported. Pi 4/5 with ≥4 GB is ample.
- Claude Code on Pi arm64: the npm route `setup.sh` already uses
  (`npm install -g @anthropic-ai/claude-code`) works; the native
  `claude.ai/install.sh` installer does not on Pi — don't switch to it.
- Home NAT: forward ports 80/443 to the Pi and point the domain at your
  public IP (DDNS if dynamic). Twilio webhooks and Caddy's certificate
  issuance must reach the Pi directly; Cloudflare orange-cloud breaks the
  relay WS.
- The SQLite DB lives on the SD card — keep the backup cron; a USB-SSD is
  kinder for longevity.

## Human actions required (one-time accounts & consoles)

None of this is scriptable from the host shell. A **browser agent can drive
every console flow below**; the human must handle payments, phone/identity
verification, 2FA, and legal acceptances. The fully ordered end-to-end
walkthrough with per-step `[human]` / `[browser-agent OK]` / `[server]` tags
is **`docs/setup-checklist.md`**; Twilio detail: `docs/telephony-twilio.md`.

| # | Action | Where | Yields (.env) |
|---|--------|-------|---------------|
| 1 | Create VPS (2 vCPU/4 GB, Ubuntu 24.04, SSH key) — or prep the Pi | provider console | host |
| 2 | A record `assistant.yourdomain.com` → host IP (Cloudflare: grey/DNS-only) | DNS provider | `PUBLIC_DOMAIN` |
| 3 | Create API key; set a monthly spend cap | console.anthropic.com | `ANTHROPIC_API_KEY` |
| 4 | @BotFather → `/newbot` | Telegram | `TELEGRAM_BOT_TOKEN` |
| 5 | Message the new bot once, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and read `chat.id` | browser | `TELEGRAM_OWNER_CHAT_ID` |
| 6 | Twilio sign-up → **upgrade to paid** (trial only reaches verified numbers) | console.twilio.com | — |
| 7 | Buy a local number with **Voice + SMS** | Console → Phone Numbers → Buy a number | `TWILIO_NUMBER` |
| 8 | Accept the **"Predictive and Generative AI/ML Features Addendum"** — ConversationRelay won't run without it | Console → Voice → Settings → General | — |
| 9 | Geo Permissions: enable only countries you'll call; set a low-balance billing alert | Console → Voice → Geo Permissions; Billing | — |
| 10 | Copy Account SID + Auth Token | Console dashboard | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` |
| 11 | **After the service is live**, wire the number's webhooks: Voice "A call comes in" → `POST https://$PUBLIC_DOMAIN/twilio/voice` · "Call status changes" → `/twilio/status` · Messaging "A message comes in" → `/twilio/sms` (AMD callback is set per-call by the harness) | Console → Phone Numbers → Active numbers | — |
| 12 | US SMS only: **A2P 10DLC** Sole-Proprietor registration (≈$4.50 brand + $15 campaign one-time, ~$2/mo, approval ~10–15 days). Keep `SMS_ENABLED=false` until approved — SMS auto-degrades to Telegram | Console → Messaging → Regulatory Compliance | `SMS_ENABLED` |
| 13 | Fill the personal facts: `OWNER_NAME`, `OWNER_PHONE`, `OWNER_TIMEZONE`, optional `WHITELIST_PHONES` | `/opt/switchboard/.env` | — |
| 14 | Read `docs/legal.md` for your jurisdiction; record consent before the agent calls any individual | — | — |

Post-setup gotchas (`docs/telephony-twilio.md §5`): webhook **403** = signature
validated against the wrong public URL or wrong auth token; call connects then
**silence** = AI/ML addendum not accepted or `wss://` unreachable (Cloudflare
proxying, firewall, Caddy down); US SMS silently dropped = 10DLC still
pending.
