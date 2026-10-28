# Architecture and trust boundaries

`SARAH_BACKEND=llm` uses the direct model flow below. `SARAH_BACKEND=acp` shares local speech but delegates each transcript to a separately configured ACP agent using dedicated durable sessions. [ACP architecture and trust boundaries](ACP.md) describe session recovery, no-replay behavior, permission denial and agent-owned tools.

Client → HTTPS bearer-authenticated bridge → local STT → OpenAI-compatible local-model chat completions → optional explicitly configured dispatchers → local TTS → authenticated media download.

API routes: `GET /v1/health`, `POST /v1/conversations`, `POST /v1/turns`, `GET /v1/requests/{request}`, `GET /v1/turns/{turn}`, `GET /v1/turns/{turn}/audio`, and turn `/cancel` and `/confirmation` POSTs. Health requires device authentication too. Audio upload requires `Content-Type: audio/wav`, `X-Conversation`, and `Idempotency-Key`.

SQLite stores devices as token hashes; conversations, turn transcript/detail and dispatch metadata are persisted. Restart marks unfinished turns uncertain, not replayable. Action claims are durable before dispatch; cancellation is not rollback. Model-generated success cannot override dispatcher receipts. Mixed mutation turns use server-owned receipts; pure read/conversation turns retain model prose. HA group success requires stable membership and all-member readback.

Runtime reads an explicitly configurable endpoint, model and token from `SARAH_LLM_*` environment variables. It calls `/chat/completions` with chat messages and streamed tool-call deltas. It imports no Hermes modules and never calls Codex. No credential rotation, provider fallback, automatic retries, environment proxies or redirects. HTTP is restricted to loopback upstreams; remote endpoints require HTTPS. Streams are bounded by deadline, total bytes, line bytes and answer/tool size. Truncated responses and unsupported/parallel tools fail closed. `reasoning_content` is not displayed or spoken. Tests construct the real runtime with synthetic configuration and transports.

Local speech model assets are not bundled or downloaded implicitly. Whisper defaults to `base`, CPU/int8, English. Kokoro defaults to `af_heart`, speed 1.05, `en-us`; an isolated subprocess is terminated/reaped on timeout/cancellation, and MP3 publication is atomic. Missing TTS yields text-only replies. Missing STT fails the turn.

The optional idle-power policy holds suspend for 3600 seconds after fresh physical input, with a hard 300-second active-operation cap. It has no network listener and never forces suspend/unlock. Installing a privileged helper changes power behavior and requires separate device review. Historical Wi-Fi repair/deployment programs and private observation tooling are intentionally not distributed.
