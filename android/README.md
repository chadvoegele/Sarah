# S.A.R.A.H Android

Kotlin/Compose voice-assistant client for a separately operated HTTPS Sarah bridge. Current source declares `com.serexe.sarah`, `versionCode 26`, `versionName 0.1.25-soft-cue-review`. This is development source, not a new APK release or a reproducibility claim.

## This fork

Chad's Agent — the server uses ACP only. Basic protocol-1 voice/settings/playback/conversation behavior stays compatible with existing clients. The unused bridge integration-confirmation method/UI has been removed; unknown or historical confirmation outcomes stay uncertain and never trigger approval or resend. Health needs only protocol/readiness. Android JNI keyword/capture code and its licenses remain required. Version, signing and dependencies are unchanged.

## Behavior

- Foreground tap-to-talk, encrypted local pairing state, authenticated HTTPS bridge health/upload and reply playback; unknown upload admission is not blindly retried.
- Opt-in **Hey Sarah** offline keyword listener with Android foreground-service notification and explicit Stop; listener, capture and playback ownership gates guard handoffs. Manual tap remains fallback. Assistant-role gesture opens the app; it does not itself grant recording permission.
- Adaptive speech endpointing; no-speech or 30-second cap discards. The mic-ready cue starts after native recording reports ready and drains its acoustic tail before retaining command PCM.

Microphone requires opt-in/permission. Do not put provider or home secrets on the device; use a revocable bridge token. Local reset does not erase server history, and OS cache may retain temporary reply audio after process death. No live bridge endpoint, token, private CA, signer or personal transcript is included.

## Build and test

Use JDK 17, Android SDK 35 and the Gradle 8.11.1 wrapper. The compiled sherpa-onnx AAR is intentionally not in Git. Retrieve the official v2.0.1 artifact from [third-party notices](THIRD-PARTY-NOTICES.md) as `app/libs/sherpa-onnx-2.0.1.aar` and verify SHA-256 `a8d09d1d32f3eb8520482c6d3d43fae674681c5b050385967c70a3c2c9bf0ee7`; Gradle's `verifySherpaAar` task also rejects a mismatch. Model inference assets and required notices are included under `app/src/main/assets/`. SDKs, downloaded dependencies and caches are not included.

`app/build.gradle.kts` reads private `.local-review/review.jks` and `.local-review/signing-pass` files for signed debug builds. Supply your own local signing inputs outside Git; never publish a signer or password. A locally rebuilt APK is not claimed identical to an upstream review APK.

With these prerequisites installed, run from `android/`:

```sh
./gradlew testDebugUnitTest lintDebug assembleDebug
```

Unit tests use synthetic fixtures. Historical `ScreenshotPolicyTest.kt` remains, but private audio/instrumentation fixtures and test-server keys are not included. Offline tests do not establish physical-device, acoustic, background/OEM, live bridge or end-to-end reliability.

## Licensing and upstream records

Owner-controlled source/artwork: [MIT LICENSE](LICENSE). Third-party components and models retain separate terms. [Third-party notices](THIRD-PARTY-NOTICES.md) record sherpa/model provenance and declared dependency license families. `app/src/main/assets/licenses/` includes sherpa Apache-2.0, ONNX Runtime MIT and its third-party notices.

Preserved upstream [COVERED-SOURCE.md](COVERED-SOURCE.md), [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md) and checksum manifests and `notices/` concern the separate historical code8 artifact where stated, not an APK built from this tree. Eigen covered-source downloads remain linked. These records are not an exhaustive SBOM or legal certification. Images under `docs/screenshots/` are historical code3 emulator captures with synthetic transcript text, not current device or live-service proof. Original launcher artwork retains C2PA generated-media provenance, not user credentials. [Code3 third-party notices](CODE3-THIRD-PARTY-NOTICES.md) and the Gradle license remain preserved.

No APK or compiled native AAR is committed. Upstream attribution is in the [repository README](../README.md).
