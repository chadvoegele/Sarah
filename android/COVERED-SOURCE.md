# Third-party covered source — historical code8

These supplements contain **Eigen source**, not SARAH application source. The original application snapshot remains unavailable. Root MIT covers owner material only. Eigen is primarily MPL-2.0; original per-file notices and other applicable terms are retained. MPL-covered source and modifications are supplied under MPL-2.0; nothing here restricts recipients' MPL source rights. The full license is in `notices/eigen/COPYING.MPL2` and each source archive.

## Obtain source, free of charge

Download the following assets from the same [historical-code8 release](https://github.com/serexe/sarah-android/releases/tag/historical-code8) as the APK. Verify against `hashes-manifest.json` and its companion checksum. Asset names are flat even though the staging manifest records `sources/` paths.

- [eigen-5.0.1.tar.gz](https://github.com/serexe/sarah-android/releases/download/historical-code8/eigen-5.0.1.tar.gz): original Eigen 5.0.1 archive, SHA-256 `e9c326dc8c05cd1e044c71f30f1b2e34a6161a3b6ecf445d56b53ff1669e3dec`. The sherpa v2.0.1 root CMake module path supplies its `eigen.cmake` when kaldi-decoder 0.3.0 calls `include(eigen)`; that module hash-pins this archive and declares no Eigen patch.
- [eigen-3.4.0.tar.gz](https://github.com/serexe/sarah-android/releases/download/historical-code8/eigen-3.4.0.tar.gz): original archive, SHA-256 `8586084f71f9bde545ee7fa6d00288b264a2b7ac3607b974e54d13e7162c1c72`. Conservative extra: kaldi-decoder 0.3.0's standalone module pins this version. Its inclusion does not claim the sherpa AAR was compiled twice or establish a second effective Eigen selection.
- [eigen-onnxruntime-1.28.2-covered-source.tar.gz](https://github.com/serexe/sarah-android/releases/download/historical-code8/eigen-onnxruntime-1.28.2-covered-source.tar.gz): full Eigen source tree from commit `1d8b82b0740839c0de7f1242a3585e3390ff5f33`, with both patches from ONNX Runtime v1.28.2 applied in upstream order. Original patch files are also included. Base archive SHA-1 `05b19b49e6fbb91246be711d801160528c135e34` matches ONNX's dependency pin. Patches change ZVector headers **and `Eigen/src/Core/RandomImpl.h`**; the patch set is not described as architecture-only or unmodified Eigen. All patch applications succeeded without rejects.

These archives preserve upstream source notices. Full source archives include ancillary files under their own stated licenses; the owner MIT does not override those terms. No SARAH-side modification to native bytes is introduced here. No claim is made about undisclosed upstream changes, a complete SBOM or bit-identical rebuilding.

## First-party build/source references

- sherpa root module path and dependency inclusion: https://github.com/k2-fsa/sherpa-onnx/blob/v2.0.1/CMakeLists.txt
- sherpa Eigen archive/hash, no patch declaration: https://github.com/k2-fsa/sherpa-onnx/blob/v2.0.1/cmake/eigen.cmake
- kaldi-decoder standalone module: https://github.com/k2-fsa/kaldi-decoder/blob/v0.3.0/cmake/eigen.cmake
- Eigen original archives: https://gitlab.com/libeigen/eigen/-/archive/5.0.1/eigen-5.0.1.tar.gz and https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz
- ONNX dependency commit/hash: https://github.com/microsoft/onnxruntime/blob/v1.28.2/cmake/deps.txt
- ONNX patch declarations: https://github.com/microsoft/onnxruntime/blob/v1.28.2/cmake/external/eigen.cmake
- ONNX patch files: https://github.com/microsoft/onnxruntime/tree/v1.28.2/cmake/patches/eigen
- Android ONNX library packager's tagged workflow: https://github.com/csukuangfj/onnxruntime-libs/blob/v1.28.2/.github/workflows/android-shared.yaml

MPL sections 3.1–3.4 require covered source availability, information for recipients, preserved notices and unrestrained source rights. They do not require unrelated application source, a complete SBOM, a fresh build, or a maintainer-signed no-modification attestation. Larger Work terms remain separate. See https://www.mozilla.org/MPL/2.0/ and Mozilla's FAQ questions 7–11: https://www.mozilla.org/en-US/MPL/2.0/FAQ/ . This is a bounded redistribution assessment, not legal advice or an exhaustive guarantee.

The separately bundled Public Suffix List retains its exact notice in `notices/okhttp3/internal/publicsuffix/NOTICE`; its MPL source is available at https://publicsuffix.org/list/public_suffix_list.dat .
