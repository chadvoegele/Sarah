# Sarah bridge

Python HTTPS voice bridge for Android, with local Whisper speech recognition, optional local Kokoro/FFmpeg replies, and either direct OpenAI-compatible model conversation or a persistent ACP agent session. See the [repository README](../README.md) for setup and [configuration](docs/CONFIGURATION.md) for supported environment variables.

The four inherited bridge-owned Home Assistant, SiYuan, Maton Calendar and TV integrations have been removed, including their model schemas, dispatch/approval helpers, rollback exports and enable flags. Direct Qwen is conversation only; unsupported tool calls fail closed. An ACP agent retains its own model, tools, MCP integrations and skills. See [ACP sessions and trust boundaries](docs/ACP.md).

Android-facing protocol 1 remains compatible: authentication, health, conversation creation, WAV submission, request lookup, turn polling, audio and cancellation. Health's legacy integration fields remain false, and the legacy confirmation route remains an authenticated HTTP 403 denial. Existing APK/package/signing are unchanged. Existing SQLite data is preserved; unfinished turns become uncertain without replay.

[Build and setup](docs/SETUP.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md) · [Proxy and Docker](docs/PROXY.md)

## Tests

From this directory, using an environment with `requirements.txt` and `requirements-dev.txt` installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests
```

Tests use synthetic configuration and mock/loopback peers, with no real model or household actions. Production-runtime streaming/deadline/process regressions, authenticated direct conversation/history/audio tests, and persistent ACP session/no-replay/cancellation/filtering coverage remain active. The privacy regression scans a copy of Git-tracked server files against `PUBLICATION-MANIFEST.txt`; stage newly added files before running it.

## Upstream reference client and provenance

This subtree was imported from `serexe/sarah-r1` at `9794c41b201cc97001e575cb28a72b54489148bb`. Its legacy Qt/QML Ubuntu Touch client, general speech/clock helpers, power helper and applicable native probes remain for reference. Native probes are separate from pytest; no device rebuild or compatibility claim follows from the Python suite.

`GITHUB-POST.md` and `docs/VERIFICATION.md` are historical upstream records. Their Codex/Hermes and bridge-integration descriptions do not describe current runtime behavior. The reviewed redacted screenshot is historical, not proof of an installation of this fork.

Original project code remains MIT licensed, copyright © 2026 serexe. See [LICENSE](LICENSE), [license scope](LICENSE-STATUS.md), and [third-party notices](THIRD-PARTY-NOTICES.md). Third-party dependencies and model/voice assets retain their own licenses and are not bundled or relicensed here.
