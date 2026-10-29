# Architecture and trust boundaries

`SARAH_BACKEND=llm` uses the direct model flow below. `SARAH_BACKEND=acp` shares local speech but delegates each transcript to a separately configured ACP agent using dedicated durable sessions. [ACP architecture and trust boundaries](ACP.md) describe session recovery, no-replay behavior, permission denial and agent-owned tools.

Client → HTTPS bearer-authenticated bridge → local STT → OpenAI-compatible local-model chat completions → local TTS → authenticated media download.

API routes: `GET /v1/health`, `POST /v1/conversations`, `POST /v1/turns`, `GET /v1/requests/{request}`, `GET /v1/turns/{turn}`, `GET /v1/turns/{turn}/audio`, and turn `/cancel` and `/confirmation` POSTs. Health requires device authentication too. Audio upload requires `Content-Type: audio/wav`, `X-Conversation`, and `Idempotency-Key`.

SQLite stores device token hashes, conversations, and turn transcript/detail. Restart marks unfinished turns uncertain without replay. Removed dispatcher approval/action helpers no longer create tables in new databases. Existing databases are opened without dropping historical tables or records; ACP session binding/durability is unchanged. Cancellation cannot undo actions an ACP agent may already have taken.

Protocol 1 routes and JSON fields used by the existing Android APK remain compatible. Health retains `tools`, `home_assistant`, `siyuan`, `calendar` and `tvtime` as false, for either backend; these describe only bridge-owned capabilities, never agent-owned tools. No new turn enters confirming/acting or offers a confirmation envelope. The legacy `/confirmation` route retains its request schema, authentication and turn ownership checks, then returns HTTP 403 `confirmation_unavailable`; old clients cannot authorize stale actions. No APK/package/signing change is needed.

The direct runtime reads endpoint, model and token from `SARAH_LLM_*`. It calls `/chat/completions` with conversation messages and real streaming, without tool schemas or a dispatch loop. It imports no Hermes modules and never calls Codex. No credential rotation, provider fallback, automatic retries, environment proxies or redirects. HTTP is restricted to loopback upstreams; remote endpoints require HTTPS. Streams are bounded by deadline, total bytes, line bytes and answer size. Truncated responses and any tool/function calls fail closed. `reasoning_content` is not displayed or spoken. Tests construct the production runtime with synthetic configuration and transports.

Local speech model assets are not bundled or downloaded implicitly. Whisper defaults to `base`, CPU/int8, English. Kokoro defaults to `af_heart`, speed 1.05, `en-us`; an isolated subprocess is terminated/reaped on timeout/cancellation, and MP3 publication is atomic. Missing TTS yields text-only replies. Missing STT fails the turn.

The optional idle-power policy holds suspend for 3600 seconds after fresh physical input, with a hard 300-second active-operation cap. It has no network listener and never forces suspend/unlock. Installing a privileged helper changes power behavior and requires separate device review. Historical Wi-Fi repair/deployment programs and private observation tooling are intentionally not distributed.
