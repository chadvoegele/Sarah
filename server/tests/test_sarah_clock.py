"""Offline clock presentation and speech-boundary regressions."""
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from bridge import runtime
from bridge.runtime import speech_text

class ClockSpeech(unittest.IsolatedAsyncioTestCase):
    def test_clock_formats(self):
        cases={
            'At 3:30 PM.':'At three thirty P M.',
            'At 12:00 p.m.':'At noon',
            'At 12:00 AM.':'At midnight.',
            'At 3:05 pm.':'At three oh five P M.',
            'At 15:30.':'At three thirty P M.',
            'At 00:05.':'At twelve oh five A M.',
            'At 2026-10-24T20:30:00Z.':'At 2026-10-24 at eight thirty P M.',
            'At 2026-12-24T21:30:00+00:00.':'At 2026-12-24 at nine thirty P M.',
            'At 2026-10-24T15:30:00-04:00.':'At 2026-10-24 at seven thirty P M.',
            'At 2026-03-08T08:05:00Z.':'At 2026-03-08 at eight oh five A M.',
            'At 2026-11-01T07:05:00Z.':'At 2026-11-01 at seven oh five A M.',
            '**8:30–10:00 a.m.**':'eight thirty A M to ten A M',
            '**10:00–11:30 a.m.**':'ten A M to eleven thirty A M',
            'I am S.A.R.A.H.':'I am Sarah.',
        }
        for source,expected in cases.items():
            with self.subTest(source=source): self.assertEqual(speech_text(source),expected)
    def test_nonclock_preserved(self):
        text='2026-10-24; 30 minutes; duration 01:30; ratio 3:05; VI230620; gpt-6.1-sol; 1.05; 80%; `15:30`.'
        self.assertEqual(speech_text(text),text.replace('`',''))
        self.assertEqual(speech_text('$100.50 at 3:30 PM.'),'one hundred dollars and fifty cents at three thirty P M.')
    async def test_production_tts_stdin_clock_and_original_display(self):
        original='Test event on 2026-10-24 at 2026-10-24T22:00:00Z.'
        seen=[]
        async def process(*args,input=None,**kwargs):
            if input is not None: seen.append(input.decode())
            Path(args[-1]).write_bytes(b'offline audio fixture')
        with tempfile.TemporaryDirectory() as tmp, patch.object(runtime,'_tts_process',process):
            await runtime.SpeechRuntime().speak(original,Path(tmp)/'out.mp3')
        self.assertEqual(seen,['Test event on 2026-10-24 at 2026-10-24 at ten P M.'])
        self.assertEqual(original,'Test event on 2026-10-24 at 2026-10-24T22:00:00Z.')
