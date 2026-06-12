# Extending Switchboard (adapters)

Four small interfaces decouple providers from the core. Reference signatures
in Python `Protocol` style; any conformant implementation may be swapped via
config. Rule of thumb: **adapters move data; the core decides.** An adapter
must never make policy decisions (consent, caps, roles).

## 1. ChannelAdapter (chat control plane — ref: Telegram)
```python
class ChannelAdapter(Protocol):
    name: str
    async def start(self, on_inbound: Callable[[InboundMessage], Awaitable[None]]) -> None: ...
    async def send(self, peer_id: str, text: str) -> None: ...
    def is_owner(self, peer_id: str) -> bool: ...   # root-of-trust check
```
Notes: drop+log non-owner peers; voice notes may be passed as
`InboundMessage(kind="audio", uri=…)` for a future STT hook.

## 2. TelephonyAdapter (ref: Twilio/ConversationRelay)
```python
class TelephonyAdapter(Protocol):
    name: str
    async def place_call(self, to: str, session_id: str, amd: bool = True) -> CallHandle: ...
    async def send_sms(self, to: str, body: str) -> None: ...
    def verify_webhook(self, request) -> bool: ...      # S2 lives here
    # Inbound surface: the adapter owns its HTTP/WS routes and translates
    # provider events into core CallEvents:
    #   call_started(meta) · caller_text(text) · interrupted()
    #   amd_result(AnsweredBy) · call_ended(reason)
    # and consumes core commands: speak(token_stream) · hangup()
```
`AnsweredBy` is the spec enum (`human`, `machine_start`, `machine_end_*`,
`fax`, `unknown`); map provider-specific values onto it.

## 3. BrainAdapter (ref: Claude Agent SDK)
```python
class BrainAdapter(Protocol):
    name: str
    async def respond(self, session: Session, user_text: str,
                      tools: ToolSet) -> AsyncIterator[BrainEvent]: ...
    # BrainEvent = TextToken | ToolCall | Done
```
The core hands the brain a **role-filtered ToolSet** (spec §3); the brain
never sees tools the role lacks. The reference adapter wires Agent SDK
custom tools and confines file/exec built-ins to the workspace
(https://platform.claude.com/docs/en/agent-sdk/overview).

## 4. Tools
Native tools register with a name, JSON schema, required role, and
`sensitive: bool` (out-of-band approval gate, S3). External tools SHOULD
come in via **MCP**
(Model Context Protocol) servers so they're portable across harnesses —
attach MCP servers to the brain adapter and list their tools in the
registry with role mappings.

## Checklist for a new adapter PR
- [ ] Implements the Protocol; no imports from other adapters
- [ ] Maps provider events/errors onto core enums (incl. AMD)
- [ ] Webhook/auth verification implemented and tested (forged + valid)
- [ ] Fixtures added so CI runs without live provider credentials
- [ ] Docs page `docs/telephony-<name>.md` or `docs/channel-<name>.md`
