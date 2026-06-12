# Setup checklist (end-to-end)

Single ordered walkthrough for a brand-new Switchboard operator. Follow
top-to-bottom; every step is tagged:

- `[human]` — payment, identity/phone verification, 2FA, accepting legal
  terms, physical hardware prep. Must be done by the person.
- `[browser-agent OK]` — console navigation, form filling, copying values,
  webhook wiring. A browser agent (e.g. Claude in Chrome) can drive these on
  your behalf.
- `[server]` — shell commands on the host. A coding agent (e.g. Claude Code)
  can run these.

Where a step yields a credential, the exact `.env` variable name it fills is
shown in **bold**. Paste all secrets into `/opt/switchboard/.env` (chmod 600
— never into chat logs or commits).

---

## Phase 1 — Host

### Option A: VPS

- [ ] [human] Create a VPS at your cloud provider: **2 vCPU / 4 GB RAM**,
  **Ubuntu 24.04 LTS**, public IPv4, SSH-key login (no password auth).
- [ ] [human] Note the public IPv4 — you will need it for the DNS A record in
  Phase 2.

### Option B: Raspberry Pi (instead of VPS)

- [ ] [human] Flash **Ubuntu Server 24.04 LTS arm64** onto a Pi 4 or Pi 5
  with ≥ 4 GB RAM. (Raspberry Pi OS bookworm ships Python 3.11, which is too
  old; use Ubuntu.)
- [ ] [human] On your home router, forward ports **80** and **443** to the
  Pi's LAN IP. If your ISP assigns a dynamic public IP, configure a DDNS
  service and note the DDNS hostname.
- [ ] [human] Enable SSH-key login; confirm the Pi boots and is reachable over
  SSH from outside the LAN.

> Raspberry Pi note: `scripts/setup.sh` is plain apt + systemd and runs
> unmodified on arm64. The SQLite DB lives on the SD card — keep the backup
> cron (Phase 9) and consider a USB SSD for longevity.

---

## Phase 2 — DNS

- [ ] [browser-agent OK] At your DNS provider, create an **A record**:
  `assistant.yourdomain.com` → the host's public IPv4 (or DDNS hostname via
  CNAME if dynamic).
- [ ] [browser-agent OK] If using **Cloudflare**: set the record to
  **DNS-only / grey-cloud** (proxy disabled). The ConversationRelay WebSocket
  (`wss://`) requires a direct connection to the host; the orange-cloud proxy
  breaks it.
- [ ] [server] Confirm DNS propagation:
  ```bash
  dig +short assistant.yourdomain.com
  ```
  The output must be your host IP before you proceed to Phase 6.

  Fills **`PUBLIC_DOMAIN`** = `assistant.yourdomain.com` (recorded now,
  entered into `.env` in Phase 6).

---

## Phase 3 — Anthropic API key

- [ ] [browser-agent OK] Open https://console.anthropic.com and sign in (or
  create an account).
- [ ] [human] Complete any identity verification or 2FA the console requires.
- [ ] [browser-agent OK] Navigate to **API Keys** → **Create key**. Name it
  (e.g. `switchboard-prod`). Copy the key immediately — it is shown only once.
- [ ] [browser-agent OK] In the console, set a **monthly spend cap** at a
  level you are comfortable with (Billing → Usage limits).
- [ ] [server] Paste the key into `/opt/switchboard/.env` (Phase 6 creates
  this file; keep the value ready until then):

  Fills **`ANTHROPIC_API_KEY`**.

---

## Phase 4 — Telegram bot

- [ ] [browser-agent OK] In Telegram, open a chat with **@BotFather** and send
  `/newbot`. Follow the prompts to choose a name and username.
- [ ] [browser-agent OK] BotFather replies with a token of the form
  `123456789:AAF...`. Copy it.

  Fills **`TELEGRAM_BOT_TOKEN`**.

- [ ] [human] Send **any message** to your new bot (e.g. "hello") — this
  creates the chat so the next step can read it.
- [ ] [browser-agent OK] Open in a browser:
  ```
  https://api.telegram.org/bot<TOKEN>/getUpdates
  ```
  (Replace `<TOKEN>` with the token above.) In the JSON response, find
  `result[0].message.chat.id`. It is a plain integer, possibly negative for
  group chats.

  Fills **`TELEGRAM_OWNER_CHAT_ID`**.

> This chat ID is the root of trust for the entire system — the only chat that
> can issue `/halt`, `/resume`, and sensitive approvals. Keep it secret.

---

## Phase 5 — Twilio

Full detail and protocol notes: [`telephony-twilio.md`](telephony-twilio.md).

### 5.1 Account creation and upgrade

- [ ] [browser-agent OK] Open https://console.twilio.com and sign up for a new
  account (or sign in to an existing one).
- [ ] [human] Complete phone-number verification and any identity steps Twilio
  requires.
- [ ] [human] **Upgrade to a paid account** (Billing → Upgrade). Trial accounts
  can only reach verified numbers and inject a trial message into every call —
  they cannot run Switchboard in production.
- [ ] [human] Set a **low-balance email alert** (Billing → Balance alerts) so
  you are warned before the account runs dry and calls start failing.

### 5.2 Buy a phone number

- [ ] [browser-agent OK] Navigate to **Phone Numbers → Manage → Buy a number**.
  Search for a local number with both **Voice** and **SMS** capabilities. Buy
  it.

  Fills **`TWILIO_NUMBER`** (copy the number in E.164 format, e.g.
  `+15550000000`).

### 5.3 Accept the AI/ML features addendum

- [ ] [human] Navigate to **Voice → Settings → General**. Find
  **"Predictive and Generative AI/ML Features Addendum"** and accept it.
  ConversationRelay will not run without this acceptance; calls will connect
  then stay silent.

  Onboarding guide:
  https://www.twilio.com/docs/voice/conversationrelay/onboarding

### 5.4 Geo permissions and fraud protection

- [ ] [browser-agent OK] Navigate to **Voice → Geo Permissions**. Enable only
  the countries you will call. Disable all others. This limits toll-fraud
  exposure if credentials are ever compromised.

### 5.5 Copy credentials

- [ ] [browser-agent OK] From the **Console Dashboard**, copy:
  - **Account SID** (starts with `AC`)
  - **Auth Token** (click the eye icon to reveal)

  Fills **`TWILIO_ACCOUNT_SID`** and **`TWILIO_AUTH_TOKEN`**.

  > The Auth Token is also used to validate webhook signatures (security
  > invariant S2). Keep it secret; rotate it at the console if leaked and
  > update `.env` immediately.

### 5.6 US SMS — A2P 10DLC registration (US only, optional)

Skip this sub-phase if you are outside the US or do not plan to send SMS.
Keep `SMS_ENABLED=false` until registration completes; the harness
automatically degrades SMS notifications to the Telegram control channel.

- [ ] [browser-agent OK] Navigate to **Messaging → Regulatory Compliance →
  A2P 10DLC**.
- [ ] [human] Register as a **Sole Proprietor** brand (individuals without an
  EIN use this tier; hobbyist use is allowed). Submit a campaign with an honest
  description such as "personal assistant notifications and replies."
  Costs approximately $4.50 brand + $15 campaign vetting one-time, plus
  approximately $2/month; approval typically takes 10–15 days. Do not flip
  `SMS_ENABLED=true` until the campaign status shows approved.

  Quickstart:
  https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/quickstart

  When approved, set **`SMS_ENABLED=true`** in `.env` and restart the service.

---

## Phase 6 — Server bootstrap

Perform these steps on the host (SSH in as a user with sudo).

### 6.1 Clone and run the bootstrap script

- [ ] [server]
  ```bash
  git clone https://github.com/YOURNAME/switchboard
  cd switchboard
  sudo bash scripts/setup.sh assistant.yourdomain.com
  ```
  Replace `assistant.yourdomain.com` with your actual domain from Phase 2.

  The script is idempotent. It performs: system updates and unattended security
  upgrades; UFW (ports 22/80/443 only) and fail2ban; Node.js 22 (Agent SDK /
  Claude Code dependency); Caddy with automatic HTTPS; a dedicated non-root
  `switchboard` user; Python venv with pinned dependencies; directory layout
  under `/opt/switchboard/{app,personas,workspace,data}`; `.env` copied from
  `.env.example` (chmod 600); systemd unit installed but not started.

### 6.2 Provide the application code

The `src/` directory must be present in `/opt/switchboard/app` before starting
the service. Two options — see [`deployment.md`](deployment.md) for detail:

- [ ] [server] **Option A (release):** copy a released, CI-tested `src/` tree
  into `/opt/switchboard/app`.
- [ ] [server] **Option B (generate):** run a coding agent (e.g. `claude` from
  Claude Code) in `/opt/switchboard/app` with `docs/spec.md` and
  `docs/configuration.md` as instructions, then run the conformance tests
  (`pytest tests/`) until green.

### 6.3 Fill the .env file

- [ ] [server] Open the config file:
  ```bash
  sudo nano /opt/switchboard/.env
  ```
  Fill every required variable. The table below maps each variable to the phase
  where you collected its value:

  | Variable | Phase | Notes |
  |---|---|---|
  | `ANTHROPIC_API_KEY` | 3 | Brain credentials |
  | `TELEGRAM_BOT_TOKEN` | 4 | Control-channel bot |
  | `TELEGRAM_OWNER_CHAT_ID` | 4 | Integer; root of trust |
  | `TWILIO_ACCOUNT_SID` | 5.5 | Starts with `AC` |
  | `TWILIO_AUTH_TOKEN` | 5.5 | Also validates webhook signatures |
  | `TWILIO_NUMBER` | 5.2 | E.164 format, e.g. `+15550000000` |
  | `PUBLIC_DOMAIN` | 2 | Hostname only, no scheme |
  | `OWNER_NAME` | — | Your name, used in personas |
  | `OWNER_PHONE` | — | Your phone in E.164; maps to role `MASTER` |
  | `OWNER_TIMEZONE` | — | IANA tz string, e.g. `America/New_York` |
  | `WHITELIST_PHONES` | — | Optional CSV of E.164; maps to role `TRUSTED` |
  | `DRY_RUN` | — | Set `true` for rehearsal; flip `false` in Phase 8 |

  Leave policy/safety variables at their defaults for now (see
  [`configuration.md`](configuration.md) for all options). Ensure the file
  remains chmod 600:
  ```bash
  sudo chmod 600 /opt/switchboard/.env
  sudo chown switchboard:switchboard /opt/switchboard/.env
  ```

### 6.4 Copy personas and enable the service

- [ ] [server]
  ```bash
  sudo cp -r personas/* /opt/switchboard/personas/
  sudo systemctl enable --now switchboard
  ```

- [ ] [server] Confirm the service started cleanly:
  ```bash
  journalctl -u switchboard -f
  ```
  Look for a log line indicating the FastAPI app is listening. Press Ctrl-C
  when satisfied.

- [ ] [server] Confirm Caddy obtained a TLS certificate and the health endpoint
  responds:
  ```bash
  curl https://assistant.yourdomain.com/health
  ```
  Expected: HTTP 200 with a JSON body. If you get a TLS error, Caddy has not
  yet obtained the certificate — wait a minute and retry. If you get
  connection refused, check `journalctl -u caddy` and UFW rules.

---

## Phase 7 — Twilio webhook wiring

**Do this after the service is live and `/health` returns 200.** Twilio will
attempt to reach the URLs immediately on save; they must be reachable.

Full field reference: [`telephony-twilio.md §3`](telephony-twilio.md#3-webhook-wiring-phone-numbers--active-numbers--your-number).

- [ ] [browser-agent OK] In the Twilio Console, navigate to **Phone Numbers →
  Manage → Active numbers** and click your number.

- [ ] [browser-agent OK] Under **Voice Configuration**, set:

  | Field | Value |
  |---|---|
  | "A call comes in" | Webhook — `https://<PUBLIC_DOMAIN>/twilio/voice` — HTTP POST |
  | "Call status changes" | `https://<PUBLIC_DOMAIN>/twilio/status` — HTTP POST |

- [ ] [browser-agent OK] Under **Messaging Configuration**, set:

  | Field | Value |
  |---|---|
  | "A message comes in" | Webhook — `https://<PUBLIC_DOMAIN>/twilio/sms` — HTTP POST |

  Replace `<PUBLIC_DOMAIN>` with the exact value from your `.env` (e.g.
  `assistant.yourdomain.com`). The URL scheme must be `https://`; the path
  must match exactly. A mismatch here is the most common cause of 403 errors.

- [ ] [browser-agent OK] Save the configuration. Twilio will make a test
  request; if it fails, check that `/health` is reachable from the public
  internet before debugging further.

  > The AMD callback URL is supplied per-call by the harness — leave it blank
  > here.

---

## Phase 8 — Verification and rehearsal

### 8.1 Basic health check

- [ ] [server]
  ```bash
  curl -s https://assistant.yourdomain.com/health | python3 -m json.tool
  ```
  Confirm the response is well-formed JSON and shows no error fields.

- [ ] [server] Check for warnings or errors in the first minutes of operation:
  ```bash
  journalctl -u switchboard --since "10 minutes ago"
  ```

### 8.2 Dry-run rehearsal

Ensure `DRY_RUN=true` is set in `/opt/switchboard/.env` (it was set in
Phase 6.3). Restart if needed:

```bash
sudo systemctl restart switchboard
```

- [ ] [human] On Telegram, send `/status` to the bot. Confirm the reply
  includes a dry-run indicator and shows today's counters at zero.

- [ ] [human] Trigger a test reminder through the bot or scheduler so the
  harness runs the full loop: **reminder → escalation → approval → "call"**
  (in dry-run mode no real call is placed; the adapter logs the intent).

- [ ] [human] Send `/calls` to the bot. Confirm the rehearsal call appears in
  the list with direction, peer, and estimated cost.

- [ ] [human] Test the kill switch:
  - Send `/halt test` to the bot.
  - Confirm `/status` shows `HALTED`.
  - Send `/resume`.
  - Confirm `/status` shows normal.

### 8.3 Go live

- [ ] [server] Set `DRY_RUN=false` in `/opt/switchboard/.env`:
  ```bash
  sudo sed -i 's/^DRY_RUN=true/DRY_RUN=false/' /opt/switchboard/.env
  sudo systemctl restart switchboard
  ```

- [ ] [human] Send `/status` to the bot and confirm dry-run is no longer
  shown.

- [ ] [human] Make a test call to the Twilio number from your own phone
  (`OWNER_PHONE`). The agent should answer, identify itself, and handle a
  short conversation. Check `/calls` for the transcript.

---

## Phase 9 — Day-2 operations

### 9.1 Backup crontab

- [ ] [server] Install the nightly backup job (as root):
  ```bash
  sudo crontab -e
  ```
  Add the line:
  ```
  17 3 * * * /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1
  ```
  This backs up the SQLite database to
  `/opt/switchboard/data/backups/`, pruning local copies older than 14 days.
  Contacts and consent provenance are the data that cannot be reconstructed —
  test a restore once with `sqlite3 backup.db ".tables"`.

  Full detail: [`operations.md §6`](operations.md#6-backups-nightly-off-box).

### 9.2 Off-box backup (optional)

- [ ] [server] If you want off-box copies, install `rclone`, configure a
  remote (e.g. `b2:my-bucket/switchboard`), and pass it on the cron line —
  `backup.sh` reads `BACKUP_REMOTE` from its own environment, and the root
  cron job does not read `/opt/switchboard/.env`:
  ```
  17 3 * * * BACKUP_REMOTE=b2:my-bucket/switchboard /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1
  ```

### 9.3 Legal and consent reminder

- [ ] [human] Read [`legal.md §1–§2`](legal.md) for your jurisdiction before
  the agent calls any individual. Key points:
  - The harness enforces an AI-disclosure sentence on every outbound call
    (non-removable; TCPA and several state laws require it).
  - The consent registry (`consented_to_ai_calls` on contacts) must be
    populated before the agent calls any person. Record consent in
    `add_contact` with `consent_method` and `consent_note`.
  - Never use the harness for marketing, cold-calling, or repeated unwanted
    contact.

---

## Troubleshooting

The three most common post-setup issues (from
[`telephony-twilio.md §5`](telephony-twilio.md#5-known-gotchas)):

**403 errors on webhooks**
The signature Twilio sends is computed against the exact public URL it called.
If the URL in your webhook settings does not match the URL Caddy exposes (wrong
scheme, extra slash, trailing path difference) or if `TWILIO_AUTH_TOKEN` in
`.env` does not match the token shown in the Twilio console, every request will
return 403. Fix: copy the URL from your `.env` `PUBLIC_DOMAIN` exactly into
the webhook fields, confirm the auth token matches, and restart the service.

**Call connects then silence**
Two causes: (1) the AI/ML Features Addendum (Phase 5.3) was not accepted —
ConversationRelay returns no audio without it; (2) the `wss://` WebSocket URL
is unreachable from Twilio's servers — check that Caddy is running
(`systemctl status caddy`), that UFW allows port 443, and that Cloudflare
orange-cloud proxy is **not** enabled on the domain (it intercepts WebSocket
upgrades).

**US SMS silently not delivered**
Carrier filtering drops messages from unregistered local numbers to US
recipients. The A2P 10DLC campaign (Phase 5.6) must be fully approved before
SMS works. Until then, keep `SMS_ENABLED=false`; the harness degrades SMS
notifications to the Telegram control channel automatically.
