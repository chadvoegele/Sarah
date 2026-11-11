# Security boundaries

Sarah is an authenticated speech transport, **not an agent sandbox**. The configured ACP agent owns reasoning, tools, model/provider credentials and action authorization. A spoken request can cause that agent to act. Configure its skills, filesystem/network privileges and confirmation policy independently.

The bridge contains no local semantic command dispatcher, bridge-owned integration credential loader, direct model API, Hermes policy/profile launcher, research/mail service, clock-answer fast path or phone action envelope. It advertises no ACP filesystem/terminal capabilities, denies client permission requests and returns method-not-found for unsupported delegated execution requests. Assistant prose is displayed/spoken, never evaluated as code or a device command.

## Required deployment controls

- HTTPS with hostname verification. Explicit HTTP is permitted only on literal loopback behind a trusted TLS proxy. Every endpoint, including health/diagnostics, requires the bearer token; forwarded headers never authorize a device.
- Private per-device tokens, provided through an existing file, not command-line values/URLs. The database stores hashes and honors revocation. Re-provisioning never rotates a different token or restores a revoked one.
- A private state directory and backups; database/media files contain private dialogue and voice data. Media/scratch is owner-only. Whole-response audio and history currently require an operator retention policy; do not assume automatic deletion. Diagnostics expire after seven days with per-owner/global quotas.
- A trusted local ACP socket or explicit executable argv. Never derive endpoints, executable paths, workspace or arguments from user/agent text. Stdio uses no shell; bridge-specific environment variables are not passed to the child. Limit all other inherited environment and OS privileges yourself.
- Minimal network exposure and no access/body/token logs. Do not give the bridge provider accounts, user home/password stores, container-management sockets or arbitrary integration secrets.

## Ownership and uncertainty

All conversation/turn/request/audio/cancel/report reads and writes enforce authenticated device ownership. Read-only lookup cannot admit or replay work. Idempotency binds device, request key, conversation and upload hash. Concurrent voice work is refused, not queued. The admission slot remains owned through native STT and subprocess cleanup.

ACP session identity is durable before prompting and isolated per device/conversation. Timeout, cancellation, disconnect or crash during an agent turn means **unknown outcome**, not permission to replay or create a replacement. Cancellation sends best-effort ACP cancel, kills/reaps an owned stdio process group and stops local output; it cannot undo agent-side effects. Socket agents are independently managed and are not killed. Reconcile actions externally before explicitly starting a new conversation.

Old conversations/sessions are never silently migrated or reused. Additive schema changes preserve historical rows/audit tables; the new boundary marker is granted only when explicitly creating a new conversation. Unknown legacy configuration fails closed. No destructive database or agent-session migration is provided.

## Limits and evidence

WAV format/duration/size, authenticated request rates, protocol frame/stream/answer sizes, ACP deadlines, sentence sequence/backpressure/output bounds, diagnostics schema/quotas and owned process cleanup are covered by disposable synthetic tests. Raw agent errors, tool/thought output and protocol payloads are not exposed as speech or normal logs. Completed assistant text remains untrusted text; it is not proof of an action's success.

Synthetic tests do not establish protection against a compromised bridge host/agent, physical microphone privacy, Android OEM background behavior, real TLS/proxy deployment, real provider compatibility or speech-model vulnerabilities. Review exact dependencies and assets before shipping. Publication scanning is heuristic and only covers the staged bridge export, not Android binary/model provenance. Report suspected vulnerabilities privately to the repository owner without including tokens, audio, raw dialogue or private service addresses in public reports.
