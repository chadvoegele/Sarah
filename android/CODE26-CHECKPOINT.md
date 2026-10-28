# Code26 softer-cue source checkpoint — review, not release

Josh's phone feedback on the code26 review APK: “Much better. Go ahead and commit this version.” This commit snapshots current production/build/unit-test source from `/root/work/sarah-android` (a non-Git development tree), including cumulative code23–26 cue, adaptive endpoint and wake-stage changes since the code22 public checkpoint. It is **not** a fresh build, tag, APK release, or production promotion.

Exact user-reviewed APK association: SHA-256 `714f00380a8500a7b3b766343ac2547429db31af5f52b077ee6b6edacd2a2698`, package `com.serexe.sarah`, versionCode `26`, versionName `0.1.25-soft-cue-review`, ABIs `arm64-v8a` and `x86_64`. Signed review bytes remain outside Git; source snapshot is not a claim of bit-reproducible APK output.

Retained development evidence: 155 JUnit tests in 19 suites, zero failures/errors/skips; successful lint and debug APK build. The 180 ms mic-ready PCM cue was independently measured from compiled production code; Android code26 automated runtime was **not run** because the frozen code25 instrumentation fixture checks the old APK SHA and its one-shot marker had already been consumed. Phone feedback establishes subjective improvement only; no broader endpoint, full acoustic, or automated device regression claim.

Public-source boundary: production/build and unit-test changes only. Private instrumentation/audio fixtures, test-server key, personal endpoints, bridge tokens, private CA, signer, build caches/logs and APK are not included. Existing licensing/notices and historical source/release records remain unchanged; historical code8 APK-specific hashes do not describe code26.
