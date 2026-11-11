# Configuration

The bridge does not load `.env` files itself. `config/bridge.env.example` is an example for an administrator-managed environment. Never commit private environment files.

| Setting | Meaning |
| --- | --- |
| `SARAH_BACKEND` | Optional compatibility assertion; only `acp` is accepted. |
| `SARAH_ACP_CWD` | Required absolute agent-side workspace. For stdio it must also exist locally. |
| `SARAH_ACP_SOCKET` | Absolute Unix socket path to a separately managed ACP v1 agent. |
| `SARAH_ACP_COMMAND` | Alternative JSON array of executable/arguments, without shell parsing. |
| `SARAH_ACP_TIMEOUT_SECONDS` | Whole ACP connect/initialize/load/prompt deadline: 1–600 seconds, default 120. |
| `R1_WHISPER_MODELS` | Existing local Whisper cache; default `.build/whisper-models` under repository root. |
| `R1_KOKORO_ROOT` | Existing Kokoro root containing model, voices and `venv/bin/python`; default `.build/kokoro-audition`. |
| `R1_TIMEZONE` | Speech presentation of explicit timestamps, default `UTC`. Not a semantic time-answer shortcut. |

Exactly one transport is mandatory. Stdio argv is administrator-controlled and is never derived from a transcript. The child does not inherit `SARAH_*` or `R1_*` bridge settings. Other environment variables belong to the administrator-selected agent; run it with a deliberately restricted environment/account. Agent provider credentials belong to the agent, not a bridge integration.

Unknown `SARAH_*`/`R1_*` settings, old SiYuan/Maton integration settings and `HERMES_GLOBAL_HOME` fail startup rather than silently enabling or ignoring old product configuration. Legacy flags such as `--hermes-source`, `--backend`, and `--enable-research` are not accepted. No fixed launcher, policy handshake, profile, bootstrap, credentials lookup, model resolver or tool schema is installed. Generic agents may use their own tools, including search/mail, but Sarah never calls them on their behalf.

## HTTP listener

Direct TLS requires `--db PATH --cert PATH --key PATH`. Default bind is `127.0.0.1`, port 8787. TLS minimum is 1.2. Certificate/key files remain external and private. Choose a hostname/certificate trusted by the Android client; never disable hostname verification.

Behind a trusted TLS proxy, use `--http --bind 127.0.0.1` (or literal `::1`) with no certificate flags. `localhost`, wildcard and non-loopback binds are refused in HTTP mode. Every route still requires a valid bearer token; proxy identity headers are not trusted. In containers, use host networking as in the review example or an equivalent design that preserves the loopback-only boundary; publishing a container's loopback port is not sufficient.

Health is authenticated protocol 1 with `backend: acp`, `connected`, `ready` and a static explanation. It does not probe the socket, start the agent, download assets or call a provider. There are no integration capability flags or implicit fallback routes.

## Speech assets

STT uses local-only English Whisper `base`, CPU/int8, beam size 3 and VAD. TTS uses local CPU Kokoro (`af_heart`, speed 1.05, English) and FFmpeg/libmp3lame. Missing assets fail without download/fallback. Kokoro runs under its local environment's `python -I`, with a 20-second synthesis deadline. FFmpeg has a separate 20-second stage deadline; whole non-chunk speech is bounded by 45 seconds. The Dockerfile makes asset acquisition an explicit build-time operation; runtime never downloads models.
