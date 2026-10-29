# Sarah speech bridge

Local Whisper transcription, ACP session relay, and optional Kokoro/FFmpeg synthesis for the Android voice client. ACP is the only/default backend. The agent owns its model, credentials, tools and skills.

## Setup

Use Python 3.12, a dedicated unprivileged account, a private state directory and one bridge process. From `server/`:

```sh
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
export SARAH_ACP_CWD=/absolute/agent/working/directory
export SARAH_ACP_SOCKET=/run/pi-acp/acp.sock
umask 077
.venv/bin/python -m bridge.provision_device --db .state/state.db \
  --device android --token-file /absolute/private/path/sarah-api-key
.venv/bin/python -m bridge.server --db .state/state.db \
  --cert /absolute/private/path/server.pem --key /absolute/private/path/server.key \
  --bind 127.0.0.1 --port 8787
```

Supply an existing private 40–256 character printable non-whitespace ASCII device key file. Provisioning stores its hash and rejects rotation/revocation mismatches. Certificates must match the Android-facing hostname. Pair Android with the HTTPS origin and device key; optionally import the private CA certificate, never its key.

### Configuration

`config/bridge.env.example` is not loaded automatically; export trusted values or use a private service-manager environment file.

| Variable | Behavior |
| --- | --- |
| `SARAH_BACKEND` | Optional compatibility assertion; only `acp` is accepted. |
| `SARAH_ACP_CWD` | Required absolute agent working directory. |
| `SARAH_ACP_SOCKET` | Absolute Unix socket path; choose this or command. |
| `SARAH_ACP_COMMAND` | JSON argv array for an owned stdio child, never shell parsing. |
| `SARAH_ACP_TIMEOUT_SECONDS` | Total request deadline, 1–600 seconds, default 120. |
| `R1_WHISPER_MODELS` | Local Whisper cache; default `.build/whisper-models`. |
| `R1_KOKORO_ROOT` | Assets plus `venv/bin/python`; default `.build/kokoro-audition`. |
| `R1_TIMEZONE` | IANA spoken-clock timezone; default UTC. Invalid zones fail startup. |

Obtain Whisper base explicitly; runtime never downloads assets or uses cloud speech:

```sh
.venv/bin/python -c 'from faster_whisper.utils import download_model; download_model("base", cache_dir=".build/whisper-models")'
```

For optional synthesis, create an isolated environment at `R1_KOKORO_ROOT/venv`, install `requirements-tts.txt`, and obtain `kokoro-v1.0.onnx` and `voices-v1.0.bin` in that root. [Dockerfile](Dockerfile) records pinned asset hashes. The worker uses Python `-I`; FFmpeg with libmp3lame must be at `/usr/bin/ffmpeg`. Missing Whisper fails voice turns; missing TTS preserves text replies. Review separate asset licenses before redistribution.

### Docker and TLS proxy

The [Dockerfile](Dockerfile) and entrypoint retain private-file API-key provisioning. Direct TLS is the default. Behind a trusted TLS proxy, explicit `--http --bind 127.0.0.1` permits loopback HTTP only; never expose unauthenticated ACP sockets or plaintext bridge traffic publicly. Configure hostname-valid TLS, phone/VPN routing and firewall deliberately. Forward `/v1/` without stripping the prefix and preserve the `Authorization` header. Android accepts an HTTPS origin, not a URL prefix. Host-loopback checks do not prove phone connectivity. See [Android build prerequisites](../android/README.md).

## Protocol and security

Protocol 1 retains authentication, health, conversation creation, WAV upload, read-only request lookup, polling, audio and cancellation. Integration confirmation routes and direct-model backends are removed. Existing ACP bindings and device keys remain valid; prior direct-model history requires a new conversation. There is no destructive database migration or automatic key rotation.

Bearer token possession authorizes the associated device. Keep credentials, TLS keys, SQLite transcripts/session metadata and reply media private, with restrictive permissions. Establish your own retention/backup policy; no retention scheduler exists. Revoke devices through trusted local administration using `Store.revoke`.

ACP delegates to an agent with its own privileges. Denial of client permission/filesystem/terminal requests is not an agent sandbox. Prompts and replies are untrusted. Cancellation cannot undo agent actions. Session binding is persisted before prompting; uncertain/interrupted outcomes do not trigger replay or a replacement session. This is not distributed exactly-once execution.

## Verification and publication

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests
python tools/privacy_scan.py
```

Tests use synthetic Unix/stdio/HTTP peers and disposable children; do not point them at real agents/accounts. Offline tests do not establish physical-device, live speech/agent or deployment behavior. No Android build or deployment is implied.

`PUBLICATION-MANIFEST.txt` inventories server source. The hygiene regression scans a clean copy of Git-tracked files; stage additions/deletions first. Missing/unlisted input, private/generated files, symlinks, binaries and forbidden directories fail the gate. Remove local generated output before a direct scan. Review manifest changes manually.

Privacy detection is heuristic, not proof. Independently review source, metadata and dependencies. A private literal list can be supplied with `--literal-file /absolute/private/file`; never commit that list or its values. Establish an owner-controlled vulnerability-reporting channel before public release.

## Licensing

Derived from [serexe/sarah-r1](https://github.com/serexe/sarah-r1) at `9794c41b201cc97001e575cb28a72b54489148bb`. Original project code remains MIT licensed, copyright © 2026 serexe. See [LICENSE](LICENSE) and [third-party notices](THIRD-PARTY-NOTICES.md). Dependencies, model/voice assets and branding retain separate terms. License selection is not publication approval or a legal certification.
