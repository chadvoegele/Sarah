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

On the integration host, a disposable Python 3.14 environment was created with `uv venv /tmp/sarah-integration-venv` and declared requirements installed using `uv pip install --python /tmp/sarah-integration-venv/bin/python -r requirements.txt -r requirements-dev.txt`. `/tmp/sarah-integration-venv/bin/python -m pytest -q` passed **137 tests and 124 subtests**. That includes five Android source audits, not Kotlin execution.

Independent cross-contract tests exercise WAV -> stub STT -> real disposable Unix ACP peer -> stub TTS -> sentence MP3 polling/download/ACK; exact session reload for a fresh ordinary follow-up; Stop during the agent versus Stop during speech; permission/delegated-dispatch refusal; deadline uncertainty; read-only lookup and no prompt replay. Shared `tests/fixtures/voice-relay.json` envelopes are asserted against HTTP responses and loaded by Android's `VoiceReplyTest`. The follow-up HTTP test checks fresh keys without the bridge-rejected legacy clarification header. The new Kotlin tests are source only until the following build blocker is resolved.

Both commands were attempted from `android/`:

```sh
./gradlew --no-daemon :app:testPhoneDebugUnitTest :app:testLenovoDebugUnitTest
./gradlew --no-daemon :app:assemblePhoneDebug :app:assembleLenovoDebug
```

Both stopped before Gradle/compilation: `JAVA_HOME is not set and no 'java' command could be found in your PATH`. Java, javac, Kotlin, Gradle and sdkmanager were absent from PATH; JDK/SDK checks under `/usr/lib`, `/usr/local`, `/opt`, `/mnt`, `~/Android` and `~/.gradle` found no usable toolchain. `adb` alone is not a build toolchain. JAVA_HOME/ANDROID_HOME/ANDROID_SDK_ROOT were unset. No signing material was read, created or retrieved. No Kotlin/JVM result or APK is claimed. Historical upstream JVM failures remain unverified rather than counted as passing.

## Separate authorization required

Not performed: Docker image build/model downloads, container/service deployment, certificate/proxy reachability, real ACP/provider requests, Android install, physical wake/capture/playback, instrumentation/background/permission/OEM validation, key creation/rotation or production database changes. Run those only under an explicit live-validation plan. Android compilation remains a tooling blocker, not physical validation and not a source-audit pass.
