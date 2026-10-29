# Verification and publication

Chad's Agent — current server scope: local speech + ACP relay. Offline checks do not establish physical-device, live speech/agent or deployment behavior. Upstream attribution and license notices remain.

Run Python tests with `PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Tests isolate configuration and reject non-loopback TCP connections, use temporary Unix ACP peers and disposable stdio/TTS children, and never need live model/tool calls. These controls are not a general sandbox for arbitrary future subprocesses.

`PUBLICATION-MANIFEST.txt` explicitly inventories server source. The automated hygiene test copies Git-tracked files into a clean temporary directory and scans every file; stage additions/deletions first. It rejects missing/unlisted input, private/generated files, unknown binaries, symlinks, unreadable entries and forbidden directories, including ignored/hidden files. No screenshot or binary exception remains. Synthetic negative controls keep these gates active.

For manual review, export only the tracked server tree into a clean temporary directory and run `python tools/privacy_scan.py <export>`. Do not scan/package private runtime state or build caches. A zero-finding heuristic scan does not prove absence of all private data. Independent literal review can use `--literal-file` outside the source tree, without committing values.

Original MIT license text and third-party notices are preserved. This cleanup is source review, not device, live speech/agent, binary distribution or deployment proof.
