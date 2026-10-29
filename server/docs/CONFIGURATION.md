# Explicit configuration

`config/bridge.env.example` lists generic values; it is not loaded automatically. Export approved values or use a private service-manager environment file. Never source untrusted env files. No credentials are shipped. The inherited HA, SiYuan, Maton Calendar and TV dispatchers are removed; their old enable/credential flags are unused. Configure any ACP agent-owned integrations and skills on the agent itself.

- `SARAH_BACKEND`: `llm` (default) or `acp`. ACP uses `SARAH_ACP_CWD` plus exactly one of `SARAH_ACP_SOCKET` or JSON argv `SARAH_ACP_COMMAND`, with optional `SARAH_ACP_TIMEOUT_SECONDS` (default 120). Neither backend has bridge-owned integrations. See [ACP transport, sessions and trust boundary](ACP.md).
- `SARAH_LLM_BASE_URL`: OpenAI-compatible API prefix (default `http://127.0.0.1:8012/v1`); appends `/chat/completions`. HTTPS required except on loopback; no URL credentials/query/fragment. Redirects, proxies and automatic retries are disabled.
- `SARAH_LLM_MODEL`: model ID (default `ggml-org/Qwen3.8-27B-GGUF:Q4_K_M`).
- `SARAH_LLM_API_KEY` or `SARAH_LLM_API_KEY_FILE`: server-side provider token. Set only one; both empty omits upstream authentication. Token is never included in device responses or configuration repr. There is no Hermes credential pool or Codex fallback.
- `R1_WHISPER_MODELS`: local faster-whisper download/cache root, no automatic fetch.
- `R1_KOKORO_ROOT`: isolated TTS venv and ONNX/voice asset directory.
- `R1_TIMEZONE`: IANA timezone for speech clock presentation, default UTC. Set before process start; an invalid timezone fails startup/import.

The direct-model backend sends no tool schemas and rejects model tool calls. Legacy `R1_ENABLE_*`, HA/SiYuan/Maton credentials, calendar scope and TV script variables no longer configure any bridge behavior. Remove those obsolete values from your own private service environment when maintaining it; no live environment is changed by this source cleanup.

No built-in retention/deletion scheduler for bridge media or transcripts exists. Establish a private lifecycle policy and backups. Revoke a device using `Store.revoke(device_id)` from a trusted local administrative script; no unauthenticated admin endpoint exists. Re-provision intentionally rather than overwriting state.
