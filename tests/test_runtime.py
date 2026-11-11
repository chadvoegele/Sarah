"""Offline production speech regressions with disposable synthetic children."""
import asyncio
import signal
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge import runtime as module
from bridge.runtime import VoiceRuntime
from bridge.warm_voice import WarmVoice


class TranscriptionTests(unittest.TestCase):
    def test_real_audio_decoder_accepts_wav(self):
        import wave
        from faster_whisper.audio import decode_audio
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic.wav'
            with wave.open(str(path), 'wb') as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b'\0\0' * 1600)
            decoded = decode_audio(str(path))
            self.assertEqual(len(decoded), 1600)
            self.assertTrue((decoded == 0).all())

    def test_local_model_path_no_download_and_bounded_transcript(self):
        from types import SimpleNamespace
        adapter = VoiceRuntime()
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
            with self.assertRaises(RuntimeError): VoiceRuntime().transcribe(Path('synthetic.wav'))
            factory.assert_called_once()


class EncoderOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def probe(self, mode):
        children = []
        real_spawn = asyncio.create_subprocess_exec
        started = asyncio.Event()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'out.mp3'
            async def synth(worker, text, output):
                output.write_bytes(b'synthetic wav')
            async def factory(*args, **kwargs):
                self.assertEqual(args[0], '/usr/bin/ffmpeg')
                output = Path(args[-1])
                handler = 'SIG_DFL' if mode == 'graceful' else 'SIG_IGN'
                ending = ('raise SystemExit(7)' if mode == 'failure' else
                          '' if mode == 'success' else 'time.sleep(30)')
                code = ('import pathlib,signal,time; '
                        f'signal.signal(signal.SIGTERM,signal.{handler}); '
                        f'pathlib.Path({str(output)!r}).write_bytes(b"partial"); {ending}')
                child = await real_spawn(sys.executable, '-c', code,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
                children.append(child)
                while not output.exists():
                    await asyncio.sleep(.002)
                started.set()
                if mode == 'spawn_cancel':
                    await asyncio.sleep(.05)
                return child
            task = None
            try:
                with patch.object(WarmVoice, 'synthesize', synth), \
                        patch.object(module.asyncio, 'create_subprocess_exec', factory), \
                        patch.object(module, 'TTS_STAGE_SECONDS', .2), \
                        patch.object(module, 'TTS_TERMINATE_GRACE', .04):
                    task = asyncio.create_task(VoiceRuntime().speak('synthetic', target))
                    if mode in ('cancel', 'spawn_cancel', 'repeat_cancel', 'graceful'):
                        await asyncio.wait_for(started.wait(), 1)
                        self.assertFalse(target.exists())
                        task.cancel()
                        if mode == 'repeat_cancel':
                            await asyncio.sleep(.005)
                            task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    elif mode == 'timeout':
                        with self.assertRaises(TimeoutError):
                            await asyncio.wait_for(task, 2)
                    elif mode == 'failure':
                        with self.assertRaisesRegex(RuntimeError, '^tts_encoding_failed$'):
                            await task
                    else:
                        await task
                self.assertTrue(children)
                self.assertTrue(all(child.returncode is not None for child in children))
                if mode == 'success':
                    self.assertEqual(target.read_bytes(), b'partial')
                    self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                    self.assertEqual(list(Path(tmp).iterdir()), [target])
                else:
                    self.assertFalse(target.exists())
                    self.assertEqual(list(Path(tmp).iterdir()), [])
                    expected = 7 if mode == 'failure' else -(signal.SIGTERM if mode == 'graceful' else signal.SIGKILL)
                    self.assertEqual(children[-1].returncode, expected)
            finally:
                if task is not None and not task.done():
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
                for child in children:
                    if child.returncode is None:
                        child.kill()
                    await child.wait()

    async def test_encoder_ownership_at_all_boundaries(self):
        for mode in ('success', 'failure', 'timeout', 'cancel', 'spawn_cancel', 'repeat_cancel', 'graceful'):
            with self.subTest(mode=mode):
                await self.probe(mode)
