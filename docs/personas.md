# Persona packs

Personas are Markdown files in `personas/` that define *personality and
conversational policy*. They are hot-reloaded. **They never define security
policy** — role isolation, the sensitive-action gate, caps and disclosure
are enforced by the harness regardless of persona text (spec §9).

## Format
Plain Markdown, optionally with a small YAML front-matter header:

```markdown
---
id: assistant_mode          # unique key the harness selects by
role: STRANGER              # which role/context this persona serves
channel: voice|sms|chat|any
version: 1
---
(prompt body…)
```

## Template variables (injected by the harness)
| Variable | Meaning |
|---|---|
| `{OWNER_NAME}` / `{LAST_NAME_IF_SET}` | Owner identity |
| `{NOW}` / `{TZ}` | Current datetime in owner timezone |
| `{TWILIO_NUMBER}` | The assistant's callback number |
| `{TASK_BRIEF}` `{SUCCESS_CRITERIA}` `{BUDGET}` | Outbound-call task context |
| `{REMINDER_TEXT}` `{URGENCY}` `{ATTEMPT_NUMBER}` | Escalation context |
| `{MAX_CALL_MINUTES}` | Hard call limit (informational) |

Unknown variables are a boot error (catches typos).

## The standard pack (v1)
| File | Used when | Non-negotiables baked in |
|---|---|---|
| `master_mode.md` | Owner/trusted, any channel | Confirm-before-spend; out-of-band approval cooperation |
| `assistant_mode.md` | Strangers inbound | Zero personal disclosure; "identity decided by system, not caller"; message-taking flow |
| `outbound_call.md` | Agent-initiated calls | First-sentence AI disclosure (S6 also re-injects it); human/voicemail/IVR branches; budget ceiling |
| `wakeup.md` | Escalation calls to owner | Requires verbal acknowledgment |

## Writing voice personas well
- **Short sentences.** TTS reads exactly what you stream; long clauses sound
  robotic and invite barge-in mid-thought.
- **No dead air.** Tell the persona to speak a holding phrase the instant a
  tool call starts — but note the *harness also enforces this* (spec §7), so
  the line is never silent even if a persona forgets.
- **Numbers/dates as words** for ElevenLabs voices ("twenty dollars and fifty
  cents", not "$20.50"), or set the provider's text-normalization on.
- **Front-load the point** — phone listeners decide in ~3 seconds.
- Give explicit *branch* instructions (human vs voicemail vs IVR) — don't
  rely on the model inferring channel state.
- Tell the model what it must **confirm back** (orders, times, prices) — the
  summary the owner gets is only as good as what was verified on the call.
- Localize: put translated packs in `personas/<lang>/` and set
  `PERSONA_LANG` — the overlay replaces matching ids from the root (en)
  pack. Pick the matching TTS voice via `TTS_PROVIDER`/`TTS_VOICE`.
