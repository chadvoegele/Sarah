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

## Separate authorization required

Not performed by this source task: Docker image build/model downloads, container/service deployment, certificate/proxy reachability, real ACP/provider requests, Android build/install, physical wake/capture/playback, background/permission/OEM validation, key creation/rotation or production database changes. Run those only under an explicit live-validation plan. The integration agent must validate the combined Android/bridge branch; this branch intentionally leaves `android/` untouched.
