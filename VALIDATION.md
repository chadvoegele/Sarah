# Validation

## Bridge-dispatcher removal — 2026-10-29

Chad's Agent — offline validation in the managed isolated feature worktree, based on `origin/main` at `d1483a6`. This section describes the current cleanup; the dated live-server and integration evidence below is historical and was not repeated.

Removed the four bridge-owned HA/SiYuan/Maton Calendar/TV dispatchers, schemas, wiring, enable/credential settings, exclusive rollback and durable dispatch/approval helpers, and integration-only tests/fixtures. Replaced the integration-dependent conversation and speech-history tests with the production direct-Qwen runtime and synthetic streaming model responses. ACP session, transport, no-replay, typed filtering and process-safety implementation is unchanged; its full active tests remain. Agent-owned MCP integrations/skills are independent and unchanged.

From the isolated `server/`, using the existing Python 3.12.15 environment without changing packages:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/chad/code/code.voegele.me/chad/sarah/qwen-backend/server/.venv/bin/python -m pytest -q -p no:cacheprovider tests
```

**166 passed, 80 subtests passed, one existing aiohttp `NotAppKeyWarning`.** A focused run of runtime, direct conversation, ACP/config, LLM config, security, HTTP/reconnect, proxy/provisioning, speech/clock and publication tests passed **144 tests and 80 subtests**, with the same warning. No timing flake occurred in these final runs; earlier HA timing reports above concern the now-removed integration tests. Intermediate development runs found stale dispatcher test helpers/assertions; those were rewritten rather than dropping general speech, stream or safety coverage.

A clean temporary export of Git-tracked server files exactly matched all **77** `PUBLICATION-MANIFEST.txt` entries. Running `python tools/privacy_scan.py <export>` returned **0 findings**. The obsolete Maton gateway endpoint exception was removed from the scanner and its rejection is covered by a negative control. `git diff --cached --check` passed.

Android compatibility was assessed against its unchanged `Bridge.kt`: protocol 1 routes and fields for auth/health/conversations/WAV submit/lookup/poll/audio/cancel remain. Health's legacy bridge capability fields are false for both backends. The legacy confirmation schema/route stays authenticated and ownership-checked, always returning HTTP 403 `confirmation_unavailable`; no new turn requests confirmation. A synthetic legacy database test verifies historical tables/records and device identity survive reopen, while an interrupted turn becomes uncertain without replay.

No real model/household/agent action, live speech-model test, APK/native rebuild, deployment, service restart, Dockerops change, or modification of existing private state was performed. Existing APK/package/signing and license notices remain. Offline mocks do not establish physical-device behavior; ACP agents retain their own privileges and cancellation is not rollback. Source changes are for review, not deployment.

Chad's Agent — 2026-10-28. Local development validation, not a production or Android-device release.

## Live server

Started the real Python TLS server on `https://127.0.0.1:8787` with private device provisioning and a seven-day local test CA/certificate. All optional integrations were disabled. The server used the existing local llama.cpp endpoint and loaded `ggml-org/Qwen3.8-27B-GGUF:Q4_K_M` model. The provider token was obtained privately; no credential pool or Hermes source was present in runtime configuration.

Downloaded the public Whisper JFK test clip from `https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac` and converted it to 16 kHz mono PCM WAV. Explicitly downloaded local Whisper base and Kokoro model/voice assets into ignored `.build/` directories; runtime does not download them.

```sh
cd server
.venv/bin/python -u tools/smoke_voice.py \
  --state .state --wav .state/test.wav --ca .state/server.pem --require-audio
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1 .state/smoke-reply.mp3
```

Passed:

- Certificate/hostname verification without insecure TLS overrides.
- Unauthenticated health rejected; device-authenticated health reports protocol 1 and ready.
- Conversation creation, completed WAV upload, duplicate request returning the same turn, and request lookup.
- Real local Whisper transcript: “And so my fellow Americans, ask not what your country can do for you, ask what you can do for your country.”
- Real local Qwen response discussing the JFK quote.
- Real local Kokoro synthesis, authenticated MP3 download: 43,436 bytes; FFprobe duration 10.752 seconds.
- No tools, HA, notes, calendar or TV were enabled or called.

The first live run caught a faster-whisper/PyAV incompatibility (`metadata_errors` removed in PyAV 19); `av==16.1.0` is now pinned. A text-only intermediate run confirmed STT/Qwen before optional SoundFile was installed in the isolated TTS environment. The final run required audio and passed.

## Offline checks

Full offline suite: **270 passed, 44 subtests passed**, in 67.85 seconds on Python 3.12.15. Two warnings: upstream aiohttp request-key style and an inherited multithreaded-fork power-helper probe. No failed tests. Command: `.venv/bin/python -m pytest -x -vv -o faulthandler_timeout=12`. The diagnostic timeout printed a stack during a slow inherited probe, but that probe and the suite completed successfully.

Earlier runs showed intermittent HA timeouts/hangs with AnyIO 4.15.1. A hang also reproduced against the unchanged upstream HA tests in the same environment. The final successful suite used pinned `anyio==4.8.0`; the precise upstream/dependency timing cause was not fully isolated. Test fixture polling was slowed to avoid exceeding the real bridge device rate limit. Configuration and tracked-source privacy checks also passed independently.

The publication-hygiene test scans Git-tracked source copied into a clean directory, not the working tree's private state, models or dependency environments. The scanner's synthetic fail-closed tests still verify unmanifested files, secrets, forbidden directories and invalid inventories. Added source is explicitly listed in the server publication manifest. The upstream reviewed PNG is preserved unchanged.

## Limits

- Android source imported unchanged; no APK build, installation, phone microphone/wake-word/playback, or device pairing was tested.
- Current listener is loopback-only and managed by the agent's process harness, not a persistent service/deployment. It is not reachable from a phone as configured.
- Test certificate/key, device token, provider token, models, audio, SQLite state and transcripts are not committed. A real deployment needs deliberate network/TLS configuration and a service lifecycle.
- No real integration/tool action was performed; those regressions use mocks/loopback services.
- Dependencies and third-party model/voice rights require separate distribution review. This validation is not a security certification.
