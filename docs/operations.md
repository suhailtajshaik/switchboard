# Operations guide (v0.3)

Day-2 concerns: staying alive, staying cheap, and stopping fast. Normative
requirements live in `docs/spec.md`; this is the operator-facing detail.

## 1. Break-glass kill switch (S14)
- **`/halt <reason>`** on Telegram: instantly blocks all outbound calls/SMS
  and sensitive tool execution. Inbound strangers still get polite
  message-taking; reminders still notify on Telegram (no calls).
- **`/resume`** re-enables. Both commands work **only** from the owner chat.
- State persists in `runtime_flags` across restarts and shows at the top of
  `/status` as `⛔ HALTED (<reason>, <when>)`.
- Use it the moment anything feels off — it's free to engage, cheap to lift.

## 2. Spend ledger & daily budget
- Every call/SMS records an estimated cost (`est_cost_usd`): telephony
  minutes + relay/STT/TTS + LLM tokens (estimates are fine; bias high).
- `counters` accumulates per-day `spend_usd` buckets; `/status` shows
  *today: $X.XX of $BUDGET (calls $a · llm $b)*.
- `DAILY_MAX_SPEND_USD` is a **soft budget**: when reached, non-urgent
  outbound actions pause with reason `daily_spend_budget`; **urgent
  escalations to the owner are exempt**, and the owner can `/override` per
  action. 80% crossing pings the owner once (mirrors S5).
- Count caps (S5) and the dollar budget are independent — one long expensive
  call can't hide under a low call count.

## 3. Call review
- **`/calls [n]`** on Telegram: the last *n* (default 10) calls — direction,
  peer, AnsweredBy, duration, est. cost, outcome line.
- **`/call <id>`**: the stored transcript for one call (subject to retention).
You are reviewing what an agent said on your behalf; make it a habit early on.

## 4. Watchdog (hung-process protection)
- `deploy/switchboard.service` ships `Type=notify` + `WatchdogSec=60`
  (commented until `main.py` implements it — see spec §7): the app sends
  `sd_notify(READY=1)` at boot and `WATCHDOG=1` from the main loop every
  ≤25 s. A hung event loop then gets killed and restarted by systemd, which
  `Restart=always` alone cannot do.
- The heartbeat task SHOULD verify internals first (DB reachable, scheduler
  ticking) so a wedged subsystem stops the heartbeat on purpose.

## 5. Degraded modes (graceful outage behavior)
| Failure | Behavior |
|---|---|
| Brain (LLM API) down/timeout | Inbound stranger calls get a static line: "You've reached {OWNER}'s assistant — I can't take a detailed message right now; please send a text instead." Owner alerted once per incident on Telegram. Outbound tasks queue or fail loudly — never half-execute. |
| Telephony API errors | Owner alerted; affected task marked failed with reason; retry only where idempotent (S13). |
| Telegram (control channel) down | Log + retry with backoff; if `SMS_ENABLED`, SMS-alert the owner. Sensitive approvals simply expire (safe default: deny). |
| DB unwritable | Refuse new side-effecting work, heartbeat stops (watchdog restarts), loud logs. |

## 6. Backups (nightly, off-box)
- `scripts/backup.sh` runs `sqlite3 ... ".backup"` to
  `/opt/switchboard/data/backups/`, prunes local copies older than 14 days,
  and—if `BACKUP_REMOTE` is set (an `rclone` remote like
  `b2:my-bucket/switchboard`)—syncs off-box.
- Install (as root):
  `crontab -e` → `17 3 * * * /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1`
- Contacts + consent provenance are the unrecoverable data; test a restore
  once (`sqlite3 backup.db ".tables"`).

## 7. Transcript retention & PII minimization (S15)
- Nightly purge deletes `messages` rows and `calls.transcript` older than
  `TRANSCRIPT_RETENTION_DAYS` (default 90); call metadata (who/when/outcome/
  cost) is kept. Set lower if you're privacy-sensitive; `0` disables storing
  transcripts at all.
- Never stored regardless of setting: DTMF digits, secrets, audio (S7).

## 8. Consent provenance
`add_contact` records *how and when* consent for AI calls was given:
`consent_method` (`verbal` / `text` / `in_person` / `owner_attested`),
`consent_at`, optional `consent_note` ("asked at dinner 2026-06-10").
If a call is ever questioned, you can answer "they agreed, here's when."

## 9. Dry-run mode
`DRY_RUN=true` → adapters log intended calls/SMS (target, persona, brief,
est. cost) without executing; Telegram replies are prefixed `🧪 DRY-RUN`;
`/status` shows it in the first line. Rehearse the full loop — reminders,
escalation, approvals — before the first real dial.
