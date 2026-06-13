# Security Policy

Switchboard controls a real phone line and an autonomous agent — we treat
security reports as top priority.

## Reporting a vulnerability
- **Do not** open a public issue for exploitable problems.
- Email: REPLACE_WITH_YOUR_SECURITY_EMAIL (or use GitHub *Private
  vulnerability reporting* if enabled).
- Include: affected component, reproduction steps, impact. Expect an
  acknowledgment within 72 hours.

## Scope of interest (examples)
- Bypassing role isolation (a STRANGER reaching any tool) — invariant **S1**
- Webhook signature validation bypass — **S2**
- Sensitive-action approval bypass (out-of-band gate) / caller-ID-spoofing
  escalation — **S3**
- Prompt-injection paths from untrusted callers to actions — **S1/S6**
- Cost-runaway or cap-bypass vectors — **S5**

## Supported versions
Only the latest minor release receives fixes during alpha/beta.

## Operator hardening
Deployment hardening guidance (firewall, secrets, least privilege, spend
caps) lives in `docs/security.md` — read it before going live.
