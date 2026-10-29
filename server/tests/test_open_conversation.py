"""Authenticated HTTP voice flow through production ACP over a loopback Unix peer."""
import asyncio
import io
import unittest
import wave

from aiohttp.test_utils import TestClient, TestServer
from bridge.core import Store
from bridge.server import make_app
from acp_fixture import ACPFixture


class Conversation(ACPFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.adapter = self.runtime
        self.transcript = 'Hello Sarah'
        self.adapter.transcribe = lambda path: self.transcript
        self.spoken = []
        async def speak(text, path):
            self.spoken.append(text)
            path.write_bytes(b'synthetic MP3')
        self.adapter.speak = speak
        self.client = TestClient(TestServer(make_app(self.store, self.adapter)))
        await self.client.start_server()
        response = await self.client.post('/v1/conversations', headers=self.auth(), json={})
        self.assertEqual(response.status, 201)
        self.conversation = (await response.json())['conversation']
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0'*8000)
        self.wav = buf.getvalue()

    async def asyncTearDown(self):
        await self.client.close()
        await super().asyncTearDown()

    def auth(self, other=False):
        return {'Authorization':'Bearer '+('b' if other else 'a')*48}

    def prompts(self):
        return [m['params'] for m in self.requests if m['method']=='session/prompt']

    async def submit(self, key='one', conversation=None, data=None):
        return await self.client.post('/v1/turns', data=self.wav if data is None else data,
            headers={**self.auth(), 'Content-Type':'audio/wav', 'Idempotency-Key':key,
                     'X-Conversation':conversation or self.conversation})

    async def finished(self, response):
        self.assertEqual(response.status, 202)
        turn = (await response.json())['turn']
        async with asyncio.timeout(2):
            while True:
                result = await (await self.client.get('/v1/turns/'+turn, headers=self.auth())).json()
                if result['state'] in ('done','error','cancelled','uncertain'):
                    return result
                await asyncio.sleep(.01)

    async def test_voice_history_audio_and_conversation_isolation(self):
        self.answers = ['Hello', 'A followup', 'Fresh reply']
        first = await self.finished(await self.submit())
        self.assertEqual(first['state'], 'done')
        self.assertEqual(first['detail'], 'Hello')
        self.assertTrue(first['audio'])
        audio = await self.client.get('/v1/turns/'+first['id']+'/audio', headers=self.auth())
        self.assertEqual(await audio.read(), b'synthetic MP3')
        self.assertEqual(audio.content_type, 'audio/mpeg')
        self.assertEqual(audio.headers['Cache-Control'], 'no-store')
        self.assertEqual((await self.client.get('/v1/turns/'+first['id']+'/audio', headers=self.auth(True))).status, 403)
        self.transcript = 'And then?'
        second = await self.finished(await self.submit('two'))
        self.assertEqual(second['detail'], 'A followup')
        fresh = self.store.conversation('one')
        foreign = self.store.conversation('two')
        self.store.finish('two', self.store.admit('two',foreign,'private','hash'), 'done','private answer','private prompt')
        third = await self.finished(await self.submit('three', conversation=fresh))
        self.assertEqual(third['detail'], 'Fresh reply')
        prompts = self.prompts()
        self.assertEqual(prompts[0]['sessionId'], prompts[1]['sessionId'])
        self.assertNotEqual(prompts[1]['sessionId'], prompts[2]['sessionId'])
        self.assertEqual(prompts[1]['prompt'], [{'type':'text','text':'And then?'}])
        self.assertEqual(prompts[2]['prompt'], [{'type':'text','text':'And then?'}])
        self.assertEqual(self.spoken, ['Hello', 'A followup', 'Fresh reply'])
        self.assertEqual(len([m for m in self.requests if m['method']=='session/load']), 1)

    async def test_duplicate_and_conflicting_upload_never_replay(self):
        self.answers = ['Only once']
        first = await self.finished(await self.submit())
        again = await self.finished(await self.submit())
        self.assertEqual(again['id'], first['id'])
        changed = bytearray(self.wav); changed[-1] = 1
        self.assertEqual((await self.submit(data=bytes(changed))).status, 409)
        self.assertEqual((await self.submit(conversation=self.store.conversation('one'))).status, 409)
        self.assertEqual(len(self.prompts()), 1)
        self.assertEqual(self.spoken, ['Only once'])
        reopened = Store(self.store.path)
        try:
            reopened.recover()
            self.assertEqual(reopened.by_request('one','one')['id'], first['id'])
            self.assertEqual(reopened.get('one',first['id'])['state'], 'done')
        finally:
            reopened.close()

    async def test_transport_failure_no_speech_or_replay(self):
        self.mode = 'drop'
        first = await self.finished(await self.submit())
        self.assertEqual(first['state'], 'error')
        self.assertFalse(first['audio'])
        self.assertEqual(self.binding()['state'], 'uncertain')
        self.mode = 'normal'
        second = await self.finished(await self.submit('two'))
        self.assertEqual(second['state'], 'error')
        self.assertEqual(len(self.prompts()), 1)
        self.assertEqual(self.spoken, [])
        self.assertEqual(list((self.store.path.parent/'media').iterdir()), [])

    async def test_invalid_wav_and_foreign_conversation_refused_before_acp(self):
        self.assertEqual((await self.submit(data=b'invalid')).status, 403)
        self.assertEqual((await self.submit(conversation=self.store.conversation('two'))).status, 403)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM turns').fetchone()[0], 0)

    async def test_health_and_removed_confirmation_contract(self):
        health = await (await self.client.get('/v1/health', headers=self.auth())).json()
        self.assertEqual(health['protocol'], 1)
        self.assertTrue(health['ready'])
        self.assertEqual(health['backend'], 'acp')
        for key in ('tools','home_assistant','siyuan','calendar','tvtime'):
            self.assertNotIn(key, health)
        turn = self.store.admit('one',self.conversation,'legacy','hash')
        route = '/v1/turns/'+turn+'/confirmation'
        value = {'conversation':self.conversation,'nonce':'legacy','action_hash':'legacy','accept':True}
        self.assertEqual((await self.client.post(route,json=value)).status, 403)
        for auth in (self.auth(), self.auth(True)):
            self.assertEqual((await self.client.post(route,headers=auth,json=value)).status, 404)
        self.assertEqual(self.store.get('one',turn)['state'], 'transcribing')
        result = await (await self.client.get('/v1/turns/'+turn,headers=self.auth())).json()
        self.assertNotIn('confirmation', result)
        self.assertEqual(self.requests, [])

    async def test_text_preserved_when_tts_fails(self):
        async def fail(text, path):
            path.write_bytes(b'partial')
            raise RuntimeError('synthetic TTS failure')
        self.adapter.speak = fail
        self.answers = ['Answer preserved']
        result = await self.finished(await self.submit())
        self.assertEqual(result['state'], 'done')
        self.assertEqual(result['detail'], 'Answer preserved')
        self.assertFalse(result['audio'])
        self.assertEqual((await self.client.get('/v1/turns/'+result['id']+'/audio',headers=self.auth())).status, 403)
        self.assertEqual(list((self.store.path.parent/'media').iterdir()), [])

    async def test_lost_202_lookup_is_read_only(self):
        response = await self.submit('lost-response')
        self.assertEqual(response.status, 202)
        response.release()
        async with asyncio.timeout(2):
            while self.store.by_request('one','lost-response')['state'] != 'done':
                await asyncio.sleep(.01)
        row = await (await self.client.get('/v1/requests/lost-response',headers=self.auth())).json()
        for _ in range(3):
            lookup = await self.client.get('/v1/requests/lost-response',headers=self.auth())
            self.assertEqual((await lookup.json())['id'], row['id'])
        self.assertEqual((await self.client.get('/v1/requests/lost-response',headers=self.auth(True))).status, 403)
        self.assertEqual(len(self.prompts()), 1)

    async def test_rate_and_body_bounds_before_dispatch(self):
        response = await self.client.post('/v1/turns',data=b'x'*(4*1024*1024+1),
            headers={**self.auth(),'Content-Type':'audio/wav','X-Conversation':self.conversation,'Idempotency-Key':'large'})
        self.assertEqual(response.status, 413)
        # Per-device rate limit covers every authenticated route, including health.
        response = None
        for _ in range(90):
            response = await self.client.get('/v1/health',headers=self.auth())
        self.assertEqual(response.status, 429)
        self.assertEqual((await self.client.get('/v1/health',headers=self.auth(True))).status, 200)
        self.assertEqual(self.requests, [])
