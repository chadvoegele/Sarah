# Proxy/container validation

Chad's Agent — 2026-10-28.

- **297 tests + 72 subtests passed** in 66.67 seconds. One inherited aiohttp request-key warning. Earlier concurrent-build run had one inherited HA timing timeout; final full rerun passed unchanged.
- New tests enforce default TLS, literal-loopback-only HTTP, private-file token validation, hashed/idempotent provisioning and refusal to silently rotate/revive existing device records.
- The real deployed HTTPS path through nginx passed missing/wrong/Basic-key rejection (403), correct Bearer authentication (200), public certificate/hostname verification, WAV upload, duplicate request identity, lookup, transcript/reply polling and authenticated MP3 download.
- Real local Whisper recognized a harmless synthetic connection-test command. The dedicated real Pi/ACP agent replied **“Sarah is connected.”**; real Kokoro returned a **5,517-byte / 1.258667-second** MP3. This was not a synthetic ACP peer.
- The first real-agent test exposed startup/version/MCP banners arriving as late assistant chunks. The client now ignores the exact advertised prelude and typed UI notifications; a regression test and clean live retest passed.
- Restarted the new agent, memory and bridge without re-provisioning secrets. The same Sarah key authenticated, the same ACP session reloaded, and a fresh follow-up returned the clean reply and audio. Pi session records show zero tool calls in these validation conversations.
- The backend is loopback-only; its LAN address/port is not accepting connections. Existing llama HTTPS health and existing Dex containers remained healthy; no original lan0 deployment/Matrix client was changed.

Detailed deployment/mount/rollback notes are in Dockerops `chaddev.lan/claws/sarah/VALIDATION.md`, MR `chad/dockerops!95`. This server change is MR `chad/sarah!3`, stacked on ACP MR !2. Review worktrees/images are running without merging those branches.

No APK change is necessary: Android uses an HTTPS origin and the existing Bearer device token, with no private CA required for a publicly trusted frontend certificate. No phone/VPN-client test or real household/tool mutation was performed. VPN clients still need the correct DNS/routes to the gateway. Protect the key: the ACP agent's own privileges are not sandboxed by client permission denial. No tokens, credentials, models, runtime DBs or validation audio were committed.
