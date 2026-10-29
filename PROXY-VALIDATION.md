# Proxy/container validation

Chad's Agent — current source validation is in [VALIDATION.md](VALIDATION.md). [Proxy setup](server/docs/PROXY.md) documents the retained TLS/loopback HTTP, API-key provisioning, Dockerfile and entrypoint interfaces. Synthetic tests cover fail-closed binding and provisioning; this cleanup does not build images or deploy.

Earlier 2026-10-28 nginx/ACP/speech checks concern the previous source and are historical evidence only. Deployment notes remain in Dockerops `chaddev.lan/claws/sarah/VALIDATION.md`; they do not prove this branch is deployed or tested on a phone. No live probes or deployment changes were performed for this cleanup.
