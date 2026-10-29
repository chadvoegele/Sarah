# ACP agent backend

Chad's Agent — implementation notes.

Sarah can act as an **Agent Client Protocol v1 client**, while retaining local Whisper/Kokoro and the existing Android HTTPS API. Direct OpenAI-compatible inference remains the default.

```text
Android → HTTPS Sarah bridge → Whisper → ACP agent → assistant text
        ← authenticated MP3  ← Kokoro ←
```

## Configuration

```sh
export SARAH_BACKEND=acp
export SARAH_ACP_CWD=/absolute/agent/working/directory
export SARAH_ACP_SOCKET=/run/pi-acp/acp.sock
export SARAH_ACP_TIMEOUT_SECONDS=120
```

The Unix socket carries newline-delimited ACP JSON-RPC, not HTTP, WebSocket, Pi RPC or MCP. Socket access is authorized by filesystem permissions; there is no ACP bearer-token field. Mount/share the socket deliberately and match its UID/GID. Never expose an unauthenticated socket as a public TCP service.

Alternatively, launch an administrator-selected stdio agent:

```sh
export SARAH_BACKEND=acp
export SARAH_ACP_CWD=/absolute/agent/working/directory
unset SARAH_ACP_SOCKET
export SARAH_ACP_COMMAND='["pi-acp"]'
```

Set **exactly one** of `SARAH_ACP_SOCKET` or `SARAH_ACP_COMMAND`. The command is a JSON argv array executed directly, never a shell string and never derived from speech/model output. A stdio child inherits the bridge environment except `SARAH_*` variables, so the Sarah LLM token is not passed to it. Configure agent credentials privately using the agent's own mechanisms. Child stderr is discarded, not exposed to devices or bridge logs. The bridge owns and reaps spawned agent process groups; a socket connection never terminates the shared agent service.

`SARAH_ACP_CWD` must be absolute. For sockets it is interpreted by the agent, not checked against the bridge filesystem. A stdio command also uses it as its local process cwd. The deadline (1–600 seconds, default 120) includes connect, initialize, session creation/loading and prompt completion. Backend/environment changes require a bridge restart.

To return to Qwen, set `SARAH_BACKEND=llm`; existing `SARAH_LLM_*` configuration is unchanged. Start a new Sarah conversation when switching backends; prior direct-model history is not replayed into an agent.

## Sessions and recovery

- Initialize with protocol version 1 and no delegated filesystem/terminal capabilities.
- Each Sarah device/conversation gets a **new, dedicated ACP session**. No configured/shared Matrix session IDs and no steering into existing Dex conversations.
- Persist its session ID, backend-configuration fingerprint and state in the private bridge SQLite database, before sending the first prompt. Session IDs are unique per backend binding.
- Close the connection after each turn. Reconnect and `session/load` for subsequent turns or after bridge restart. An agent must advertise `loadSession` for resumed conversations.
- Load-time replay/startup notifications are ignored. Send only the current transcript as a text prompt; the ACP agent owns its context. Never resend Sarah history.
- A failed load never falls back to `session/new`. An inflight, interrupted, timed-out, disconnected or cancelled prompt leaves its binding uncertain and blocks further prompts in that conversation. Start a new conversation deliberately; no automatic replay/retry or transfer to Qwen.
- HTTP cancellation sends `session/cancel` best-effort, closes the connection and cleans up owned processes. Cancellation is **not rollback** and does not prove agent tools stopped or undo their effects. Agent-side session/history deletion is not implemented.

Only `agent_message_chunk` text received during the active prompt is retained/spoken. Pi's advertised startup prelude and typed extension/UI notifications are filtered even when they arrive after a prompt begins. Thoughts, tools, usage, startup text and replayed history are not. A complete nonempty answer requires `stopReason=end_turn`; partial/refused/cancelled/length-limited turns fail closed. Frames, total bytes, frame count, answer length and total runtime are bounded. Upstream errors/payloads are not included in device error messages.

## Tool trust boundary

**Selecting an ACP backend delegates to an agent with its own configured privileges.** Denying ACP client permission requests is not an agent sandbox. In particular, Pi/Dex may execute its own tools without asking the client; its credentials and host mounts can provide broad access.

Sarah always returns a cancelled permission outcome and rejects delegated filesystem/terminal/client RPC methods. There is no automatic approval policy. Sarah's inherited HA/notes/calendar/TV dispatchers have been removed from both backends. Configure tools and restrictions on the ACP agent instead. The health response's `tools` field describes Sarah-owned integrations only; it does not certify that an ACP agent has no tools. `backend=acp` identifies the selected trust boundary.

ACP-authored action claims are ordinary agent prose, not Sarah dispatcher receipts. The direct-Qwen backend offers conversation only and rejects tool calls. Do not treat ACP replies as verified physical action outcomes.

## Dex integration

Dex's current pi-acp deployment uses a Unix socket at `/run/pi-acp/acp.sock` that forks an ACP stdio connection. This backend matches that framing and uses `initialize`, `session/new`, `session/load`, `session/prompt`, `session/update`, `session/request_permission` and `session/cancel`.

A future Sarah deployment needs intentional access to Dex's socket volume (or a separately reviewed transport helper), its agent-side cwd and session persistence, and review of Dex's broad host/tool access. This change does **not** alter Dex Compose, mount a volume, switch its model, take over Matrix sessions, approve tools or deploy Sarah. A successful local protocol test is not proof of a production Dex voice deployment.

## Tests

`tests/test_acp.py` uses a real temporary Unix-socket fake ACP agent, plus real disposable stdio children. It covers wire framing, context/session isolation, persistent reload, replay suppression, denied permissions, no delegated tools, malformed/oversized streams, deadlines, cancellation, process reaping, HTTP upload/deduplication and the shared speech pipeline. No real Dex prompt or action is needed by the offline tests.
