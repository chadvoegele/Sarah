# Sarah

Android voice assistant and Python HTTP/TLS speech bridge to an ACP agent. Local Whisper transcribes voice; the agent owns conversation context, model configuration, skills and tools; local Kokoro/FFmpeg supplies optional MP3 replies.

```text
Android → HTTPS Sarah bridge → local Whisper → ACP Unix socket/stdio agent
        ← text + MP3         ← local Kokoro ← assistant text
```

- `android/`: Kotlin/Compose app, imported from [serexe/sarah-android](https://github.com/serexe/sarah-android) at `e29456bc59fe26ecd482c434141f41433d2e8a90`.
- `server/`: speech bridge, derived from [serexe/sarah-r1](https://github.com/serexe/sarah-r1) at `9794c41b201cc97001e575cb28a72b54489148bb`.
- Original MIT copyrights/licenses and third-party notices remain in each subtree. Historical Android checksum/release records apply to their named upstream artifacts.

The supported product is Android + speech server + ACP client. The inherited Qt/QML/Ubuntu Touch client, power helper, native packaging, direct OpenAI-compatible model client and bridge-owned integration confirmation flow have been removed. This source change does not deploy a service or publish an APK.

## Setup

Use Python 3.12 and a dedicated unprivileged account. From `server/`:

```sh
uv venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt -r requirements-dev.txt
export SARAH_ACP_CWD=/absolute/agent/working/directory
export SARAH_ACP_SOCKET=/run/pi-acp/acp.sock
# ACP is the only backend; SARAH_BACKEND=acp remains accepted.

# Supply an existing private 40–256 character device key file. Never commit it.
umask 077
.venv/bin/python -m bridge.provision_device --db .state/state.db \
  --device android --token-file /absolute/private/path/sarah-api-key

# Supply private TLS material whose SAN matches the bridge hostname.
.venv/bin/python -m bridge.server --db .state/state.db \
  --cert /absolute/private/path/server.pem --key /absolute/private/path/server.key \
  --bind 127.0.0.1 --port 8787
```

Provision local speech assets explicitly; runtime never downloads or uses cloud speech. See the [server README](server/README.md) for setup and configuration. A JSON argv `SARAH_ACP_COMMAND` can replace the socket transport. Agent credentials and permissions belong to the agent.

The default listener is loopback. For phone access, configure deliberate routing, firewall and hostname-valid TLS. [Docker and reverse proxy setup](server/README.md#docker-and-tls-proxy) retains the existing image/entrypoint, API-key file provisioning and explicit loopback HTTP behind nginx. Android uses an HTTPS origin and the same revocable device Bearer token, with an optional explicitly imported private CA. [Android build prerequisites](android/README.md) include an external pinned AAR and private review signing configuration.

## Compatibility and recovery

Protocol 1 basic voice remains: authenticated health, conversation creation, WAV submit, read-only request lookup, polling, audio and cancellation. Health retains `connected`, `ready`, `reason`, `protocol` and `backend=acp`. Obsolete integration capability flags and `/confirmation` are removed; updated Android has no integration approval UI. Existing protocol-1 basic voice clients do not use those fields/routes.

ACP is now the default and only backend. `SARAH_BACKEND=llm` or any unsupported selection fails startup. Remove obsolete direct-model settings from private configuration and configure an ACP transport; prior direct-model conversations require an explicitly created new conversation. Existing ACP session bindings and device keys remain valid. There is no destructive database migration or automatic key rotation; old integration tables remain inert.

Session identity is persisted before prompting, then reloaded for followups. Uncertain/interrupted outcomes never cause replay or a replacement session. Backend identity changes fail closed. Cancellation cannot undo agent actions. ACP agents retain their own privileges; Sarah denies client permission/delegated filesystem/terminal requests, which is not an agent sandbox. See [protocol and security](server/README.md#protocol-and-security).

## Validation

From `server/` with test dependencies installed:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests
```

Tests use synthetic Unix/stdio/HTTP peers and disposable children. [Verification](server/README.md#verification-and-publication) describes publication checks and their limits. Fresh device, live model/tool, speech-asset and deployment proof are separate from these offline checks.
