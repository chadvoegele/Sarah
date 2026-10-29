"""Offline production speech regressions with disposable synthetic children."""
import asyncio
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge import runtime as module
from bridge.runtime import SpeechRuntime


class TranscriptionTests(unittest.TestCase):
    def test_local_model_path_no_download_and_bounded_transcript(self):
        from types import SimpleNamespace
        adapter = SpeechRuntime()
        segments = [SimpleNamespace(text=' hello '), SimpleNamespace(text='Sarah')]
        with patch.object(module, 'WhisperModel') as factory:
            factory.return_value.transcribe.return_value = (segments, None)
            self.assertEqual(adapter.transcribe(Path('synthetic.wav')), 'hello Sarah')
            self.assertEqual(adapter.transcribe(Path('synthetic.wav')), 'hello Sarah')
            factory.assert_called_once()
            self.assertTrue(factory.call_args.kwargs['local_files_only'])
            self.assertEqual(factory.call_args.kwargs['compute_type'], 'int8')
            self.assertEqual(factory.return_value.transcribe.call_args.kwargs,
                             {'beam_size':3, 'language':'en', 'vad_filter':True})
            for text in ('', 'x'*8001):
                factory.return_value.transcribe.return_value = ([SimpleNamespace(text=text)], None)
                with self.assertRaisesRegex(ValueError, 'empty_or_oversize_transcript'):
                    adapter.transcribe(Path('synthetic.wav'))

    def test_missing_local_assets_fail_without_retry(self):
        with patch.object(module, 'WhisperModel', side_effect=RuntimeError('synthetic missing assets')) as factory:
            with self.assertRaises(RuntimeError): SpeechRuntime().transcribe(Path('synthetic.wav'))
            factory.assert_called_once()


class TTSTests(unittest.IsolatedAsyncioTestCase):
    async def probe(self, stage, mode, *, fail=False, ignores_term=True):
        adapter = SpeechRuntime()
        children = []
        real_spawn = asyncio.create_subprocess_exec
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'reply.mp3'
            ready = asyncio.Event()

            async def factory(*args, **kwargs):
                current = 'encode' if args[0] == '/usr/bin/ffmpeg' else 'speech'
                output = Path(args[-1]) if current == 'encode' else Path(args[args.index('--output') + 1])
                hangs = current == stage
                code = ('import pathlib,signal,time; '
                        f'signal.signal(signal.SIGTERM,signal.{"SIG_IGN" if ignores_term else "SIG_DFL"}); '
                        f'pathlib.Path({str(output)!r}).write_bytes(b"partial"); '
                        + ('time.sleep(30)' if hangs else ''))
                if fail and hangs:
                    code = code.replace('time.sleep(30)', 'raise SystemExit(7)')
                proc = await real_spawn(sys.executable, '-c', code,
                                        stdin=asyncio.subprocess.PIPE,
                                        stdout=asyncio.subprocess.DEVNULL,
                                        stderr=asyncio.subprocess.DEVNULL)
                children.append(proc)
                if hangs:
                    # Child has installed SIGTERM handler and written partial output.
                    while not output.exists():
                        await asyncio.sleep(0.002)
                    ready.set()
                    if mode == 'spawn_cancel':
                        # Cancellation between process creation and handle return.
                        await asyncio.sleep(0.03)
                return proc

            task = None
            try:
                with patch.object(module.asyncio, 'create_subprocess_exec', factory), \
                     patch.object(module, 'TTS_STAGE_SECONDS', 0.08, create=True), \
                     patch.object(module, 'TTS_TERMINATE_GRACE', 0.02, create=True):
                    task = asyncio.create_task(adapter.speak('synthetic text', target))
                    if mode in ('cancel', 'spawn_cancel', 'repeat_cancel'):
                        await asyncio.wait_for(ready.wait(), 1)
                        self.assertFalse(target.exists(), 'in-progress audio published')
                        task.cancel()
                        if mode == 'repeat_cancel':
                            await asyncio.sleep(0.005)
                            task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    elif mode == 'success':
                        await task
                    elif fail:
                        with self.assertRaisesRegex(RuntimeError, '^tts_encoding_failed$'):
                            await task
                    else:
                        # Pre-fix outer timeout returns with child still alive.
                        with self.assertRaises(TimeoutError):
                            await asyncio.wait_for(task, 0.3)
                self.assertTrue(children)
                self.assertTrue(all(child.returncode is not None for child in children),
                                'TTS returned while subprocess remains alive')
                if mode == 'success':
                    self.assertEqual(target.read_bytes(), b'partial')  # Synthetic child output, not real MP3.
                    self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(list(Path(tmp).iterdir()), [target])
                else:
                    if not fail:
                        expected = signal.SIGKILL if ignores_term else signal.SIGTERM
                        self.assertEqual(children[-1].returncode, -expected)
                    self.assertFalse(target.exists(), 'partial audio published')
                    self.assertEqual(list(Path(tmp).iterdir()), [], 'temporary audio leaked')
            finally:
                if task and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                # Keep intentionally failing pre-fix probes harmless.
                for child in children:
                    if child.returncode is None:
                        child.kill()
                    await child.wait()

    async def test_speech_deadline_kills_reaps(self):
        await self.probe('speech', 'timeout')

    async def test_encoder_deadline_kills_reaps_no_partial(self):
        await self.probe('encode', 'timeout')

    async def test_speech_cancellation_kills_reaps(self):
        await self.probe('speech', 'cancel')

    async def test_encoder_cancellation_kills_reaps_no_partial(self):
        await self.probe('encode', 'cancel')

    async def test_encoder_failure_does_not_publish_partial(self):
        await self.probe('encode', 'failure', fail=True)

    async def test_spawn_cancellation_retains_handle_and_reaps(self):
        await self.probe('speech', 'spawn_cancel')

    async def test_repeated_cancellation_does_not_interrupt_reap(self):
        await self.probe('encode', 'repeat_cancel')

    async def test_graceful_termination_reaps(self):
        await self.probe('speech', 'cancel', ignores_term=False)

    async def test_success_publishes_only_final_private_audio(self):
        await self.probe(None, 'success')


if __name__ == '__main__':
    unittest.main()
