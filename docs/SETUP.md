# Bridge setup (operator review only)

These examples are not deployment approval. Do not create/rotate keys, install on a device, contact a live agent/provider or modify a production database as part of source validation.

## Local service

1. Install Python dependencies from `requirements.txt`. Use a separate Kokoro environment with `requirements-tts.txt`, its native dependencies, an existing approved model/voice bundle and FFmpeg. Models are not acquired at runtime.
2. Configure a separately managed ACP v1 socket agent, or a trusted executable argv in `SARAH_ACP_COMMAND`. Its tools and provider configuration are outside Sarah.
3. Arrange an existing private state directory and existing private device-token file. Run the following only when explicitly authorized, with paths supplied by the operator:

   ```sh
   umask 077
   python -m bridge.provision_device --db /srv/sarah-state/state.db \
     --device android --token-file /etc/sarah/device.token
   ```

   Surrounding file whitespace (including LF/CRLF line endings) is stripped before validation. The token itself must contain 40–256 printable ASCII characters without whitespace; files larger than 4096 bytes are rejected. The token is hashed. Re-provisioning the same token is idempotent; a different, reassigned or revoked token fails without rotation. There is no admin HTTP provisioning route and no command here creates a token.
4. Start with TLS, or explicitly loopback HTTP behind a reviewed TLS proxy:

   ```sh
   python -m bridge.server --db /srv/sarah-state/state.db \
     --http --bind 127.0.0.1 --port 8789
   ```

   The ACP and speech environment settings must already be present. See `config/bridge.env.example`. This command is illustrative; validation uses disposable peers instead.
5. Pair Android with the HTTPS origin and that existing device token over a trusted channel. Use normal hostname verification and trusted/explicit CA validation, never an insecure TLS override.

## Docker/proxy assets

The root Dockerfile packages the root `bridge/`, not the old `server/` tree. It installs speech dependencies, explicitly downloads Whisper/Kokoro assets at **build time**, verifies the Kokoro release-file SHA-256 values, and runs as unprivileged UID 1000. It includes upstream MIT and dependency notices. The base image, OS and transitive dependency versions still require an operator supply-chain review; this is not a hermetic/reproducible build claim.

`docker-entrypoint.sh` uses umask 077, verifies/provisions the existing token from `/run/secrets/sarah_api_key`, and starts the bridge with `/var/lib/sarah/state.db`. State must be writable/private for UID 1000. The token must be readable by that UID and not publicly readable. Mismatched/revoked tokens stop startup.

`compose.example.yaml` is a Linux host-networking example. Its listener is loopback-only; no bridge port is published. Replace `/srv/sarah-state`, `/srv/acp-socket`, `/etc/sarah/device.token` and agent workspace with operator-reviewed paths. The socket directory must permit UID 1000 to connect. Mount only the intended socket/state; do not mount user homes, password stores, Docker sockets or integration/provider secrets into the bridge. The example uses read-only rootfs, private temporary scratch, dropped capabilities and no-new-privileges. Stdio agents are not installed in this image; provide your own reviewed image/executable if using that transport.

`config/Caddyfile.example` shows TLS termination to loopback. Use a real hostname/certificate configuration. Preserve Authorization, refuse large uploads and avoid request-body/token logging. The proxy must reach the same host loopback as the bridge. Do not weaken the application to `--http --bind 0.0.0.0` to work around networking problems.

## Existing state

Back up state before any approved upgrade. Startup makes only additive schema changes and marks interrupted turns uncertain; it does not delete or import legacy history, clear revocation or mutate the agent database. No legacy migration command exists. Keep the old history for read-only lookup and explicitly create a new conversation. Do not manually mark an uncertain binding ready to force a retry.

The earlier fork's deployed source lived under `server/`; update build context, command/module paths and service configuration explicitly for the root `bridge/` layout. Preserve the existing private state mount, token file, device identity and proxy HTTPS origin. The example entrypoint provisions device `android`; if existing state assigns that token to a different device, startup deliberately fails rather than reassigning it. Have the operator supply a reviewed entrypoint/configuration for that identity; do not rotate or replace the token to work around the check.

## Android prerequisites and rollback

Android needs JDK 17, Android SDK platform/build-tools 35, the Gradle dependencies, pinned sherpa AAR and the existing wake model assets/notices. Both debug variants require the operator's existing private `.local-review/review.jks` and signing-pass configuration under `android/`; do not create signing keys just to run source checks. See `android/README.md` for exact JVM/assembly commands and ABI/version limitations. No install is authorized here.

For a separately approved upgrade, snapshot the private bridge state consistently with SQLite WAL and preserve the previous service image/configuration and signed APK. Additive tables do not make old and new agent sessions interchangeable. Rollback means an operator-reviewed restoration of a matching service/configuration/state snapshot, not a destructive down-migration or running both bridges against the same writable database. Stop and reconcile outstanding work first: restoring state cannot undo agent actions, and uncertain prompts must never be replayed. Keep pairing identity/revocation intact; explicitly start a new conversation across backend boundaries. Android downgrades and signature changes are not a safe automatic rollback; preserve encrypted state and consult the variant/version constraints before any device change. Old local alerts/media must be stopped on the old app before an authorized upgrade; this refork does not clean them up.

This change has not built/deployed a Docker image, installed an APK, probed private services or exercised physical audio. Use the synthetic verification procedure first and obtain separate authorization for live validation.
