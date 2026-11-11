# Sarah: Android speech interface to your ACP agent

Sarah relays speech to a generic Agent Client Protocol (ACP v1) agent. The agent owns reasoning, model choice, context, skills, tools and action authorization. Sarah does not interpret commands or execute actions on the phone or bridge.

```text
Android wake word + microphone
             |
             v
Authenticated HTTPS bridge -> local Whisper -> generic ACP agent
             ^                                      |
             |                                      v
Android playback <- local Kokoro + FFmpeg <- assistant text
```

The product includes wake/capture, local STT, ACP conversation, local TTS, playback, text/history, pairing, diagnostics and safe recovery. There is no direct model backend, required Hermes installation, bridge tool schema/dispatcher, integration confirmation, research/mail integration, local clock answer, schedule/timer execution or media-command execution. Requests such as “what time is it?” and “play music” are ordinary agent prompts. Agent text is not an action receipt or an instruction for Android execution.

## Source layout

- `android/`: Android voice client, wake/capture, playback, captions/history and pairing. See its dependency/model notices before redistribution.
- `bridge/`: HTTP/authentication, durable turn ownership, generic ACP socket/stdio, Whisper and warm Kokoro speech pipeline.
- `tests/`: synthetic peers, HTTP/security, session/cancel/restart, sentence audio and speech process ownership tests. No real providers or device required.
- `Dockerfile`, `docker-entrypoint.sh`, `compose.example.yaml`, `config/`: reviewable bridge packaging and private-provisioning/proxy examples, not a deployment.
- `docs/`: configuration, protocol, recovery and verification.

The root `bridge/` layout is retained from `serexe/sarah-r1` at `fa993b1`. Generic ACP transport and container/proxy support are adapted from the earlier fork's `server/` implementation. Native Ubuntu Touch app, power helper and packaging have been removed. Upstream `LICENSE` and copyright notices are preserved.

## Configure, do not guess

Set `SARAH_ACP_CWD` and **exactly one** of `SARAH_ACP_SOCKET` or `SARAH_ACP_COMMAND` (a JSON argv array). No endpoint, agent, provider, profile or model is selected from spoken text. See [configuration](docs/CONFIGURATION.md) and [setup](docs/SETUP.md).

Every HTTP endpoint requires a provisioned per-device bearer token over HTTPS. Direct HTTP is available only with explicit `--http` and a literal loopback bind behind a trusted TLS proxy. The token is provisioned locally from an existing private file; it is never accepted in URLs or command-line arguments, printed, implicitly rotated or un-revoked.

A healthy response indicates configuration, not a live agent/provider or speech-asset probe. Missing agent transport or local assets fails the request; there is no cloud speech/model fallback.

## Conversation and recovery boundary

Create a **new conversation** when switching from any incompatible old bridge/backend. Existing history and audit tables stay intact and readable; no automatic import, database rewrite, session replacement or prompt replay is performed. A new additive conversation boundary and backend identity prevent reuse of legacy sessions, including sessions from the earlier generic fork.

Each device/conversation is durably bound to one agent session before its first prompt. A completed session can be loaded after bridge restart if the agent supports `session/load`. A transport error, timeout, crash or cancellation during an agent turn makes its outcome uncertain. Sarah never retries or replaces that session. Reconcile actions with the agent, then explicitly create a new conversation if necessary. Stopping playback does not undo agent actions.

See [ACP and HTTP contract](docs/ACP.md), [architecture](docs/ARCHITECTURE.md) and [security](SECURITY.md).

## Synthetic verification

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
sh -n docker-entrypoint.sh
```

Tests use disposable Unix/loopback peers, synthetic WAV/MP3 bytes, temporary state and owned synthetic subprocesses. They do not establish real audio quality, wake-word accuracy, Android permission/background behavior, live agent compatibility or deployment correctness. See [verification](docs/VERIFICATION.md).

## Publication and licenses

`PUBLICATION-MANIFEST.txt` lists the **bridge-only source export**, not the Android APK, Android binary/model assets or a working directory. Stage exactly those files into a fresh directory and run `python tools/privacy_scan.py STAGED_DIRECTORY`. The scanner fails on unexpected files and is only a heuristic. Do not publish state, keys, recordings, diagnostics, build output or working-tree metadata.

`LICENSE` is the upstream MIT license, copyright 2026 serexe. Dependency, speech/wake model, codec and Android SDK/runtime rights are separate; see [third-party notices](THIRD-PARTY-NOTICES.md) and [license status](LICENSE-STATUS.md). This source change does not authorize deployment, device installation or release.
