# Deployment (Ubuntu 24.04 VPS)

## Prerequisites
- VPS with a public IPv4 (2 vCPU / 4 GB recommended), Ubuntu 24.04 LTS,
  SSH-key login.
- A domain with an **A record** → the VPS IP (if Cloudflare: *DNS only*/grey —
  the relay WebSocket needs a direct connection).
- Accounts: Anthropic Console (brain), Telegram bot, Twilio (see
  `docs/telephony-twilio.md` for the Twilio checklist incl. the AI/ML
  addendum and A2P 10DLC).

## Install
```bash
git clone https://github.com/YOURNAME/switchboard
cd switchboard
sudo bash scripts/setup.sh assistant.yourdomain.com
```
The script is idempotent and performs: system updates + unattended security
upgrades; UFW (22/80/443 only) + fail2ban; Node 22 (for the Agent
SDK/Claude Code); Caddy with automatic HTTPS; a dedicated non-root
`switchboard` user; Python venv with pinned deps; directory layout under
`/opt/switchboard/{app,personas,workspace,data}`; `.env` from the example
(chmod 600); systemd unit installed (not started).

## Provide the application code (`src/`)
The reference implementation is built **against `docs/spec.md`** and verified
on your own server (real webhook signatures, real relay WS):
- Option A — release: copy a released, CI-tested `src/` tree into
  `/opt/switchboard/app`.
- Option B — generate: run a coding agent (e.g. `claude` from Claude Code) in
  `/opt/switchboard/app` with `docs/spec.md` + `docs/configuration.md` as the
  instruction, then run the conformance tests (spec §11) until green.

## Run
```bash
sudo nano /opt/switchboard/.env        # fill everything (docs/configuration.md)
sudo cp -r personas/* /opt/switchboard/personas/
sudo systemctl enable --now switchboard
journalctl -u switchboard -f
curl https://assistant.yourdomain.com/health
```
Then wire Twilio webhooks (`docs/telephony-twilio.md §3`) and run the spec §11
conformance checklist.

## Operations
- **Logs:** `journalctl -u switchboard` (structured JSON).
- **Backups:** install the provided script —
  `crontab -e` → `17 3 * * * /opt/switchboard/app/scripts/backup.sh >> /var/log/switchboard-backup.log 2>&1`.
  Set `BACKUP_REMOTE` (an rclone remote) for off-box copies. Details:
  `docs/operations.md §6`.
- **Watchdog:** once `main.py` implements `sd_notify` (spec §7), uncomment
  `Type=notify` / `WatchdogSec=60` in the unit to catch hung processes.
- **First run:** set `DRY_RUN=true`, rehearse the full loop (reminder →
  escalation → approval → "call"), check `/status` and `/calls`, then flip it
  off.
- **Updates:** `git pull`, re-run conformance tests, `systemctl restart
  switchboard`. OS patches itself (unattended-upgrades).
- **Docker:** planned (roadmap); the systemd path is the supported one today.
