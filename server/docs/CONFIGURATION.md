# Configuration

`config/bridge.env.example` is an example, not loaded automatically. Export trusted values or use a private service-manager environment file.

| Variable | Behavior |
| --- | --- |
| `SARAH_BACKEND` | Optional compatibility assertion; only `acp` is accepted and it is the default. |
| `SARAH_ACP_CWD` | Required absolute agent working directory. |
| `SARAH_ACP_SOCKET` | Absolute Unix socket path; choose this or command. |
| `SARAH_ACP_COMMAND` | JSON argv array for an owned stdio child, never shell parsing. |
| `SARAH_ACP_TIMEOUT_SECONDS` | Total connect/initialize/new-or-load/prompt deadline, 1–600 seconds, default 120. |
| `R1_WHISPER_MODELS` | Local Whisper cache root; default `server/.build/whisper-models`. |
| `R1_KOKORO_ROOT` | Local assets plus `venv/bin/python`; default `server/.build/kokoro-audition`. |
| `R1_TIMEZONE` | IANA timezone for spoken clocks; default UTC. Invalid zone fails import/startup. |

The three `R1_*` speech variables retain their existing names and defaults so current startup paths and Docker speech assets keep working. They enable no native-client behavior. No model/provider configuration is read by the bridge. Configure ACP agent credentials, tools, skills and restrictions on the agent itself.

Remove old direct-model and integration settings from private service configuration deliberately. Unsupported backend selectors fail startup. `SARAH_BACKEND=acp` deployments need no selector change. Existing direct-model history cannot be replayed into ACP; create a new conversation. Existing ACP bindings keep their backend-identity check. There is no key reset or destructive database migration.

No built-in retention scheduler exists for transcripts/media. Establish a private lifecycle/backup policy. Revoke devices with trusted local administration using `Store.revoke`; provisioning never silently overwrites or revives a key.
