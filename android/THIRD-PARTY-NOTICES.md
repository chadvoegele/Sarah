# Third-party notices / binary redistribution review

Root MIT applies only to serexe-owned material. All third-party rights and conditions remain separate. Exact in-APK notices are copied unchanged under `notices/assets/`, `notices/META-INF/`, and `notices/okhttp3/`; model README/provenance are under `notices/assets/kws/`. Additional upstream license files and verbatim attribution headers are retained under `notices/upstream-static/`, `notices/upstream/`, and `notices/THIRD-PARTY-HEADER-NOTICES.txt`. These supplemental headers are a conservative superset from pinned dependency archives, not SARAH implementation source or a complete SBOM.

## Verified model-specific terms — resolved

Official original model archive:
https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2

SHA-256 `f170013b4716e41b62b9bfd809687c207cef798ef9bc6534d524e17af9b6561a` verified from freshly downloaded bytes. All six shipped original files (README, encoder, decoder, joiner, BPE model and token list) match archive bytes. Its **model-specific README explicitly declares Apache License 2.0** and identifies GigaSpeech XL training and author repository:
https://www.modelscope.cn/pkufool/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.git

This is model-specific evidence, not inference from the engine's source license. `keywords.txt` is the SARAH-selected HEY SARAH token sequence; original encoder, not failed mobile-converted encoder, is shipped. No training audio/test WAVs are bundled. The declaration does not grant training-corpus audio rights or warrant training-data provenance.

## Native library provenance — established with explicit boundaries

Official sherpa-onnx v2.0.1 AAR:
https://github.com/k2-fsa/sherpa-onnx/releases/download/v2.0.1/sherpa-onnx-2.0.1.aar

SHA-256 `a8d09d1d32f3eb8520482c6d3d43fae674681c5b050385967c70a3c2c9bf0ee7` matches official GitHub API digest and fresh download. All six shipped sherpa C/C++/JNI libraries are byte-identical to AAR members. Both ONNX Runtime libraries differ in non-runtime ELF data from AAR members; **every SHF_ALLOC section** matches in name/size/hash. This supports packaging/stripping provenance, not whole-file equality. ELF dependencies resolve to bundled matching-ABI libraries or Android platform libraries; static inspection is not device execution.

- sherpa Apache-2.0: https://github.com/k2-fsa/sherpa-onnx/blob/v2.0.1/LICENSE
- Official Android ONNX pin (1.28.2): https://github.com/k2-fsa/sherpa-onnx/blob/v2.0.1/cmake/onnxruntime-android-aarch64.cmake
- ONNX MIT: https://github.com/microsoft/onnxruntime/blob/v1.28.2/LICENSE
- ONNX transitive notices: https://github.com/microsoft/onnxruntime/blob/v1.28.2/ThirdPartyNotices.txt

All three corresponding in-APK license/notice files match official tagged upstream bytes exactly. ONNX notices include mixed transitive terms, including Eigen/MPL and LLVM terms; ONNX MIT alone is not blanket clearance.

AndroidX graphics-path 1.0.1 official artifact:
https://dl.google.com/dl/android/maven2/androidx/graphics/graphics-path/1.0.1/graphics-path-1.0.1.aar

AAR SHA-256 `8ca4032b6d79b351f0b59ad4b580eddbb9423e1652f7c958830687f1eee2ec03`; both shipped graphics-path native libraries match all allocated ELF sections. APK version marker and official POM identify 1.0.1 and Apache-2.0. Current official native headers corroborate AOSP Apache attribution but are not claimed to be exact historical build source:
https://github.com/androidx/androidx/tree/androidx-main/graphics/graphics-path/src/main/cpp

## Statically linked dependencies — notices and covered-source supplements

Official sherpa v2.0.1 CMake explicitly links kaldi-native-fbank, utf8proc, kaldi-decoder, simple-sentencepiece and FST, and configures hclust/json. Sources:
https://github.com/k2-fsa/sherpa-onnx/tree/v2.0.1/cmake
https://github.com/k2-fsa/sherpa-onnx/blob/v2.0.1/sherpa-onnx/csrc/CMakeLists.txt

Fetched exact pinned archives and retained notices: kaldi-native-fbank 1.22.4 (Apache-2.0), simple-sentencepiece 0.7 (Apache-2.0 plus embedded third-party header terms), OpenFST 1.8.5-2026-07-09 (Apache-2.0), kaldi-decoder 0.3.0/kaldifst 1.8.0 (Apache-2.0), utf8proc 2.12.0 (MIT/Unicode terms), KissFFT commit `febd4caeed32e33ad8b2e0bb5ea77542c40f18ec` (BSD-3-Clause), hclust-cpp 2026-02-25 (BSD-style two-condition license). KissFFT COPYING and full LICENSES texts are both included; ONNX's notices lacked KissFFT/utf8proc/hclust names, so they were not assumed covered. Archive hashes were verified against tagged CMake pins where available. Copyright/license header excerpts are retained verbatim rather than replaced by owner MIT.

**Eigen/MPL gate resolved for this bounded redistribution:** [COVERED-SOURCE.md](COVERED-SOURCE.md) supplies recipient instructions and identifies the original hash-pinned Eigen archives plus the ONNX-specific source tree with upstream patches actually applied. The sherpa root module search path takes precedence over kaldi-decoder's standalone Eigen module: it points to 5.0.1. Eigen 3.4.0 is supplied conservatively as well, not asserted as a second effective selection. ONNX Runtime v1.28.2 pins a distinct Eigen commit and two patches; the supplemented source includes both, including the generic RandomImpl change. MPL-covered source remains MPL-2.0, with original notices retained. The APK is unchanged; no newer SARAH source is substituted. Exact SBOM/reproducibility or a maintainer-signed negative modification attestation is not an MPL prerequisite. Published upstream source/pins/patches support this practical assessment; undisclosed upstream changes are not ruled out.

Relevant upstream source locations (not an assertion that one is the complete corresponding source):
https://gitlab.com/libeigen/eigen/-/tree/5.0.1
https://gitlab.com/libeigen/eigen/-/tree/3.4.0
https://github.com/microsoft/onnxruntime/tree/v1.28.2

## JVM/runtime attribution

APK markers identify AndroidX activity 1.10.1, Compose 1.8.0, Material3 1.3.2, lifecycle 2.9.0 and coroutines 1.10.2. Historical dependency record identifies Kotlin 2.0.21 and OkHttp 4.12.0; these version declarations are not a complete recovered dependency lockfile. Apache license texts retained for Kotlin, coroutines, OkHttp and Okio. Public-suffix data is separate MPL-2.0 data with exact embedded NOTICE and upstream source URL https://publicsuffix.org/list/public_suffix_list.dat . No test-fixture audio, test-only JSON.org package, signing key or current Android source is staged.

Redistribution review cleared for the unchanged historical APK with these notices and the covered-source release assets. This bounded assessment is not legal advice, an exhaustive SBOM, proof of undisclosed upstream build state, or a guarantee of exhaustive license compliance.

## Direct dependency record (not a license clearance)

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
| Runtime (external build input, not committed binary) | sherpa-onnx AAR | 2.0.1 | Apache-2.0; ONNX Runtime MIT with additional third-party terms. See the provenance above and app/src/main/assets/licenses/. |
| Test | JUnit | 4.13.2 | EPL-1.0 (with secondary license; inspect upstream) |
| Test | MockWebServer / okhttp-tls | 4.12.0 | Apache-2.0 |
| Test | org.json | 20240303 | JSON.org license (“The Software shall be used for Good, not Evil”); test-only, not OSI-approved |
| Instrumentation test | androidx.test.ext:junit / androidx.test:core / androidx.test:runner | 1.2.1 / 1.6.1 / 1.6.2 | AndroidX Apache-2.0; confirm transitive components |

Android SDK/platform and Gradle wrapper distributions are separate toolchain inputs. This is an inventory, **not** a lockfile, transitive SBOM or permission to distribute. `org.json` is test-only; Android platform supplies runtime JSON. Publication update: owner-controlled source and owner-approved launcher artwork are now MIT, Copyright (c) 2026 serexe; see LICENSE. This does not relicense third-party components. See README.md for current build prerequisites and source-only verification limits. Existing code3/code8 release and covered-source documents concern separate historical artifacts, not an APK generated from this tree.
