# HTTPS reverse proxy and container deployment

Chad's Agent — implementation notes.

The existing Android client already sends `Authorization: Bearer <device token>` on every API call. That is the server's API key, not HTTP Basic auth. A TLS reverse proxy should forward this header unchanged; no second key or APK auth change is needed. Keep the Sarah key separate from other services' keys.

## Internal transport

TLS remains required by default:

```sh
python -m bridge.server --db state.db --cert server.pem --key server.key
```

An explicit proxy-only mode is available:

```sh
python -m bridge.server --db state.db --http --bind 127.0.0.1 --port 8789
```

`--http` rejects non-loopback/hostname binds and certificate options. Do not expose plaintext bearer credentials on a LAN/VPN listener. The supplied container uses host networking so its loopback listener is directly reachable by a host-network nginx, but not by remote clients. Only nginx's HTTPS port should be reachable over LAN/VPN.

## Device key provisioning

Provision from a private file without printing or embedding the token in command arguments:

```sh
python -m bridge.provision_device --db state.db --device android --token-file /private/api-key
```

The token must be 40–256 printable non-whitespace ASCII characters. SQLite stores its hash. Repeating the same provisioning is idempotent; a different or revoked token is rejected rather than silently rotated. Rotation/revocation remains a deliberate local administrative operation, not an unauthenticated HTTP endpoint.

The container entrypoint provisions/verifies `/run/secrets/sarah_api_key` before starting against its persistent `/var/lib/sarah/state.db`. Do not put the key into the image, tracked Compose environment or logs. The Docker build explicitly downloads local Whisper/Kokoro assets; runtime has no cloud speech fallback. The public Kokoro model/voice archives are checksum-verified. Review their separate licenses before redistribution.

## Proxy paths and APK configuration

The client accepts an **HTTPS origin**, not an arbitrary URL prefix. Route `/v1/` on the chosen HTTPS host to the backend **without stripping `/v1`**. For example:

```nginx
location /v1/ {
    client_max_body_size 4m;
    proxy_set_header Authorization $http_authorization;
    proxy_pass http://127.0.0.1:8789;
}
```

Enter `https://bridge.example.invalid` and the Sarah device/API token in Android Connection settings. Do not enter an agent/Codex/llama credential. With a publicly trusted HTTPS certificate, leave the private-CA field empty. DNS and routing must make this host reachable from the phone/VPN; a successful test from the bridge host does not prove a particular VPN client's configuration.

The ACP backend, tool trust and persistent session behavior remain documented in [ACP.md](ACP.md). The app is independent of which server backend is selected.
