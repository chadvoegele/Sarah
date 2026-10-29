# Sarah

Android voice assistant and Python HTTPS bridge, with a configurable OpenAI-compatible local model (default) or an optional [ACP agent backend](server/docs/ACP.md). No Hermes installation, credential pool, or automatic provider fallback. An ACP agent manages its own model/credentials/tools.

```text
Android → HTTPS bridge → local Whisper → Qwen chat/completions
        ← text + MP3   ← local Kokoro ← model reply
```

## Layout / provenance

- `android/`: https://github.com/serexe/sarah-android at `e29456bc59fe26ecd482c434141f41433d2e8a90`.
- `server/`: https://github.com/serexe/sarah-r1 at `9794c41b201cc97001e575cb28a72b54489148bb`, including its legacy Ubuntu Touch client/tests for reference.
- Upstream MIT licenses and third-party notices are retained in each subtree. Upstream publication/checksum reports describe upstream artifacts, not this fork. Android is unchanged; its existing API matches this bridge.
- The original import is committed separately from local backend changes. Upstream README/publication records are historical; this README and `server/docs/CONFIGURATION.md` describe the fork's setup.

## ACP / Dex backend

Set `SARAH_BACKEND=acp`, `SARAH_ACP_CWD` to the agent's absolute working directory, and `SARAH_ACP_SOCKET` to its Unix socket. Alternatively set `SARAH_ACP_COMMAND` to a JSON argv array for a stdio agent. [ACP setup and security](server/docs/ACP.md) covers dedicated persistent conversation sessions, cancellation, denied client permission requests, and future Dex socket-volume access. This does not deploy or change Dex; an ACP agent's own tools retain its configured privileges.

## Reverse proxy / Docker

The server includes a container image and an explicit loopback-only HTTP mode for use behind a trusted HTTPS proxy. It reuses the existing device Bearer token as the API key; no Basic-auth layer or APK change is required. See [proxy and provisioning setup](server/docs/PROXY.md). Keep direct TLS as the default outside that topology.

## Server setup

Requires Python 3.12, FFmpeg for MP3, local speech assets, and an OpenAI-compatible chat-completions server (such as llama.cpp).

```sh
cd server
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt

# Copy generic configuration; edit privately, then explicitly export it.
cp config/bridge.env.example .env
# Supply endpoint/model and a provider token or private token-file path:
export SARAH_LLM_BASE_URL=http://127.0.0.1:8012/v1
export SARAH_LLM_MODEL=ggml-org/Qwen3.8-27B-GGUF:Q4_K_M
export SARAH_LLM_API_KEY_FILE=/absolute/private/path/llm-token

# One-time local pairing state; token is saved privately, not printed.
.venv/bin/python -m bridge.prepare --state .state --origin https://localhost:8787 --device android
# Local test CA/server certificate only; use a trusted deployment cert for real use.
openssl req -x509 -newkey rsa:2048 -nodes -days 7 \
  -keyout .state/server.key -out .state/server.pem \
  -subj /CN=localhost -addext 'subjectAltName=DNS:localhost,IP:127.0.0.1' \
  -addext 'basicConstraints=critical,CA:TRUE'
chmod 600 .state/server.key

# Provision speech assets explicitly (runtime never downloads them).
.venv/bin/python -c 'from faster_whisper.utils import download_model; download_model("base", cache_dir=".build/whisper-models")'

.venv/bin/python -m bridge.server --db .state/state.db \
  --cert .state/server.pem --key .state/server.key --bind 127.0.0.1 --port 8787
```

The server listens only on loopback by default. To pair a phone, deliberately configure a reachable bind address, firewall and TLS hostname/certificate; `localhost` on the phone is not this server. Android accepts an explicitly imported private CA. Enter the bridge origin and device token from `.state/native-settings.json`, **not** the Qwen token. Keep that file private.

Kokoro is optional. Example setup from `server/` (review the upstream model/voice licenses before use):

```sh
uv venv --python 3.12 .build/kokoro-audition/venv
uv pip install --python .build/kokoro-audition/venv/bin/python -r requirements-tts.txt
curl -fL https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx -o .build/kokoro-audition/kokoro-v1.0.onnx
curl -fL https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin -o .build/kokoro-audition/voices-v1.0.bin
```

For a nondefault location, set `R1_KOKORO_ROOT` to the asset directory containing `venv/bin/python`. Missing TTS produces text-only replies. Missing Whisper assets fail voice turns. Speech models are not bundled.

## Behavior and security

- `SARAH_LLM_BASE_URL` includes the API prefix, normally `/v1`; the bridge appends `/chat/completions`.
- HTTP upstream is allowed only on loopback; remote endpoints require HTTPS. No redirect following, environment proxies, credential rotation, retries or fallback providers.
- `SARAH_LLM_API_KEY` or `SARAH_LLM_API_KEY_FILE` configures the provider token; set only one. Leave both unset for a deliberately unauthenticated endpoint. Never commit tokens.
- Streams have a total deadline and byte/output limits. Only final answer content is spoken, not `reasoning_content`. Qwen thinking is disabled via `chat_template_kwargs.enable_thinking=false` for voice latency.
- ACP is opt-in. Its agent owns context and tools; Sarah does not replay prompts after uncertain results or attach to existing Matrix sessions. Bridge-owned integrations cannot be enabled with ACP.
- Existing optional tools remain disabled by default. Do not enable HA/calendar/notes/TV integrations without reviewing their broad permissions. No live integration is required for conversation.
- Pairing/authentication, request idempotency, history, cancellation and server-owned action receipts retain the upstream protocol. History/media persist server-side; local Android reset does not erase them.

## Tests

```sh
cd server
.venv/bin/python -m pytest -q
```

Tests use synthetic credentials and loopback/mock services, never the real Qwen server. See `VALIDATION.md` for live-test results and limits. Android build prerequisites and private-signing limitations remain in `android/README.md`; no rebuilt APK is implied.
