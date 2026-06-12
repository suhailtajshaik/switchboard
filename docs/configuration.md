# Configuration reference (v0.3)

All settings are environment variables (see `.env.example`). Required unless a
default is shown. The process fails fast at boot on invalid values and refuses
to start if webhook signature validation is disabled.

## Core
| Variable | Type / format | Default | Meaning |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | string | — | Brain credentials (reference brain: Claude Agent SDK) |
| `BRAIN_BASE_URL` | url | (Anthropic) | Optional: route the brain through an OpenAI/Anthropic-compatible gateway |
| `BRAIN_MODEL` | string | (provider default) | Conversational model. **Pick a low-latency model** — call feel depends on it (spec §7) |
| `TELEGRAM_BOT_TOKEN` | string | — | Control-channel bot (via @BotFather) |
| `TELEGRAM_OWNER_CHAT_ID` | int | — | The ONLY chat served; **root of trust** and the out-of-band approval channel |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` | string | — | API access; token also validates webhook signatures (S2) |
| `TWILIO_NUMBER` | E.164 | — | The assistant's phone number |
| `OWNER_NAME` | string | — | Used in personas |
| `OWNER_PHONE` | E.164 | — | Maps to role `MASTER` |
| `WHITELIST_PHONES` | CSV of E.164 | empty | Map to role `TRUSTED` |
| `PUBLIC_DOMAIN` | hostname | — | Public HTTPS/WSS host (Caddy) |
| `OWNER_TIMEZONE` | IANA tz | — | All scheduling & quiet-hours math |

## Policy / safety
| Variable | Type | Default | Meaning |
|---|---|---|---|
| `QUIET_HOURS_START` / `QUIET_HOURS_END` | hour 0–23 | 21 / 09 | No outbound calls to non-owner numbers in this window (wraps midnight) |
| `MAX_CALL_MINUTES` | int | 10 | Hard per-call limit |
| `DAILY_MAX_OUTBOUND_CALLS` | int | 15 | Outbound cap (S5) |
| `DAILY_MAX_SMS` | int | 30 | Outbound cap (S5) |
| `ESCALATION_WAIT_MINUTES` | int | 5 | Notify→call delay for `normal` urgency |
| `APPROVAL_TIMEOUT_MINUTES` | int | 5 | Out-of-band sensitive-action approval expiry (S3) |
| `SMS_ENABLED` | bool | false | Keep false until US A2P 10DLC approval; falls back to control channel |
| `DTMF_PIN` | digits | empty | **Optional** keypad second factor for convenience. Never the sole gate, never logged (S3). Leave empty to rely solely on out-of-band approval |

## Inbound abuse limits (S11) & reliability (§7)
| Variable | Type | Default | Meaning |
|---|---|---|---|
| `MAX_CONCURRENT_CALLS` | int | 2 | Global cap on simultaneous calls |
| `INBOUND_PER_NUMBER_COOLDOWN_SECONDS` | int | 60 | Min gap between accepted calls/SMS from one number |
| `DAILY_INBOUND_MINUTES` | int | 120 | Daily inbound-minutes budget; beyond it, decline/forward + alert owner |
| `BRAIN_RESPONSE_TIMEOUT_SECONDS` | int | 12 | Abort a stuck brain turn → graceful fallback line + clean hangup |
| `RELAY_NONCE_TTL_SECONDS` | int | 120 | Lifetime of the single-use relay-WS token (S9) |
| `DAILY_MAX_SPEND_USD` | float | 5.0 | Soft daily dollar budget across telephony+LLM; non-urgent outbound pauses at 100%, owner warned at 80% (see `docs/operations.md §2`) |
| `TRANSCRIPT_RETENTION_DAYS` | int | 90 | Nightly purge of transcripts/messages older than this; `0` = don't store transcripts (S15) |
| `DRY_RUN` | bool | false | Side-effecting adapters log instead of execute; `/status` flags it (rehearsal mode) |
| `BLOCKED_PREFIXES` | CSV | (built-in emergency + premium) | Numbers/prefixes `make_call` must refuse (S4) — extend per country |

**Removed in v0.2:** `VOICE_PIN`. A spoken password is transcribed and stored;
sensitive actions now use out-of-band approval (S3). If migrating from v0.1,
delete `VOICE_PIN` and set `APPROVAL_TIMEOUT_MINUTES` (and optionally
`DTMF_PIN`).

**Validation rules:** phone vars parse to E.164; `TELEGRAM_OWNER_CHAT_ID`
numeric; tz must exist; caps ≥1; the process refuses any "disable signature
check" setting.

**Changing config:** edit `.env`, then `systemctl restart switchboard`.
Personas hot-reload; config does not (deliberately — config is policy).
