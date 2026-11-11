# Third-party dependencies and notices

The MIT License in `LICENSE` covers the upstream original project code and associated documentation, copyright (c) 2026 serexe. It does not relicense dependencies, models, voice assets, artwork or other third-party materials. Preserve the upstream copyright and permission notice when distributing copies or substantial portions of the software.

The bridge depends on externally installed Python, aiohttp, faster-whisper/CTranslate2, Whisper model assets and, for local synthesis, Kokoro ONNX, ONNX Runtime, NumPy, SoundFile and FFmpeg/libmp3lame with their transitive/native dependencies. Their licenses and the exact model/voice/codec artifacts require separate review. Docker packaging downloads speech assets explicitly at build time; it does not grant rights to redistribute them. The bridge neither vendors nor requires Hermes, provider SDKs, Qt/Lomiri or bridge-owned external integration services.

The separate `android/` subtree retains upstream Android libraries, bundled wake-word model/runtime assets, artwork and their notices. See `android/DEPENDENCIES.md`, `android/KWS-DEPENDENCIES.md`, source-snapshot documents and `android/app/src/main/assets/licenses/`. The bridge-only publication manifest does not include those assets. They have not been independently audited by this re-fork. Do not remove their notices or apply the root MIT license to them by implication.

No upstream attribution/copyright notice has intentionally been removed. Dependency distributions and their license files must accompany any bundle as required by their own terms. Review exact versions, static/dynamic linking, codec, model, voice and artwork rights before distribution. This is not a complete license bill of materials or a legal opinion.
