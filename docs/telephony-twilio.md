# Telephony adapter: Twilio (reference)

## 1. Why Twilio + ConversationRelay
ConversationRelay turns a live call into **text-in / text-out over a
WebSocket**: Twilio runs speech-to-text and text-to-speech next to the
carrier network (low latency, barge-in/interruption support), your server
only streams text. That keeps the harness brain-agnostic and the VPS
audio-free. Docs: https://www.twilio.com/docs/voice/conversationrelay

## 2. Account checklist (Console: https://console.twilio.com)
1. Sign up → **upgrade to paid** (trial accounts can only reach verified
   numbers and inject a trial message).
2. Buy a local number with **Voice + SMS** capability.
3. **Voice → Settings → General → enable the “Predictive and Generative
   AI/ML Features Addendum.”** ConversationRelay will not run without it
   (onboarding guide: https://www.twilio.com/docs/voice/conversationrelay/onboarding).
4. **Voice → Geo Permissions:** enable only countries you will call
   (toll-fraud protection).
5. **Billing:** set a low-balance email alert.
6. **US SMS — A2P 10DLC registration** (Messaging → Regulatory Compliance):
   individuals without an EIN register as **Sole Proprietor** (hobbyist use
   allowed). Costs ≈ $4.50 brand + $15 campaign vetting one-time, ~$2/mo;
   approval ~10–15 days. Until approved keep `SMS_ENABLED=false` — the
   harness degrades SMS to the control channel automatically.
   Quickstart: https://www.twilio.com/docs/messaging/compliance/a2p-10dlc/quickstart

## 3. Webhook wiring (Phone Numbers → Active numbers → your number)
| Field | Value |
|---|---|
| Voice · “A call comes in” | Webhook `https://$PUBLIC_DOMAIN/twilio/voice` · POST |
| Voice · “Call status changes” | `https://$PUBLIC_DOMAIN/twilio/status` · POST |
| Messaging · “A message comes in” | Webhook `https://$PUBLIC_DOMAIN/twilio/sms` · POST |

The AMD callback URL is supplied per-call by the harness — nothing to set.

## 4. Protocol notes for implementers
- **Inbound TwiML:** respond with `<Connect><ConversationRelay
  url="wss://$PUBLIC_DOMAIN/twilio/relay?...">`; set the greeting per role
  and pick a natural TTS voice/provider via the noun's attributes. Always
  consult the current TwiML reference — attributes evolve:
  https://www.twilio.com/docs/voice/twiml/connect/conversationrelay
- **Relay WS:** implement per
  https://www.twilio.com/docs/voice/conversationrelay/websocket-messages —
  `setup` (call metadata), `prompt` (caller speech as text), `interrupt`
  (caller barged in → stop streaming, truncate context), and stream replies
  as `text` token messages; send the end message to hang up.
- **AMD:** create calls with `MachineDetection=Enable`, `AsyncAmd=true`,
  `AsyncAmdStatusCallback=…/twilio/amd`. `AnsweredBy` ∈ `human`,
  `machine_start`, `machine_end_beep|silence|other`, `fax`, `unknown` —
  branch per spec §5. Tuning & FAQ:
  https://www.twilio.com/docs/voice/answering-machine-detection
- **Signature validation (S2):** every request must validate
  `X-Twilio-Signature` against the **exact public URL** (scheme/host/path —
  a common 403 cause behind proxies) using `TWILIO_AUTH_TOKEN`.

## 5. Known gotchas
- 403s on webhooks → URL mismatch in signature validation (see above) or
  wrong auth token.
- Call connects then silence → AI/ML addendum not accepted, or `wss://` URL
  unreachable (Cloudflare proxying, firewall, Caddy down).
- SMS to US silently filtered → 10DLC not approved yet.
- AMD is probabilistic (~94% claimed accuracy in US/Canada): the persona
  must tolerate misclassification gracefully (e.g., a human classified
  `unknown`).

## 6. Adding another provider
Implement the `TelephonyAdapter` Protocol (`docs/extending.md`). Telnyx and
raw SIP via Pipecat/LiveKit are roadmap targets; AMD semantics differ per
provider — map them onto the spec's `AnsweredBy` enum.
