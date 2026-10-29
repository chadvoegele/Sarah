# Architecture

Android captures bounded PCM16 WAV, saves request identity before sending, and authenticates to the speech bridge with its own revocable device token. The bridge admits one worker at a time, transcribes locally, sends the current transcript to the conversation's ACP session, and returns text plus optional local MP3.

`bridge.server` owns HTTP/TLS admission, device rate/body/audio limits, polling, read-only request lookup, audio and cancellation. Protocol 1 health retains `connected`, `ready`, `reason`, `protocol` and `backend=acp`; obsolete integration capability fields and confirmation endpoints are absent. Android's basic voice protocol does not depend on them.

`bridge.core.Store` owns hashed device credentials, conversations and durable idempotency records. Ownership is checked for conversation, turn, lookup, audio and cancellation. A reused request key must match both audio fingerprint and conversation. Startup makes unfinished turns uncertain; old integration tables remain untouched and inert. Request lookup never dispatches.

`bridge.acp_runtime.ACPRuntime` extends `SpeechRuntime`. `bridge.acp_client` speaks bounded newline-delimited ACP JSON-RPC over Unix socket or owned stdio. Dedicated session IDs and backend fingerprints are persisted before prompting. Followups load that session and send only the new transcript. Existing history without an ACP binding requires a new conversation. Interrupted/inflight/uncertain bindings cannot silently rebind or replay. See [ACP.md](ACP.md).

`bridge.runtime.SpeechRuntime` contains local Whisper and Kokoro/FFmpeg only. Markdown, money and clock formatting affect synthesis input, leaving the original answer in HTTP/SQLite. TTS uses private same-filesystem scratch, deadlines, terminate/kill/reap cleanup and atomic final MP3 publication. TTS failure leaves text usable. Local speech path/timezone environment names remain compatible.

ACP agents own their own models, privileges, tools, MCP and skills. Sarah has no dispatchers, confirmation mechanism or delegated filesystem/terminal support. It always denies client permission requests. Agent-authored action claims are prose; cancellation is not rollback. Keep credentials and session/media storage private and configure retention independently.
