# Android + ACP cleanup validation

Chad's Agent — 2026-10-29, isolated feature branch based on `origin/main` at `f497d4b`.

## Current scope

Retained Android, HTTP/TLS speech server, local Whisper and Kokoro/FFmpeg, durable ACP Unix/stdio sessions, device provisioning and request recovery. Removed native Qt/QML/Ubuntu Touch/Rabbit client, power helper, Clickable/CMake packaging, native-only fixtures/tests/screenshot/publication content, direct OpenAI-compatible runtime/config/SSE, and integration confirmation API/UI/capability flags.

ACP is the default and only backend; existing `SARAH_BACKEND=acp` works and unsupported selectors fail. Basic protocol 1 voice remains compatible. The three historical `R1_*` speech path/timezone names, bridge module/startup, Dockerfile/entrypoint, loopback HTTP and API-key provisioning contract remain compatible. Existing ACP sessions and keys need no migration; direct-model conversations require a deliberate new conversation. Old database dispatch/approval tables are untouched and inert.

## Python

From `server/`, using the existing Python 3.12 environment without installing or changing packages:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/chad/code/code.voegele.me/chad/sarah/qwen-backend/server/.venv/bin/python -m pytest -q -p no:cacheprovider tests
```

**110 passed, 67 subtests passed, one existing aiohttp `NotAppKeyWarning`**, in 4.30 seconds.

Production ACPRuntime/ACPClient tests use real temporary Unix peers and disposable stdio children. They cover persistent session loading and identity, conversations/device isolation, denied client permissions/delegation, startup/thought/tool/UI filtering, malformed/oversized/incomplete output, total bytes/frame count including ignored metadata, initialization/prompt deadlines, disconnects, repeated/spawn cancellation and process reaping. Authenticated HTTP voice tests cover transcript/reply/audio, request lookup and idempotency, conflicting/foreign uploads, body/rate limits, removed confirmation route/health fields, cancellation and text preservation if synthesis fails. Store tests retain legacy database/recovery/no-replay checks.

Shared speech coverage uses SpeechRuntime directly: local-only Whisper configuration and transcript bounds, synthesis arguments, Markdown/currency/clock formatting, original displayed text, stage deadlines, repeated cancellation, terminate/kill/reap and atomic private output. Direct-model and native-only tests were removed; shared protection coverage was rewritten through ACP/speech interfaces.

Intermediate runs found two Kokoro tests still calling the deleted VoiceRuntime class; both now use SpeechRuntime. An initial test command used the repository root instead of `server/`; final results above use the correct directory.

## Android

Used existing local JDK/SDK 35 read-only, a private copy of the Gradle cache inside the ignored worktree, and a copied external sherpa-onnx AAR verified as SHA-256 `a8d09d1d32f3eb8520482c6d3d43fae674681c5b050385967c70a3c2c9bf0ee7`. No signer or shared cache was modified.

```sh
JAVA_HOME=/home/chad/.cache/sarah/android-build/jdk \
ANDROID_HOME=/home/chad/.cache/sarah/android-build/sdk \
ANDROID_SDK_ROOT=/home/chad/.cache/sarah/android-build/sdk \
GRADLE_USER_HOME="$PWD/.gradle-cache" \
PATH="/home/chad/.cache/sarah/android-build/jdk/bin:$PATH" \
./gradlew --no-daemon testDebugUnitTest lintDebug assembleRelease
```

**BUILD SUCCESSFUL. 158 unit tests, zero failures/errors/skips. Lint: zero errors, 18 warnings** (dependency-version, launcher-icon, SDK-check and KTX suggestions). Release assembly produced an unsigned APK only in ignored local build output; it is not committed, signed or uploaded. Build warnings include SDK XML version mismatch, two source deprecation warnings and inability to strip bundled native libraries. An initial offline attempt lacked cached Android instrumentation lint dependencies; the final command resolved build dependencies into the private cache and passed.

New tests verify obsolete server states stay uncertain without approval, resend or a polling loop; historical local confirmation state restores as uncertain. Existing health fixtures contain only protocol/readiness, matching the retained minimal contract. Capture, JNI keyword engine, playback, version, signing and dependencies retain their existing behavior/configuration.

## Publication and limits

The explicit server manifest exactly matches a clean export of all **45 tracked server files**. Its independent privacy scan returned **0 findings**; heuristic only. Relative Markdown links resolve and `git diff --cached --check` passes. The only new tracked file is the synthetic ACP fixture; no generated/private artifact was added. Publication tests still reject unlisted/missing files, generated/private files, unknown binaries, unreadable entries and symlinks, including ignored/hidden input. The obsolete native screenshot exception was removed; all server images are now rejected. Original MIT licenses, copyrights, Android attribution/model assets and third-party notices remain.

No live model/agent/tool/household call, real speech-asset inference, phone/device test, deployment, container operation, credential rotation, private runtime-state edit, Dockerops/system-config change or shared package modification was performed. No fresh dependency installation or container-image build was tested; Python checks reuse the specified environment. Offline checks do not prove phone networking/acoustics, physical action results or a production deployment. ACP agents keep their own privileges; client permission denial is not a sandbox and cancellation is not rollback.
