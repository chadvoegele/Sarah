# Architecture

```text
[Android capture/wake]
          |
          v
[HTTPS auth + HTTP API] -> [durable device/conversation/turn store]
          |
          v
[local Whisper STT] -> [durable ACP session relay] -> [user-managed agent]
                                                            |
                                                            v
[Android playback/text] <- [local Kokoro + FFmpeg] <- [assistant text]
```

## Responsibilities

Android owns audio capture, transport, playback and UI. The bridge authenticates ownership, stores turn status, transcribes audio and relays the literal transcript. The generic ACP agent owns all reasoning, context, provider access, skills/tools and action authorization. The bridge never dispatches agent tools or asks Android to execute assistant output.

`core.Store` stores device token hashes, conversations and idempotent turns in SQLite. `relay_conversations` marks only conversations explicitly created by this implementation; old rows are never marked automatically. Legacy audit tables remain untouched. `acp_sessions` binds device/conversation to the digest of the transport/workspace identity and the exact agent session ID. Its `ready -> inflight -> ready/uncertain` transition is committed before prompting. Restart cannot convert `inflight` into permission to submit another prompt.

`acp_client` handles bounded ACP v1 NDJSON. Only assistant text for the current session during a prompt is collected. Thought/tool/history/extension notifications are not spoken. Client-side filesystem, terminals, permissions and private dispatch methods are unsupported or denied. There is no client tool executor. These restrictions do not sandbox the agent's own server-side tools; configure their authorization at the agent.

## Ownership and warm execution

One voice job owns admission until all native/process cleanup completes. Cancelling a Python await does not stop Whisper's native thread, so the bridge retains the clip and admission slot until that thread finishes. Kokoro is a lazy serialized local worker, reused after success. Failure/cancellation kills and reaps it before reuse. FFmpeg output is published atomically from same-filesystem private scratch only after successful encoding.

One ACP transport may stay warm for up to 300 idle seconds. Its key includes device, conversation, backend identity and session. Owner changes evict the transport and load the exact stored session, never a replacement. Errors/cancellation evict and poison an admitted session; successful eviction or idle expiry does not discard durable identity. Agents without `loadSession` may finish a warm conversation, but cannot resume it after eviction/restart.

Sentence audio keeps the admission slot while producing/playing. At most two produced-but-unacknowledged chunks are retained, with a 240-second generation/ack deadline. There are at most 32 chunks and 4 MiB encoded output per sentence stream. Chunk filenames are private server-generated IDs, not model-provided paths. Cancellation hides output immediately, then joins cleanup. Optional TTS failure preserves completed assistant text and never re-prompts the agent.

## Recovery and observability

Active turns become `uncertain` during startup recovery. Existing uncertain or incompatible bindings fail closed; history is not replayed into new sessions. Read-only request lookup resolves lost acknowledgements without a new admission. Reuploading the same idempotency key and bytes returns the original turn; changed bytes/conversation conflict.

Response metrics contain numeric durations and the fixed `acp` route only. Explicit opt-in diagnostics validate an allowlisted payload before writing, use owner-bound receipts, expire after seven days and enforce quotas. Normal request access logging is disabled. Conversation text/audio and diagnostic storage are still private data; operators must provide private state directories, backups and a retention policy.
