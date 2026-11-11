# Verification

## Offline/synthetic suite

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m pytest -q
sh -n docker-entrypoint.sh
```

Dependency installation is separate from test execution. Tests remove inherited bridge/integration configuration, forbid non-loopback socket connections, and use temporary SQLite state and synthetic identities. No password store, real token, provider, live agent, physical microphone, local speech-model asset or deployment is needed.

Coverage includes generic socket/stdio ACP, protocol/session ownership, durable reload without history replay, assistant-only text, denied client execution/permission requests, bounded streams/deadlines, warm owner isolation/expiry, cancellation/spawn cleanup, new-conversation boundaries, idempotency and lost-ack lookup, private provisioning, HTTP TLS/proxy argument guards, optional TTS text preservation, sentence ordering/ack/backpressure, native STT admission ownership, warm synthetic voice-process cleanup and diagnostic validation/quotas.

The fixture's “MP3” bytes are deliberately synthetic and do not establish codec/audio quality. Whisper/Kokoro units mock local model/native APIs or use disposable synthetic child processes; none download/load production models. Container/proxy files receive static/argument checks only, not deployment or certificate verification.

## Bridge-only publication gate

`PUBLICATION-MANIFEST.txt` is the exact bridge source-export inventory; Android has separate source/assets/notices. Stage only the inventory into a **fresh disposable directory**, never an active service/state directory:

```sh
review_dir=$(mktemp -d)
python - "$review_dir" <<'PY'
from pathlib import Path
import shutil
import sys
root = Path.cwd()
target = Path(sys.argv[1])
for entry in (root / 'PUBLICATION-MANIFEST.txt').read_text().splitlines():
    source = root / entry
    destination = target / entry
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
PY
python tools/privacy_scan.py "$review_dir"
```

Review the manifest itself first. Do not scan a working directory and waive its private/unmanifested files; the scanner intentionally rejects those. A clean scan is only heuristic and does not prove absence of secrets or permission to publish. Do not include Android's upstream binaries in this bridge-only export or infer that their provenance has been checked by this gate.

## Combined integration review

The combined branch merges bridge `88caf08` and Android `8f1ed68` from the ancestry-preserving upstream baseline `647f86d` (`fa993b1` tree plus an ancestry-only merge of old fork `adbbd42`). Old fork code was read with `git show`, not edited or merged into the upstream tree again.

On the integration host, a disposable Python 3.14 environment was created with `uv venv /tmp/sarah-integration-venv` and declared requirements installed using `uv pip install --python /tmp/sarah-integration-venv/bin/python -r requirements.txt -r requirements-dev.txt`. `/tmp/sarah-integration-venv/bin/python -m pytest -q` passed **137 tests and 124 subtests**. That includes five Android source audits, not Kotlin execution. The exact bridge-only manifest was staged into a fresh `/tmp/sarah-integration-export.*` directory: its suite passed **132 tests and 86 subtests**, and `python tools/privacy_scan.py STAGED_DIRECTORY` reported **0 findings** (heuristic only). `python -m compileall -q bridge tests tools`, `sh -n docker-entrypoint.sh` and `git diff --check` also passed.

Independent cross-contract tests exercise WAV -> stub STT -> real disposable Unix ACP peer -> stub TTS -> sentence MP3 polling/download/ACK; exact session reload for a fresh ordinary follow-up; Stop during the agent versus Stop during speech; permission/delegated-dispatch refusal; deadline uncertainty; read-only lookup and no prompt replay. Shared `tests/fixtures/voice-relay.json` envelopes are asserted against HTTP responses and loaded by Android's `VoiceReplyTest`. The follow-up HTTP test checks fresh keys without the bridge-rejected legacy clarification header. The shared-envelope and follow-up Kotlin tests also passed in both variants during the JVM run below.

The environment initially lacked Java/SDK. After explicit user authorization, the coordinator installed Temurin JDK 17.0.21 and the integration agent installed public Android command-line tools, platform 35 and build-tools 35.0.0. The command-line ZIP matched its official repository SHA-1 inventory. Tools/cache were moved out of ephemeral local storage into `$HOME/tmp`; no sudo, secrets, signing keys or device access were used.

From `android/`:

```sh
export JAVA_HOME="$HOME/tmp/temurin-17"
export ANDROID_HOME="$HOME/tmp/android-sdk"
export GRADLE_USER_HOME="$HOME/tmp/sarah-gradle"
export PATH="$JAVA_HOME/bin:$PATH"
./gradlew --no-daemon --continue :app:testPhoneDebugUnitTest :app:testLenovoDebugUnitTest
./gradlew --no-daemon --continue :app:assemblePhoneDebug :app:assembleLenovoDebug
./gradlew --no-daemon :app:assemblePhoneRelease :app:assembleLenovoRelease
```

JVM result: **245 tests per variant, 490 total; 0 failures/errors/skips**. Both production and test Kotlin compiled. The first combined run had six phone and three Lenovo failures; all nine were independently reproduced from untouched upstream `fa993b1` exported to a disposable directory (250 tests per upstream variant). Review removed an invalid offscreen follow-up stage label that production validation rejected. Two stale tests now assert the existing read-only recovery contract: a matching terminal receipt resolves to ready without audio/replay; an uncertain receipt remains blocked. Three follow-up tests now assert disabled behavior on phone and exercise the full enabled path on Lenovo, rather than expecting Lenovo-only behavior on both. No tests were skipped or deleted to hide these failures.

Both debug assemblies reached signing validation but failed because the existing private `.local-review/review.jks` is absent. No replacement signing key was generated or retrieved. Both **unsigned release assemblies succeeded**, including vital lint. APK inspection verified package `com.serexe.sarah`, minSdk 26/targetSdk 35, version codes 53/67, the sole intended ARM64/ARMv7 ABI respectively, and all five required native libraries. `apksigner verify` rejected both as unsigned, as expected; these are build-validation artifacts, not installable signed releases or a source-reproducibility claim.

| Unsigned output under `android/app/build/outputs/apk/` | SHA-256 |
| --- | --- |
| `phone/release/app-phone-release-unsigned.apk` | `689902e6bf1d5003dde428cb498e085dd80a5fa26385cf1208fdbf4b285d086d` |
| `lenovo/release/app-lenovo-release-unsigned.apk` | `27f74c7c6bb268faa3f3dcfe095a7c2b140e5a284cec7dac82efac06fe87f1fb` |

Synthetic test reports, build logs and unsigned APKs are retained privately outside the disposable worktree. No APK is committed or published.

## Separate authorization required

Not performed: Docker image build/model downloads, container/service deployment, certificate/proxy reachability, real ACP/provider requests, Android install, physical wake/capture/playback, instrumentation/background/permission/OEM validation, key creation/rotation or production database changes. Run those only under an explicit live-validation plan. Signed debug assembly remains blocked on the operator's existing private keystore. Passing JVM tests and unsigned builds do not establish physical voice behavior.
