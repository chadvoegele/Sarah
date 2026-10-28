# Direct dependency record (not a license clearance)

Recorded from local Gradle declarations; versions/claims below require upstream license and transitive review before redistribution. Screenshot regression adds Android instrumentation-test-only dependencies.

| Use | Dependency | Declared version | Preliminary upstream license family |
|---|---|---|---|
| Build | Android Gradle plugin | 8.9.2 | Apache-2.0; confirm components |
| Build | Kotlin Android + Compose plugin | 2.0.21 | Apache-2.0; confirm components |
| Runtime | Compose BOM | 2025.04.01 | AndroidX Apache-2.0 |
| Runtime | activity-compose | 1.10.1 | AndroidX Apache-2.0 |
| Runtime | compose ui / material3 / foundation | BOM-managed | AndroidX Apache-2.0 |
| Runtime | lifecycle-viewmodel-compose / lifecycle-runtime-compose | 2.9.0 | AndroidX Apache-2.0 |
| Runtime | kotlinx-coroutines-android | 1.10.2 | Apache-2.0 |
| Runtime | OkHttp | 4.12.0 | Apache-2.0 |
| Runtime (external build input, not committed binary) | sherpa-onnx AAR | 2.0.1 | Apache-2.0; ONNX Runtime MIT with additional third-party terms. See KWS-DEPENDENCIES.md and app/src/main/assets/licenses/. |
| Test | JUnit | 4.13.2 | EPL-1.0 (with secondary license; inspect upstream) |
| Test | MockWebServer / okhttp-tls | 4.12.0 | Apache-2.0 |
| Test | org.json | 20240303 | JSON.org license (“The Software shall be used for Good, not Evil”); test-only, not OSI-approved |
| Instrumentation test | androidx.test.ext:junit / androidx.test:core / androidx.test:runner | 1.2.1 / 1.6.1 / 1.6.2 | AndroidX Apache-2.0; confirm transitive components |

Android SDK/platform and Gradle wrapper distributions are separate toolchain inputs. This is an inventory, **not** a lockfile, transitive SBOM or permission to distribute. `org.json` is test-only; Android platform supplies runtime JSON. Publication update: owner-controlled source and owner-approved launcher artwork are now MIT, Copyright (c) 2026 serexe; see LICENSE. This does not relicense third-party components. Current source is build21; see README.md and CODE21-PUBLICATION.md for publication/build boundary. Existing code3/code8 release and covered-source documents concern separate historical artifacts, not an APK generated from this tree.
