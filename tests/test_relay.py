"""Real HTTP + disposable ACP peer; transcript and MP3 bytes are synthetic."""
import asyncio
import io
import json
from pathlib import Path
import threading
import unittest
import wave

from aiohttp.test_utils import TestClient, TestServer

from acp_fixture import ACPFixture
from bridge.server import make_app
from bridge import runtime
from bridge.warm_voice import WarmVoice
from unittest.mock import patch


def wav_bytes():
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', ''))
        wav.writeframes(b'\0\0'*8000)
    return output.getvalue()


class RelayTests(ACPFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.transcript = 'What time is it?'
        self.runtime.transcribe = lambda path: self.transcript
        async def speak(text, path):
            path.write_bytes(b'synthetic MP3')
        self.runtime.speak = speak
        self.client = TestClient(TestServer(make_app(self.store, self.runtime)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await super().asyncTearDown()

    def headers(self, key='one', device='a', **extra):
        return {'Authorization': 'Bearer '+device*48, 'X-Conversation': self.conversation,
                'Idempotency-Key': key, 'Content-Type': 'audio/wav', **extra}

    async def submit(self, key='one', **extra):
        response = await self.client.post('/v1/turns', data=wav_bytes(), headers=self.headers(key, **extra))
        self.assertEqual(response.status, 202, await response.text())
        return (await response.json())['turn']

    async def finished(self, turn):
        async with asyncio.timeout(2):
            while True:
                response = await self.client.get('/v1/turns/'+turn, headers=self.headers())
                result = await response.json()
                if result['state'] in ('done', 'error', 'uncertain', 'cancelled'):
                    return result
                await asyncio.sleep(.02)

    def prompts(self):
        return [message['params']['prompt'] for message in self.requests if message['method'] == 'session/prompt']

    def assert_wire_fixture(self, row, name):
        fixture = json.loads((Path(__file__).parent/'fixtures/voice-relay.json').read_text())[name]
        actual = {key: row[key] for key in fixture}
        actual.update(id='synthetic-turn', conversation='synthetic-conversation')
        self.assertEqual(actual, fixture)
        for key in ('confirmation', 'phone_action', 'phone_command', 'reply_expected', 'tools'):
            self.assertNotIn(key, row)

    async def wait_for_chunks(self, turn):
        async with asyncio.timeout(2):
            while True:
                response = await self.client.get('/v1/turns/'+turn, headers=self.headers())
                row = await response.json()
                if row.get('audio_chunks', {}).get('count') == 2:
                    return row
                await asyncio.sleep(.01)

    async def test_android_sentence_contract_and_plain_followup_load_same_session(self):
        self.transcript = 'Set a timer for five minutes'
        self.answers = ['First. Second. Third.', 'What duration?']
        turn = await self.submit(**{'X-Audio-Chunks': 'sentence-mp3-v1'})
        self.assert_wire_fixture(await self.wait_for_chunks(turn), 'speaking')
        session = self.binding()['session']
        for seq in range(3):
            async with asyncio.timeout(2):
                while True:
                    response = await self.client.get('/v1/turns/'+turn,
                        headers=self.headers(**{'X-Audio-After': str(seq)}))
                    row = await response.json()
                    if row['audio_chunks']['count'] > seq:
                        break
                    await asyncio.sleep(.01)
            response = await self.client.get(f'/v1/turns/{turn}/audio/{seq}', headers=self.headers())
            self.assertEqual(response.content_type, 'audio/mpeg')
            self.assertEqual(await response.read(), b'synthetic MP3')
        await self.client.get('/v1/turns/'+turn, headers=self.headers(**{'X-Audio-After': '3'}))
        self.assert_wire_fixture(await self.finished(turn), 'done')
        self.assertFalse(list((self.root/'media').glob(turn+'*.mp3')))
        self.transcript = 'Actually ten minutes'
        row = await self.finished(await self.submit('fresh-followup'))
        self.assertEqual(row['detail'], 'What duration?')
        self.assertEqual(self.binding()['session'], session)
        loads = [m['params']['sessionId'] for m in self.requests if m['method'] == 'session/load']
        self.assertEqual(loads, [session])
        self.assertEqual(self.prompts(), [[{'type': 'text', 'text': text}] for text in
            ('Set a timer for five minutes', 'Actually ten minutes')])

    async def test_android_stop_during_agent_is_uncertain_and_never_replaced(self):
        self.transcript = 'Set a timer for five minutes'
        self.mode = 'stall'
        turn = await self.submit(**{'X-Audio-Chunks': 'sentence-mp3-v1'})
        await asyncio.wait_for(self.started.wait(), 1)
        response = await self.client.post(f'/v1/turns/{turn}/cancel', json={}, headers=self.headers())
        # Cancel replies have the store envelope; polling adds audio availability.
        self.assertEqual((await response.json())['state'], 'uncertain')
        await asyncio.wait_for(self.closed.wait(), 1)
        row = await self.finished(turn)
        self.assert_wire_fixture(row, 'uncertain')
        self.assertEqual(self.binding()['state'], 'uncertain')
        self.assertTrue(self.cancelled.is_set())
        self.assertEqual(await self.submit(), turn)
        response = await self.client.post('/v1/turns', data=wav_bytes(), headers=self.headers('next'))
        self.assertEqual(response.status, 409)
        self.assertEqual(len(self.prompts()), 1)

    async def test_android_stop_during_speech_does_not_poison_completed_agent_session(self):
        self.transcript = 'Set a timer for five minutes'
        self.answers = ['First. Second. Third.']
        turn = await self.submit(**{'X-Audio-Chunks': 'sentence-mp3-v1'})
        await self.wait_for_chunks(turn)
        response = await self.client.post(f'/v1/turns/{turn}/cancel', json={}, headers=self.headers())
        self.assertEqual((await response.json())['state'], 'cancelled')
        self.assert_wire_fixture(await self.finished(turn), 'cancelled')
        async with asyncio.timeout(2):
            while list((self.root/'media').glob(turn+'*.mp3')):
                await asyncio.sleep(.01)
        self.assertEqual(self.binding()['state'], 'ready')
        self.assertEqual((await self.finished(await self.submit('next')))['state'], 'done')
        self.assertEqual(len(self.prompts()), 2)

    async def test_agent_client_permissions_and_dispatch_are_denied_over_voice_path(self):
        self.mode = 'permission'
        row = await self.finished(await self.submit())
        self.assertEqual(row['state'], 'done')
        self.assertEqual(row['detail'], 'Reply: What time is it? café')
        permission, *unsupported = self.client_responses
        self.assertEqual(permission['result'], {'outcome': {'outcome': 'cancelled'}})
        self.assertTrue(all(reply['error']['code'] == -32601 for reply in unsupported))
        self.assertEqual(len(unsupported), 3)
        self.assertEqual(len(self.prompts()), 1)

    async def test_agent_deadline_preserves_uncertain_text_only_receipt(self):
        self.mode = 'stall'
        turn = await self.submit()
        row = await self.finished(turn)
        self.assertEqual(row['state'], 'uncertain')
        self.assertIn('(TimeoutError)', row['detail'])
        self.assertFalse(row['audio'])
        self.assertEqual(self.binding()['state'], 'uncertain')
        lookup = await self.client.get('/v1/requests/one', headers=self.headers())
        self.assertEqual((await lookup.json())['id'], turn)
        self.assertEqual(len(self.prompts()), 1)

    async def test_no_semantic_fast_paths_all_transcripts_are_plain_agent_prompts(self):
        for index, text in enumerate(('What time is it?', 'Set a timer for five minutes',
                                      'Play my music', 'Turn on the lights', 'Search my mail',
                                      '/agent-owned-command')):
            self.transcript = text
            result = await self.finished(await self.submit(str(index)))
            self.assertEqual(result['state'], 'done', result)
            self.assertEqual(result['detail'], 'Reply: '+text+' café')
            self.assertEqual(result['timings']['route'], 'acp')
            self.assertGreaterEqual(result['timings']['stt_ms'], 0)
            self.assertTrue(result['audio'])
            self.assertNotIn('confirmation', result)
        self.assertEqual(self.prompts(), [[{'type': 'text', 'text': text}] for text in
            ('What time is it?', 'Set a timer for five minutes', 'Play my music',
             'Turn on the lights', 'Search my mail', '/agent-owned-command')])

    async def test_transport_failure_is_uncertain_lookup_and_reupload_never_replay(self):
        self.mode = 'drop'
        turn = await self.submit()
        result = await self.finished(turn)
        self.assertEqual(result['state'], 'uncertain', result)
        self.assertNotIn('synthetic-private', result['detail'])
        self.assertEqual(await self.submit(), turn)
        lookup = await self.client.get('/v1/requests/one', headers=self.headers())
        self.assertEqual((await lookup.json())['id'], turn)
        self.mode = 'normal'
        response = await self.client.post('/v1/turns', data=wav_bytes(), headers=self.headers('no-replay'))
        self.assertEqual(response.status, 409)
        self.assertEqual(len(self.prompts()), 1)
        self.conversation = self.store.conversation('one')
        result = await self.finished(await self.submit('explicit-new-conversation'))
        self.assertEqual(result['state'], 'done')
        self.assertEqual(len(self.prompts()), 2)

    async def test_owner_protection_extends_to_audio_chunks_lookup_and_cancel(self):
        turn = await self.submit(**{'X-Audio-Chunks': 'sentence-mp3-v1'})
        async with asyncio.timeout(2):
            while not (self.root/'media'/f'{turn}.0.mp3').exists():
                await asyncio.sleep(.005)
        for path in (f'/v1/turns/{turn}', f'/v1/turns/{turn}/audio', f'/v1/turns/{turn}/audio/0', '/v1/requests/one'):
            response = await self.client.get(path, headers=self.headers(device='b'))
            self.assertEqual(response.status, 403)
        response = await self.client.post(f'/v1/turns/{turn}/cancel', json={}, headers=self.headers(device='b'))
        self.assertEqual(response.status, 403)
        response = await self.client.get(f'/v1/turns/{turn}', headers=self.headers(**{'X-Audio-After': '99'}))
        self.assertEqual(response.status, 403)
        self.assertEqual(len(self.prompts()), 1)

    async def test_no_tools_confirmation_or_clarification_execution_endpoints(self):
        for endpoint in ('/v1/tools', '/v1/dispatch', '/v1/turns/missing/confirmation'):
            response = await self.client.post(endpoint, headers=self.headers(), json={})
            self.assertEqual(response.status, 404)
        response = await self.client.post('/v1/turns', data=wav_bytes(),
            headers=self.headers(**{'X-Clarification-Parent': 'synthetic'}))
        self.assertEqual(response.status, 403)
        self.assertEqual(self.requests, [])
        health = await (await self.client.get('/v1/health', headers=self.headers())).json()
        self.assertEqual(health['protocol'], 1)
        self.assertNotIn('tools', health)
        self.assertNotIn('home_assistant', health)

    async def test_tts_failure_keeps_text_and_never_retries_agent(self):
        async def fail(text, path):
            path.write_bytes(b'partial')
            raise RuntimeError('synthetic private TTS details')
        self.runtime.speak = fail
        for index, extra in enumerate(({}, {'X-Audio-Chunks': 'sentence-mp3-v1'})):
            row = await self.finished(await self.submit(str(index), **extra))
            self.assertEqual(row['state'], 'done')
            self.assertEqual(row['detail'], 'Reply: What time is it? café')
            self.assertFalse(row['audio'])
            self.assertNotIn('audio_chunks', row)
            self.assertEqual(row['timings']['tts_failed'], 1)
            self.assertFalse(list((self.root/'media').glob(row['id']+'*.mp3')))
        self.assertEqual(len(self.prompts()), 2)

    async def test_empty_and_oversize_audio_preserves_text_only(self):
        for size in (0, 4*1024*1024+1):
            async def invalid_audio(text, path):
                path.write_bytes(b'x'*size)
            self.runtime.speak = invalid_audio
            for chunked in (False, True):
                extra = {'X-Audio-Chunks': 'sentence-mp3-v1'} if chunked else {}
                row = await self.finished(await self.submit(f'limit-{size}-{chunked}', **extra))
                self.assertEqual(row['state'], 'done')
                self.assertFalse(row['audio'])
                self.assertEqual(row['timings']['tts_failed'], 1)
                self.assertFalse(list((self.root/'media').glob(row['id']+'*.mp3')))
        self.assertEqual(len(self.prompts()), 4)

    async def test_markdown_only_changes_at_speech_boundary(self):
        prose = '## Choice\n- **Total:** `$100` and **$1.50**.'
        self.answers = [prose, 'Followup']
        seen = []
        async def synth(worker, text, output):
            seen.append(text)
            output.write_bytes(b'synthetic wav')
        async def encode(*args, **kwargs):
            from pathlib import Path
            Path(args[-1]).write_bytes(b'synthetic MP3')
        async def speak(text, path):
            await runtime.VoiceRuntime.speak(self.runtime, text, path)
        self.runtime.speak = speak
        with patch.object(WarmVoice, 'synthesize', synth), patch.object(runtime, '_tts_process', encode):
            row = await self.finished(await self.submit())
            self.assertEqual(row['detail'], prose)
            self.assertEqual(seen, ['Choice\nTotal: $100 and one dollar and fifty cents.'])
            await self.finished(await self.submit('followup'))
        self.assertEqual(self.store.get('one', row['id'])['detail'], prose)
        self.assertEqual(self.prompts()[-1], [{'type': 'text', 'text': self.transcript}])

    async def test_stop_native_stt_retains_clip_and_admission_until_thread_finishes(self):
        started, done, release = asyncio.Event(), threading.Event(), threading.Event()
        loop, clips = asyncio.get_running_loop(), []
        def native(path):
            clips.append(path)
            loop.call_soon_threadsafe(started.set)
            try:
                if not release.wait(3):
                    raise RuntimeError('synthetic release timeout')
                self.assertTrue(path.exists())
                return 'native transcript'
            finally:
                done.set()
        self.runtime.transcribe = native
        closing = None
        try:
            turn = await self.submit()
            await asyncio.wait_for(started.wait(), 1)
            for _ in range(2):
                response = await self.client.post(f'/v1/turns/{turn}/cancel', json={}, headers=self.headers())
                self.assertEqual((await response.json())['state'], 'cancelled')
            self.assertEqual(await self.submit(), turn)
            response = await self.client.post('/v1/turns', data=wav_bytes(), headers=self.headers('busy'))
            self.assertEqual(response.status, 409)
            self.assertFalse(done.is_set())
            closing = asyncio.create_task(self.client.close())
            await asyncio.sleep(.02)
            self.assertFalse(closing.done())
            release.set()
            await asyncio.wait_for(closing, 1)
            self.assertTrue(done.is_set())
            self.assertFalse(clips[0].exists())
            self.assertEqual(self.requests, [])
        finally:
            release.set()
            if closing is not None:
                await closing
