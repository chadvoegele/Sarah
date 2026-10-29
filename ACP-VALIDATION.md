# ACP backend validation

Chad's Agent — 2026-10-28.

## Regression suite

From `server/`, Python 3.12 with the merged requirements:

```sh
python -m pytest -q
```

**292 passed, 63 subtests passed in 67.10 seconds.** One inherited aiohttp request-key style warning. Includes the existing direct-Qwen, tool-receipt, local-speech, durability, cancellation and publication-hygiene tests.

New tests use a real temporary Unix-socket ACP peer and real disposable stdio subprocesses. They verify initialize/new/load/prompt framing, fragmented text, ignoring thoughts/tools/startup/replayed history, isolated device/conversation bindings, persisted reload across a new runtime/DB connection, denied permissions/delegation, malformed/oversized answers, incomplete turns, deadlines, disconnections, no replay/replacement, repeated cancellation, spawn-cancellation ownership and process reaping. HTTP tests cover WAV admission, backend metadata, ACP reply text, deduplication and cancel notification.

No real model/account, Dex prompt or tool action is used in the offline suite.

## Existing ACP socket compatibility probe

Connected to the existing local Unix socket and sent **only `initialize`** using the new client. It returned protocol v1 with `loadSession=true`. Closed the connection afterwards.

No `session/new`, `session/load`, `session/prompt`, permission approval, Matrix operation or deployment/configuration change was made by this probe. This proves handshake/framing compatibility, not a full real-Dex voice turn or production authorization model.

## Local speech integration

A temporary second HTTPS bridge on loopback port 8788 used the new ACP backend, real local Whisper/Kokoro assets, a public JFK WAV fixture, and an explicitly synthetic stdio agent. It did not use Dex or a live agent model. The synthetic reply identifies itself as synthetic.

The existing `tools/smoke_voice.py` exercises TLS validation, missing-token rejection, authenticated health, conversation creation, WAV upload, deduplication, request lookup, transcript/reply polling and authenticated MP3 download. The run passed: the real JFK transcript was recognized, the reply was “This is a synthetic ACP reply. The voice bridge is working.”, and authenticated MP3 download returned **15,500 bytes**, verified by FFprobe as **3.754667 seconds**.

Temporary credentials, session DB, agent fixture, models, audio and test certificate remain ignored/private. No generated artifacts or secrets are committed. The temporary ACP integration server is stopped after validation; the previously running direct-Qwen test server is not switched to ACP.

## Limits

- No Dex session was created or prompted, no Matrix session was attached, and no agent tool was authorized/tested live.
- No Dex/Docker deployment changes, socket-volume sharing or phone network setup are included.
- ACP delegates tool trust to the configured agent. Denied client permissions are not a sandbox; direct agent tools can still have broad host access.
- Android source/API is unchanged; no new APK or phone test.
- ACP sessions can be resumed only by agents supporting `session/load`. Uncertain sessions require a new Sarah conversation; no automatic retry, fallback, action rollback or session deletion is provided.
