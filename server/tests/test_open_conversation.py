"""Real direct-model HTTP voice flow with synthetic SSE and local speech fixtures."""
import asyncio
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer
from bridge.core import Store
from bridge.runtime import VoiceRuntime
from bridge.server import make_app
import test_runtime as fixtures


class Conversation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name)/'state.db')
        self.store.provision('one', 'a'*48)
        self.store.provision('two', 'b'*48)
        self.adapter = VoiceRuntime(fixtures.module.LLMConfig(fixtures.BASE, 'synthetic-qwen', 'synthetic'))
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
        self.store.close()
        self.tmp.cleanup()

    def auth(self, other=False):
        return {'Authorization':'Bearer '+('b' if other else 'a')*48}

    def model(self, *answers):
        return fixtures.Transport([(200, fixtures.Stream([
            ('data: '+json.dumps(event)+'\n\n').encode() for event in
            (fixtures.text_events(answer) if isinstance(answer, str) else answer)]))
            for answer in answers])

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
        with self.model('Hello', 'A followup', 'Fresh reply') as transport:
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
        payloads = [json.loads(request.content) for request in transport.requests]
        self.assertEqual(payloads[1]['messages'][1:], [
            {'role':'user','content':'Hello Sarah'}, {'role':'assistant','content':'Hello'},
            {'role':'user','content':'And then?'}])
        self.assertEqual(payloads[2]['messages'][1:], [{'role':'user','content':'And then?'}])
        self.assertEqual(self.spoken, ['Hello', 'A followup', 'Fresh reply'])
        for payload in payloads:
            for key in ('tools', 'tool_choice', 'parallel_tool_calls'):
                self.assertNotIn(key, payload)

    async def test_duplicate_and_conflicting_upload_never_replay(self):
        with self.model('Only once') as transport:
            first = await self.finished(await self.submit())
            again = await self.finished(await self.submit())
            self.assertEqual(again['id'], first['id'])
            changed = bytearray(self.wav); changed[-1] = 1
            self.assertEqual((await self.submit(data=bytes(changed))).status, 409)
            self.assertEqual((await self.submit(conversation=self.store.conversation('one'))).status, 409)
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(self.spoken, ['Only once'])
        reopened = Store(self.store.path)
        try:
            reopened.recover()
            self.assertEqual(reopened.by_request('one','one')['id'], first['id'])
            self.assertEqual(reopened.get('one',first['id'])['state'], 'done')
        finally:
            reopened.close()

    async def test_model_tool_request_fails_without_speech_or_retry(self):
        events = fixtures.tool_events({'call_id':'unsupported', 'name':'ha_call_service', 'arguments':'{}'})
        with self.model(events) as transport:
            result = await self.finished(await self.submit())
        self.assertEqual(result['state'], 'error')
        self.assertFalse(result['audio'])
        self.assertEqual(self.spoken, [])
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(list((self.store.path.parent/'media').iterdir()), [])

    async def test_recent_history_is_bounded(self):
        for index in range(6):
            turn = self.store.admit('one',self.conversation,'prior'+str(index),'hash')
            self.store.finish('one',turn,'done','answer'+str(index),'prompt'+str(index))
        with self.model('Bounded') as transport:
            await self.finished(await self.submit())
        messages = json.loads(transport.requests[0].content)['messages']
        self.assertEqual(len(messages), 10)  # System, four pairs, current user.
        self.assertEqual(messages[1], {'role':'user','content':'prompt2'})

    async def test_invalid_wav_and_foreign_conversation_refused_before_model(self):
        with self.model() as transport:
            self.assertEqual((await self.submit(data=b'invalid')).status, 403)
            self.assertEqual((await self.submit(conversation=self.store.conversation('two'))).status, 403)
        self.assertEqual(transport.requests, [])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM turns').fetchone()[0], 0)

    async def test_health_and_legacy_confirmation_fail_closed(self):
        health = await (await self.client.get('/v1/health', headers=self.auth())).json()
        self.assertEqual(health['protocol'], 1)
        self.assertTrue(health['ready'])
        for key in ('tools','home_assistant','siyuan','calendar','tvtime'):
            self.assertIs(health[key], False)
        turn = self.store.admit('one',self.conversation,'legacy','hash')
        route = '/v1/turns/'+turn+'/confirmation'
        value = {'conversation':self.conversation,'nonce':'legacy','action_hash':'legacy','accept':True}
        self.assertEqual((await self.client.post(route,json=value)).status, 403)
        self.assertEqual((await self.client.post(route,headers=self.auth(True),json=value)).status, 403)
        for accept in (True,False,'true',None):
            response = await self.client.post(route,headers=self.auth(),json={**value,'accept':accept})
            self.assertEqual(response.status, 403)
            self.assertEqual(await response.json(), {'error':'confirmation_unavailable'})
        self.assertEqual(self.store.get('one',turn)['state'], 'transcribing')
        result = await (await self.client.get('/v1/turns/'+turn,headers=self.auth())).json()
        self.assertNotIn('confirmation', result)
