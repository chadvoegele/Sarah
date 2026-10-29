# Server setup

Use Python 3.12, a dedicated unprivileged account, a private state directory and one bridge process. Install `requirements.txt`; add `requirements-dev.txt` for tests. Configure an ACP transport as described in [ACP.md](ACP.md). The agent owns its model, credentials, tools and skills.

## Local speech

Obtain the Whisper base model explicitly into `R1_WHISPER_MODELS` (default `.build/whisper-models` relative to `server/`). The runtime always uses `local_files_only=True`:

```sh
.venv/bin/python -c 'from faster_whisper.utils import download_model; download_model("base", cache_dir=".build/whisper-models")'
```

For optional synthesis, create an isolated Python environment at `R1_KOKORO_ROOT/venv` (default `.build/kokoro-audition/venv`), install `requirements-tts.txt`, and obtain `kokoro-v1.0.onnx` and `voices-v1.0.bin` in that root. [Dockerfile](../Dockerfile) records pinned model/voice download hashes. The worker invokes Python with `-I`; FFmpeg with libmp3lame must be at `/usr/bin/ffmpeg`. Review separate model/voice/dependency licenses before redistribution. Runtime never downloads assets or falls back to cloud speech. Missing Whisper fails the voice turn; unavailable TTS preserves the agent's text.

The existing `faster-whisper==1.2.1` and `av==16.1.0` compatibility pins are retained. The separate TTS worker pins are unchanged. Direct HTTP model transport pins were removed from declared requirements; speech packages may still depend transitively on HTTP libraries.

## Private pairing and startup

Supply a private 40–256 character printable non-whitespace ASCII key file. Provision it without putting its contents in process arguments or logs:

```sh
umask 077
python -m bridge.provision_device --db .state/state.db --device android --token-file /private/sarah-api-key
python -m bridge.server --db .state/state.db --cert /private/server.pem --key /private/server.key --bind 127.0.0.1 --port 8787
```

Certificates must match the Android-facing hostname. Pair Android with the HTTPS origin and device key; optionally import the private CA certificate, never its key. Keep tokens, SQLite, transcripts and media private. The removed native-settings generator is unnecessary; existing device DB records remain valid. Repeating file provisioning checks the same key and rejects rotation/revocation mismatches.

For a TLS proxy/container, use the existing [proxy setup](PROXY.md), image/entrypoint and API-key file contract. Direct TLS remains default; plaintext HTTP requires explicit literal loopback binding. Configure phone/VPN routing and firewall deliberately. A loopback check does not prove phone connectivity.

See [Android prerequisites](../../android/README.md) for app builds. This repository has no native Ubuntu Touch build or packaging target.
