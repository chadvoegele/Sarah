# Sarah speech bridge

Local Whisper transcription, ACP session relay, and optional Kokoro/FFmpeg synthesis for the Android voice client. ACP is the only/default backend. Run `python -m bridge.server` with the existing TLS options, or explicit loopback HTTP behind a TLS proxy. Private file-based device provisioning remains `python -m bridge.provision_device`.

[Setup](docs/SETUP.md) · [Configuration](docs/CONFIGURATION.md) · [Architecture](docs/ARCHITECTURE.md) · [ACP](docs/ACP.md) · [Proxy and Docker](docs/PROXY.md) · [Security](SECURITY.md)

Protocol 1 basic voice retains authentication, health, conversation creation, WAV upload, request lookup, polling, audio and cancellation. Integration capability flags and confirmation routes are removed. Existing keys and ACP bindings are preserved; interrupted requests become uncertain without replay. Databases need no destructive migration; historical integration data stays inert. Direct-model conversations need a new conversation after configuring ACP.

From this directory, using Python 3.12 with `requirements.txt` and `requirements-dev.txt` installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests
```

Synthetic Unix/stdio/HTTP peers exercise production ACP and SpeechRuntime interfaces, including auth/ownership, idempotency, recovery, cancellation, deadlines, output limits, permission denial, metadata filtering and text-only replies. Stage source additions/deletions before the tracked-publication test. [Verification](docs/VERIFICATION.md) describes the publication gate and validation limits.

The bridge derives from `serexe/sarah-r1` at `9794c41b201cc97001e575cb28a72b54489148bb`. The inherited native client, power helper, packaging and direct-model runtime have been removed. Generic spoken Markdown/currency/clock formatting remains at the synthesis boundary. Legacy `R1_*` speech path/timezone names remain for deployment compatibility.

Original project code remains MIT licensed, copyright © 2026 serexe. See [LICENSE](LICENSE), [license scope](LICENSE-STATUS.md) and [third-party notices](THIRD-PARTY-NOTICES.md). Dependency and speech-asset licenses remain separate.
