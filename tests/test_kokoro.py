"""Synthetic warm-synthesis and encoder contracts; no real speech/model assets."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bridge import runtime
from bridge.warm_voice import WarmVoice


class KokoroContract(unittest.IsolatedAsyncioTestCase):
    def test_selected_voice_parameters_are_fixed(self):
        from bridge.kokoro_tts import VOICE, SPEED, LANGUAGE
        self.assertEqual((VOICE, SPEED, LANGUAGE), ('af_heart', 1.05, 'en-us'))

    async def test_warm_helper_only_synthesis_route_and_atomic_publication(self):
        synthesis, encodes = [], []
        async def synth(worker, text, output):
            synthesis.append((worker.python, worker.script, text, output))
            output.write_bytes(b'synthetic wav')
        async def encode(*args, **kwargs):
            encodes.append(args)
            self.assertEqual(args[0], '/usr/bin/ffmpeg')
            Path(args[-1]).write_bytes(b'synthetic encoded audio')
        with tempfile.TemporaryDirectory() as tmp, patch.object(WarmVoice, 'synthesize', synth), \
                patch.object(runtime, '_tts_process', encode):
            target = Path(tmp) / 'out.mp3'
            await runtime.VoiceRuntime().speak('Hello example.', target)
            self.assertEqual(target.read_bytes(), b'synthetic encoded audio')
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(tmp).iterdir()), [target])
        self.assertEqual(len(synthesis), 1)
        self.assertEqual(len(encodes), 1)
        self.assertEqual(Path(synthesis[0][0]), Path(runtime.__file__).resolve().parents[1] / '.build/kokoro-audition/venv/bin/python')
        self.assertEqual(Path(synthesis[0][1]), Path(runtime.__file__).with_name('kokoro_tts.py'))
        self.assertEqual(synthesis[0][2], 'Hello example.')

    async def test_synthesis_failure_has_no_fallback_or_publication(self):
        calls = []
        async def fail(*args):
            calls.append(args)
            raise RuntimeError('local_tts_failed')
        with tempfile.TemporaryDirectory() as tmp, patch.object(WarmVoice, 'synthesize', fail):
            target = Path(tmp) / 'out.mp3'
            with self.assertRaisesRegex(RuntimeError, '^local_tts_failed$'):
                await runtime.VoiceRuntime().speak('Hello.', target)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(len(calls), 1)
