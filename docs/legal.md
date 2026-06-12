# Legal & compliance guide

> **Not legal advice.** This summarizes the rules the harness is engineered
> around, with sources, so operators can make informed decisions. Laws vary
> by country and US state; if in doubt, ask a lawyer.

## 1. AI voices on calls are regulated (US)
The FCC's 2024 Declaratory Ruling confirms AI-generated voices count as
"artificial or prerecorded voice" under the **TCPA** — consent,
identification and disclosure rules apply
(https://www.fcc.gov/document/fcc-confirms-tcpa-applies-ai-technologies-generate-human-voices).
Several states (e.g. TX, CA, FL, CO, IL, UT) additionally require disclosing
AI use **during** the call, and a federal in-call disclosure rule has been
proposed. **Harness consequence:** invariant **S6** injects a first-sentence
disclosure ("This is the AI assistant for X, calling on their behalf") into
every outbound persona, non-removable by task briefs.

## 2. Consent: who may the agent call?
- **Businesses, transactional purposes** (orders, reservations, opening
  hours): normal commerce — fine.
- **Individuals:** only with prior consent. The harness enforces a
  **consent registry**: person contacts have `consented_to_ai_calls`; the
  policy engine refuses calls to persons without it. Get a simple "my AI
  assistant might call you sometimes — OK?" and record it.
- **Never** marketing, cold-calling, robocall campaigns, or repeated
  unwanted contact. TCPA statutory damages run $500–$1,500 *per call*.
  Switchboard is single-owner personal tooling **by design** and ships caps
  that make campaign abuse impractical (S5).

## 3. Recording
US states split between one-party and **all-party consent** for recording
calls. Switchboard sidesteps the problem: **no audio is recorded** (S7);
text transcripts of the agent's own conversation are kept for the owner's
records. If you ever add recording, you own the consent problem.

## 4. Calling-hours & identification
The harness enforces quiet hours for non-owner calls (default 21:00–09:00,
configurable) and always identifies the responsible party (the owner) and a
callback number on voicemails — matching long-standing TCPA artificial-voice
identification requirements.

## 5. Emergency services
The agent **cannot dial emergency numbers** (S4) — VoIP emergency calling
has strict separate rules, and an AI intermediary is the wrong tool. If a
caller's message indicates an emergency, the harness's job is to alert the
owner immediately on every channel.

## 6. SMS (US): A2P 10DLC
Carrier rules require registration to send SMS from local numbers to US
recipients; individuals use the Sole Proprietor tier. Keep the registered
campaign description honest ("personal assistant notifications and replies");
see `docs/telephony-twilio.md §2.6`.

## 7. Outside the US
AI-disclosure, robocall, data-protection (e.g. GDPR for transcripts of EU
callers) and recording laws differ. The disclosure-always +
consent-registry + no-recording posture is a sane international baseline,
but verify locally before going live.

## 8. Publishing / branding note
If you fork or redistribute: this project must keep its own branding and not
present itself as a product of Anthropic, Twilio, or any model/carrier
vendor; check name-trademark availability before release.
