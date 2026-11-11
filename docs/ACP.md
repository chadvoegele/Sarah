# ACP and HTTP contract

## Generic ACP v1

The bridge connects by trusted Unix socket or administrator-selected stdio argv and exchanges newline-delimited JSON-RPC 2.0. No shell is involved.

1. `initialize`: protocol version 1, empty client capabilities and Sarah client identity.
2. `session/new` with configured absolute `cwd` and empty `mcpServers`, or `session/load` with the exact durable session ID when supported.
3. Persist device/conversation/backend/session ownership before `session/prompt`.
4. Submit only the current literal transcript as one text prompt. Stored dialogue is never replayed as executable prompt/history on reconnect.
5. Collect current-session `agent_message_chunk` text only, requiring nonempty text and `end_turn`. Ignore thoughts, tool events, load-time history and recognized startup/UI extension notifications.
6. Mark successful binding ready. On admitted timeout, disconnect, malformed/incomplete response, cancellation or crash, retain the session as unusable/uncertain. No prompt retry, replacement session or model fallback.

The client advertises no filesystem or terminal capability. `session/request_permission` returns cancelled; other agent-to-client requests, including `_sarah/dispatch`, return method-not-found. Agent-owned tools run under the agent's own authorization model, not through Sarah. Do not mistake client permission denial for a sandbox around that agent.

Limits: 256 KiB per frame, 4 MiB total protocol input, 8192 frames per prompt and 12000 assistant characters. Initialization/load also share bounded input counters and the whole configured ACP deadline. Warm transport counters/answer buffers reset between completed prompts. Stdio stderr is discarded and raw agent errors are never returned to Android. A best-effort `session/cancel` is followed by owned transport/process cleanup; cancellation cannot undo an action.

## Authenticated HTTP protocol 1

All routes require `Authorization: Bearer TOKEN`, including health and diagnostics. Responses use no-store caching policy. Auth failure and absent/unowned resources use 403; idempotency/admission conflicts use 409; unconfigured runtime uses 503. Each authenticated device has a 90-request/minute limit shared across polling, audio and control routes.

| Method/path | Contract |
| --- | --- |
| `GET /v1/health` | Configuration-only readiness, protocol 1, `backend: acp`. |
| `POST /v1/conversations` | Exact `{}` body; return new conversation ID (201). |
| `POST /v1/turns` | WAV upload; `X-Conversation` and `Idempotency-Key` required; return turn ID (202). |
| `GET /v1/requests/{request}` | Read-only owner-bound lookup by idempotency key. Never submits work. |
| `GET /v1/turns/{turn}` | Owner-bound state/transcript/assistant text and audio availability. |
| `GET /v1/turns/{turn}/audio` | Completed whole-response MP3 when available. |
| `GET /v1/turns/{turn}/audio/{seq}` | Owner-bound sentence MP3 while stream is active. |
| `POST /v1/turns/{turn}/cancel` | Exact `{}`; stop local work, never undo/replay. |
| `POST /v1/diagnostics` | Strict opt-in schema-1 report; owner-bound receipt (201). |
| `GET /v1/diagnostics/{code}` | Owner-bound recent report or 404. |

There is no confirmation, phone receipt, dispatch, model, tool, integration or arbitrary-proxy endpoint. `X-Clarification-Parent` is refused: clarification is ordinary assistant conversation with an explicit next user turn, not a local action/lease. No `phone_command`, tool or confirmation envelope is emitted.

Uploads must be PCM WAV, signed 16-bit, mono/stereo, 16/44.1/48 kHz, 0.25–30 seconds and at most 4 MiB. A valid retry with the same key/bytes/conversation returns its original ID, never a new task. Different bytes/conversation conflict. One active voice job is admitted bridge-wide, including cleanup and sentence playback acknowledgement.

A turn envelope contains `id`, `conversation`, `state`, `detail`, `transcript`, `audio` and optionally `timings` or `audio_chunks`. States are `transcribing`, `thinking`, `speaking`, `done`, `error`, `cancelled`, `uncertain`. At `done`, `detail` is the original assistant text; speech-only Markdown/currency/time presentation does not modify saved text. `uncertain` is terminal and blocks new turns in that conversation. A post-prompt failure cannot be described as “nothing happened.”

## Sentence audio

Opt in with `X-Audio-Chunks: sentence-mp3-v1`. Poll returns `audio_chunks: {count, complete}`. Chunks are numbered from zero and contain ordered MP3 sentences. Poll with `X-Audio-After: N` to acknowledge playback of the first N chunks. Acknowledgements must be monotonic and cannot exceed produced count. Two unacknowledged chunks maximum; at most 32 chunks/4 MiB total; a 240-second timeout covers generation and acknowledgement.

The full assistant text is available in `detail` during speaking. After the final acknowledgement, the turn becomes done and ephemeral chunks are deleted; there is no combined MP3 in this mode. Whole-response MP3 output is also limited to 4 MiB. A client must not treat a transient chunk as a durable history attachment. TTS failure keeps the completed text, clears partial audio and does not retry the agent. Stop hides chunks immediately and joins actual generation cleanup before another voice admission.

## Session compatibility

Backend identity includes a relay-version namespace and a digest of cwd/transport/argv, not argv secrets. Only conversations created by the new relay get its additive boundary marker. Old conversations remain inspectable but cannot be migrated or rebound automatically, even if their old IDs or endpoint configuration happen to match. Existing database tables/rows are not deleted. Create a new conversation explicitly; reconcile any prior uncertain actions outside Sarah first.
