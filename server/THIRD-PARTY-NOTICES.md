# Third-party dependencies and notices

The MIT License in LICENSE covers the original project code and associated documentation; it does not relicense dependencies, models, voice assets or other third-party materials. Their obligations remain separate and have not been audited by this license application.

This server depends on Python, aiohttp, faster-whisper/PyAV, and optionally Kokoro ONNX, ONNX Runtime, NumPy, SoundFile and FFmpeg/libmp3lame. An externally configured ACP agent and its dependencies retain their own licenses. Speech models and voice assets have separate terms. No compiled dependencies or speech models are bundled in the server source.

The bridge derives from `serexe/sarah-r1`; its MIT copyright/license remains intact. This fork removed the Qt/Lomiri/Ubuntu Touch client, SVG assets, power helper and direct-model runtime. Their removal does not alter upstream attribution or license rights. Android retains its own third-party notices and model provenance in its subtree.

No explicit third-party attribution/copyright notice was found in the allowlisted original source files. No such notice has been removed. Dependency distributions and their license files are intentionally not copied; obtain them from their publishers and retain all applicable notices when distributing a binary or dependency bundle. Dependency licensing, dynamic/static linking obligations, codecs and separate speech-model/voice asset rights must be reviewed against the exact versions and artifacts actually shipped. This list is not a complete license bill of materials and grants no rights.
