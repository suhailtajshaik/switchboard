# Contributing to Switchboard

Thanks for helping build the open voice-agent harness!

## Ground rules
1. **Spec first.** Behavior changes start as a PR to `docs/spec.md`; code
   follows. The spec is the source of truth — implementations conform to it,
   not the other way around.
2. **Security invariants are sacred.** Any PR touching identity, policy,
   telephony, or tool exposure must keep invariants **S1–S8**
   (`docs/spec.md §8`) green and include/extend their conformance tests.
3. **Compliance rails stay on.** PRs that weaken AI disclosure, consent
   checks, quiet hours, or emergency-number blocking will be declined.
4. **One owner per instance** is a design principle, not a missing feature.

## Dev setup
```bash
git clone <your fork> && cd switchboard
python3 -m venv .venv && source .venv/bin/activate
pip install -r src/requirements.txt -r src/requirements-dev.txt
pytest tests/
```
No Twilio account is needed for tests: telephony is exercised through recorded
webhook fixtures and a fake ConversationRelay WebSocket peer (see `tests/`).

## Style
- Python ≥3.12, `ruff` for lint/format, full type hints on public interfaces.
- Adapters implement the Protocols in `docs/extending.md` — no cross-layer
  imports (a channel adapter never talks to Twilio, etc.).
- Conventional Commits (`feat:`, `fix:`, `docs:`…); update `CHANGELOG.md`.

## PR checklist
- [ ] Spec updated (if behavior changed)
- [ ] Tests added/updated; `pytest` green
- [ ] Docs updated (`docs/`, `.env.example` if config changed)
- [ ] No secrets, phone numbers, or personal data in code, tests, or fixtures

## Conduct
Be kind and assume good faith. See `CODE_OF_CONDUCT.md`.
