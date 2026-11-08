# Android golden v50

Owner-approved development baseline: the **original, exact v50 ARM64 review APK** and a reconstructed public Android source line. Golden means approved future baseline, **not** proven exact source-to-binary reproducibility or physical-device validation.

- APK: [SARAH-0.1.50+50-timer-countdown-arm64-review.apk](https://github.com/serexe/sarah-r1/releases/tag/android-golden-v50)
- Package: `com.serexe.sarah`; versionCode **50**; versionName `0.1.50-timer-countdown-review`.
- ABI: **arm64-v8a only**; signed local-review/debug build, debuggable, **not production-signed**.
- Size: **47,382,487 bytes**; SHA-256 `747d11dbc983816e5e30c493fbc9a1756f9a0fd057e915f60d120046cd7e0b54`.
- Signer SHA-256 `79c9b26baac4b0b60563430ebdf0023808cdf4e04b4d1d719fa950a7f3d5fa7d` (same local-review signer as v44).
- Annotated tag `android-golden-v50`; public reconstructed-source commit `076e9db75de04614112e51291d7f3e269271af86`, tree `0136e3e84787f69ddae53299789b12e5a50261de`.
- [Release](https://github.com/serexe/sarah-r1/releases/tag/android-golden-v50) · [Detailed source/proof boundary](android/GOLDEN50-SOURCE.md).

## Provenance boundary

The Android source was reconstructed after the approved APK build. The later alternate APK differs only in `classes3.dex`; the alternate raw timer-ID UI row was excluded. No immutable original pre-alternate source snapshot or build manifest establishes that the tagged source commit generated these APK bytes. The tag is **reconstructed development baseline**, not a reproducible-build assertion. GitHub's generated source archive is not a proven build input. The APK was **not rebuilt, resigned or substituted** for this publication.

The Android line includes local schedules, phone media, countdown/Cancel/Stop UI and v50 recovery safeguards. Public bridge source remains the sanitized mainline, not the private runtime; schedule/media backend routes and private configuration are **not published or deployed** by this promotion. Configure a compatible bridge separately. No private pairing, state, token, signing input or test-only key fixture is supplied. Earlier v44 [release](https://github.com/serexe/sarah-r1/releases/tag/android-golden-v44) remains historical.

## Actual checks and remaining limits

Original exact APK passed prior isolated synthetic VM countdown, exact Cancel, expiry and Stop. In this public source checkout, Kotlin compiled and focused new timer/schedule/media/recovery JVM tests passed. A broader three-class test run had **65 tests, 2 failures** in older `SarahViewModelTest` assertions (expected `done`/`uncertain`, observed `ready`); not a full green suite. Exact source-to-APK reproducibility, physical phone install/upgrade, acoustic alert/voice cancellation, live bridge integration, screen-off wake and battery behavior remain unverified. Privacy scan of outgoing blobs/metadata and APK ZIP/Dex/resources was bounded and heuristic, not a security certification. No bridge restart, phone install or VM test occurred during promotion.

For an existing installation, update-install without uninstall, clearing data or resetting pairing; package/signer compatibility alone does not prove upgrade success. **Future versionCode must exceed 50.** Branch from current `main` and preserve annotated tag plus exact approved APK. Licensing/dependency and historical source limits remain as documented.
