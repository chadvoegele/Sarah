# Historical SARAH code8 — 0.1.7-handsfree-review

Proposed tag `historical-code8`; prerelease **true**, draft **false**, latest **false**. Public owner `serexe`. Historical binary-only debug review build, not stable/production ready and not a later background-repair candidate. Redistribution review cleared for this unchanged historical binary with the accompanying notices and Eigen covered-source supplements; this is not security, production-readiness or exhaustive legal certification. Obtain third-party source as described in [COVERED-SOURCE.md](COVERED-SOURCE.md).

Artifact: `sarah-code8-playback-repaired-arm64-x86_64-review.apk` (unchanged), 83,050,988 bytes, SHA-256 `4cb4efa8e6ba13f9eee7154830b84237cecfe8f94a7b9102a278df8e842f93f4`; package `com.serexe.sarah`, versionCode 8, ARM64+x86_64, minSdk 26, targetSdk 35. APK v2 verified with historical local-review certificate.

Complete matching original application source is unavailable. No source commit or reproducibility claim is made. No current Android source is distributed. Generated source archives would contain documentation/notices, not original app source.

## Historical acceptance, narrowly stated

Coordinator recorded five synthetic VM cases in one test (`OK (1 test)`, 53.324 seconds), loopback HTTPS 3 POST/3 audio GET, native synthetic-tone playback/cleanup, completion-only rearm, no rearm after explicit Stop/background, and bounded capture discard/background cases. Exact installed APK hash and cold-relaunch state were checked; bounded logs had no fatal markers. Narrow static/DEX receiver-callback repair review was accepted separately, not comprehensive security acceptance. Earlier trigger-path runtime used a different hash. No tests or device actions were repeated during archive preparation.

No physical acoustic wake/command/reply, real TTS audibility, real R1/bridge/home action, self-wake-resistance mission, locked/offscreen end-to-end, Doze/OEM reliability, or full timing/interruption matrix is proven. Foreground/unlocked path and notification fallback are the historical intent, not always-on guarantees.

## Known historical limitations and successor findings

- Code8 is debuggable. Plaintext reply MP3 temporary cache and best-effort deletion can retain audio after process death or cleanup failure. Encrypted settings do not encrypt this cache. Exact APK contains `reply-`, `.mp3`, `getCacheDir`/temporary-file path; historical focused review documents best-effort deletion and native-release-only `cleanRelease` semantics.
- Stop playback does not undo an already admitted server action. Complete network cancellation, wire replay/idempotency horizon, notification continuity, concurrent state mutation, and monotonic capture timing were not comprehensively established for this historical APK.
- **Successor-only reviews, not automatically code8 findings:** code9 offscreen implementation was rejected for timer-only command bounds, concurrent state/request-marker writes and notification-continuity failures, with additional in-flight HTTP cancellation/replay and plaintext-cache concerns. Code10 review identified a prepare/start-versus-Stop/lock/notification race. Code11 review identified application-driven FGS teardown before cleanup ACK and command-capture release being acknowledged too early. These reviewed changed implementations, not this immutable code8 APK; applicability and remediation on code8 are not established. No claim these are fixed, absent, or runtime-proven on code8.
- Missing application source prevents complete original-source security audit and reproducible rebuilding. String/metadata privacy scanning is not a security certification; encrypted/obfuscated/generated secrets and unknown identifiers may evade it.

Existing newer installations are not an upgrade target for this old versionCode. Preserve user data and pairing. No version/signature bypass, downgrade, uninstall or data-clearing instructions are offered.

MIT applies only to owner material; dependencies and model retain their respective terms and exact notices. Not a claim that the whole APK is MIT licensed.
