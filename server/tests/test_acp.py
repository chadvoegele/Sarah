"""Real loopback Unix ACP peer; no Dex, accounts, provider calls or real tools."""
import asyncio
import io
import json
import os
import sys
import unittest
import wave
from unittest.mock import patch

from aiohttp.test_utils import TestClient, TestServer

from bridge.acp_client import ACPClient, ACPConfig, ACPError
from bridge.acp_runtime import ACPRuntime, create_runtime
from bridge.core import Denied, Store
from bridge.server import make_app


from acp_fixture import ACPFixture


class ACPTests(ACPFixture, unittest.IsolatedAsyncioTestCase):
    async def test_initialize_stream_and_only_assistant_text(self):
        self.assertEqual(await self.reply(), 'Reply: hello café')
        self.assertEqual(self.requests[0]['params']['clientCapabilities'], {})
        self.assertEqual(self.requests[1]['params'], {'cwd':str(self.root), 'mcpServers':[]})
        self.assertEqual(self.requests[2]['params']['prompt'], [{'type':'text','text':'hello'}])
        self.assertEqual(self.binding()['state'], 'ready')
        await asyncio.wait_for(self.closed.wait(), 1)

    async def test_late_advertised_startup_and_extension_notifications_not_spoken(self):
        self.mode = 'late_startup'
        self.assertEqual(await self.reply(), 'Reply: hello café')
        self.assertEqual(self.binding()['state'], 'ready')

    async def test_persistent_session_load_without_history_replay(self):
        await self.reply('first')
        original = self.binding()['session']
        # New runtime + DB connection simulate a bridge restart.
        other = Store(self.store.path)
        try:
            runtime = ACPRuntime(other, self.config)
            answer = await runtime.reply_turn('second', [{'role':'user','content':'first'}],
                                              device='one', conversation=self.conversation)
        finally:
            other.close()
        self.assertEqual(answer, 'Reply: second café')
        self.assertEqual(self.binding()['session'], original)
        self.assertEqual([m['method'] for m in self.requests],
                         ['initialize','session/new','session/prompt','initialize','session/load','session/prompt'])
        self.assertEqual(self.requests[-1]['params']['prompt'], [{'type':'text','text':'second'}])

    async def test_conversations_and_devices_never_share_session(self):
        await self.reply()
        other = self.store.conversation('two')
        await self.runtime.reply_turn('another', [], device='two', conversation=other)
        ids = [m['params']['sessionId'] for m in self.requests if m['method']=='session/prompt']
        self.assertEqual(len(set(ids)), 2)
        with self.assertRaises(Denied):
            await self.runtime.reply_turn('intrusion', [], device='two', conversation=self.conversation)
        self.assertEqual(len([m for m in self.requests if m['method']=='session/prompt']), 2)

    async def test_permission_denied_and_no_delegated_file_or_terminal_access(self):
        self.mode = 'permission'
        self.assertEqual(await self.reply(), 'Reply: hello café')
        self.assertEqual(self.client_responses[0]['result'], {'outcome':{'outcome':'cancelled'}})
        self.assertEqual([r['error']['code'] for r in self.client_responses[1:]], [-32601,-32601])

    async def test_failed_turn_never_replayed_or_silently_replaced(self):
        self.mode = 'drop'
        with self.assertRaises(ACPError): await self.reply()
        self.assertEqual(self.binding()['state'], 'uncertain')
        self.mode = 'normal'
        with self.assertRaisesRegex(ACPError, 'uncertain'): await self.reply('do not replay')
        self.assertEqual(len([m for m in self.requests if m['method']=='session/prompt']), 1)

    async def test_restart_with_inflight_binding_fails_closed(self):
        await self.reply()
        self.store.db.execute("UPDATE acp_sessions SET state='inflight'")
        with self.assertRaisesRegex(ACPError, 'uncertain'): await self.reply()
        self.assertEqual(len([m for m in self.requests if m['method']=='session/prompt']), 1)

    async def test_changed_endpoint_or_cwd_cannot_rebind_conversation(self):
        await self.reply()
        config = ACPConfig(str(self.root/'different'), socket=self.socket)
        runtime = ACPRuntime(self.store, config)
        with self.assertRaisesRegex(ACPError, 'changed'):
            await runtime.reply_turn('hello', [], device='one', conversation=self.conversation)

    async def test_load_failure_never_creates_replacement_or_replays_prompt(self):
        await self.reply()
        self.mode = 'no_load'
        with self.assertRaisesRegex(ACPError, 'load_unsupported'): await self.reply('second')
        self.assertEqual(len([m for m in self.requests if m['method']=='session/new']), 1)
        self.assertEqual(len([m for m in self.requests if m['method']=='session/prompt']), 1)

    async def test_invalid_streams_and_incomplete_turns(self):
        for mode in ('bad_json','oversize','answer_limit','mismatch','thought_only','truncated','error'):
            with self.subTest(mode=mode):
                self.conversation = self.store.conversation('one'); self.mode = mode
                with self.assertRaises(ACPError) as error: await self.reply()
                self.assertNotIn('synthetic-private-upstream-detail', str(error.exception))
                self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_incompatible_protocol_or_bad_session_does_not_prompt(self):
        for mode in ('version', 'bad_sid'):
            self.mode = mode
            with self.assertRaises(ACPError): await self.reply()
        self.assertFalse(any(m['method']=='session/prompt' for m in self.requests))

    async def test_deadline_cancels_agent_and_poison_session(self):
        self.mode = 'stall'
        with self.assertRaises(TimeoutError): await self.reply()
        await asyncio.wait_for(self.cancelled.wait(), 1)
        self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_deadline_includes_initialization_without_prompt(self):
        self.mode = 'initialize_stall'
        with self.assertRaises(TimeoutError): await self.reply()
        await asyncio.wait_for(self.closed.wait(), 1)
        self.assertIsNone(self.binding())
        self.assertFalse(any(m['method']=='session/prompt' for m in self.requests))

    async def test_ignored_metadata_counts_toward_transport_limits(self):
        self.mode = 'metadata_flood'
        for name, limit in (('TOTAL_BYTES', 1000), ('MAX_FRAMES', 5)):
            with self.subTest(limit=name), patch.object(ACPClient, name, limit):
                self.conversation = self.store.conversation('one')
                with self.assertRaisesRegex(ACPError, 'stream_limit'): await self.reply()
                self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_external_cancel_sends_notification_and_closes(self):
        self.mode = 'stall'
        task = asyncio.create_task(self.reply())
        await asyncio.wait_for(self.started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        await asyncio.wait_for(self.cancelled.wait(), 1)
        await asyncio.wait_for(self.closed.wait(), 1)
        self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_switching_existing_llm_history_requires_new_conversation(self):
        with self.assertRaisesRegex(ACPError, 'new_conversation'):
            await self.runtime.reply_turn('hello', [{'role':'user','content':'old prompt'}],
                                          device='one', conversation=self.conversation)
        self.assertEqual(self.requests, [])

    async def test_acp_default_and_explicit_selector(self):
        env = {'SARAH_ACP_CWD':str(self.root), 'SARAH_ACP_SOCKET':self.socket}
        for extra in ({}, {'SARAH_BACKEND':'acp'}):
            with patch.dict(os.environ, {**env, **extra}, clear=True):
                self.assertIsInstance(create_runtime(self.store), ACPRuntime)
        for backend in ('llm', 'qwen', 'invalid', ''):
            with patch.dict(os.environ, {**env, 'SARAH_BACKEND':backend}, clear=True):
                with self.assertRaisesRegex(ValueError, 'must be acp'):
                    create_runtime(self.store)
        with self.assertRaises(TypeError):
            make_app(self.store, self.runtime, ha=object())

    async def test_stdio_transport_is_reaped_and_does_not_inherit_bridge_environment(self):
        script = self.root / 'agent.py'
        script.write_text('''import json,os,sys
print('synthetic-private-stderr',file=sys.stderr,flush=True)
for line in sys.stdin:
    m=json.loads(line); method=m.get('method')
    if method=='initialize': r={'protocolVersion':1,'agentCapabilities':{}}
    elif method=='session/new': r={'sessionId':'stdio-session'}
    elif method=='session/prompt':
        assert 'SARAH_BRIDGE_TEST_SECRET' not in os.environ
        u={'jsonrpc':'2.0','method':'session/update','params':{'sessionId':'stdio-session','update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'stdio works'}}}}
        print(json.dumps(u),flush=True); r={'stopReason':'end_turn'}
    else: continue
    print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
''')
        config = ACPConfig(str(self.root), command=(sys.executable, '-u', str(script)))
        processes = []
        original = asyncio.create_subprocess_exec
        async def spawn(*args, **kwargs):
            proc = await original(*args, **kwargs); processes.append(proc); return proc
        with patch.dict(os.environ, {'SARAH_BRIDGE_TEST_SECRET':'synthetic-bridge'}), \
             patch('bridge.acp_client.asyncio.create_subprocess_exec', spawn):
            runtime = ACPRuntime(self.store, config)
            self.assertEqual(await runtime.reply_turn('hello', [], device='one', conversation=self.conversation), 'stdio works')
        self.assertEqual(len(processes), 1)
        self.assertIsNotNone(processes[0].returncode)

    async def test_cancellation_during_stdio_spawn_retains_and_reaps_handle(self):
        processes = []; started = asyncio.Event()
        original = asyncio.create_subprocess_exec
        async def spawn(*args, **kwargs):
            process = await original(*args, **kwargs); processes.append(process)
            started.set(); await asyncio.sleep(.05); return process
        config = ACPConfig(str(self.root), command=(sys.executable, '-c', 'import time; time.sleep(30)'))
        with patch('bridge.acp_client.asyncio.create_subprocess_exec', spawn):
            task = asyncio.create_task(ACPClient.connect(config))
            await asyncio.wait_for(started.wait(), 1); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await asyncio.wait_for(task, 2)
        self.assertIsNotNone(processes[0].returncode)

    async def test_repeated_cancellation_does_not_interrupt_connection_cleanup(self):
        self.mode = 'stall'; closing = asyncio.Event()
        original = ACPClient.close
        async def slow_close(client):
            closing.set(); await asyncio.sleep(.05); await original(client)
        with patch.object(ACPClient, 'close', slow_close):
            task = asyncio.create_task(self.reply())
            await asyncio.wait_for(self.started.wait(), 1); task.cancel()
            await asyncio.wait_for(closing.wait(), 1); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
        await asyncio.wait_for(self.closed.wait(), 1)
        self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_http_wav_to_acp_reply_and_cancellation(self):
        self.runtime.transcribe = lambda path: 'voice transcript'
        async def speak(text,path): path.write_bytes(b'synthetic MP3')
        self.runtime.speak = speak
        client = TestClient(TestServer(make_app(self.store, self.runtime)))
        await client.start_server()
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes(b'\0\0'*8000)
        auth = {'Authorization':'Bearer '+'a'*48}
        headers = {**auth, 'Content-Type':'audio/wav', 'X-Conversation':self.conversation, 'Idempotency-Key':'one'}
        try:
            health = await (await client.get('/v1/health', headers=auth)).json()
            self.assertEqual(health['backend'], 'acp'); self.assertNotIn('tools', health)
            for key in ('one', 'two'):
                if key == 'two': self.mode = 'stall'; self.started.clear()
                response = await client.post('/v1/turns', headers={**headers, 'Idempotency-Key':key}, data=buf.getvalue())
                self.assertEqual(response.status, 202); turn = (await response.json())['turn']
                if key == 'two':
                    await asyncio.wait_for(self.started.wait(), 1)
                    cancelled = await client.post('/v1/turns/'+turn+'/cancel', headers=auth, json={})
                    self.assertEqual((await cancelled.json())['state'], 'cancelled')
                    await asyncio.wait_for(self.cancelled.wait(), 1)
                else:
                    async with asyncio.timeout(2):
                        while True:
                            result = await (await client.get('/v1/turns/'+turn, headers=auth)).json()
                            if result['state'] in ('done','error'): break
                            await asyncio.sleep(.05)
                    self.assertEqual(result['state'], 'done', result)
                    self.assertEqual(result['detail'], 'Reply: voice transcript café')
                    self.assertTrue(result['audio'])
                    duplicate = await client.post('/v1/turns', headers=headers, data=buf.getvalue())
                    self.assertEqual((await duplicate.json())['turn'], turn)
            self.assertEqual(len([m for m in self.requests if m['method']=='session/prompt']), 2)
        finally:
            await client.close()
