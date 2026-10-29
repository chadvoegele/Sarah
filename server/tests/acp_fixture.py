"""Real loopback Unix ACP peer; no Dex, accounts, provider calls or real tools."""
import asyncio
import contextlib
import json
import tempfile
from pathlib import Path

from bridge.acp_client import ACPClient, ACPConfig
from bridge.acp_runtime import ACPRuntime
from bridge.core import Store


class ACPFixture:
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.socket = str(self.root / 'agent.sock')
        self.store = Store(self.root / 'state.db')
        self.store.provision('one', 'a' * 48)
        self.store.provision('two', 'b' * 48)
        self.conversation = self.store.conversation('one')
        self.config = ACPConfig(str(self.root), socket=self.socket, timeout=1)
        self.runtime = ACPRuntime(self.store, self.config)
        self.requests, self.client_responses, self.sessions = [], [], set()
        self.handlers = set()
        self.mode = 'normal'
        self.answers = []
        self.started, self.cancelled, self.closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        self.server = await asyncio.start_unix_server(self.peer, path=self.socket)

    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()
        for task in list(self.handlers):
            task.cancel()
        await asyncio.gather(*self.handlers, return_exceptions=True)
        self.store.close()
        self.tmp.cleanup()

    async def emit(self, writer, message):
        data = (json.dumps({'jsonrpc':'2.0', **message}, ensure_ascii=False)+'\n').encode()
        # Fragment NDJSON and non-ASCII text across socket writes.
        cut = data.index(b'\xc3')+1 if b'\xc3' in data else max(1, len(data)-4)
        writer.write(data[:cut]); await writer.drain(); await asyncio.sleep(0)
        writer.write(data[cut:]); await writer.drain()

    async def update(self, writer, sid, text, kind='agent_message_chunk'):
        await self.emit(writer, {'method':'session/update', 'params':{'sessionId':sid,
            'update':{'sessionUpdate':kind, 'content':{'type':'text','text':text}}}})

    async def peer(self, reader, writer):
        task = asyncio.current_task(); self.handlers.add(task)
        try:
            while line := await reader.readline():
                message = json.loads(line)
                if 'method' not in message:
                    self.client_responses.append(message); continue
                self.requests.append(message)
                method, params = message['method'], message.get('params', {})
                request_id = message.get('id')
                if method == 'session/cancel':
                    self.cancelled.set(); continue
                if method == 'initialize' and self.mode == 'initialize_stall': continue
                if method == 'initialize':
                    result = {'protocolVersion':2 if self.mode=='version' else 1,
                              'agentCapabilities':{'loadSession':self.mode!='no_load'}}
                elif method == 'session/new':
                    sid = 'voice-'+str(len(self.sessions)+1)
                    if self.mode == 'bad_sid': sid = ''
                    self.sessions.add(sid); result = {'sessionId':sid}
                    if self.mode == 'late_startup':
                        result['_meta'] = {'piAcp':{'startupInfo':'Delayed startup must not be spoken.'}}
                    await self.update(writer, sid, 'Startup text must not be spoken.')
                elif method == 'session/load':
                    self.assertIn(params['sessionId'], self.sessions)
                    await self.update(writer, params['sessionId'], 'Replayed historical answer must not be spoken.')
                    result = {}
                elif method == 'session/prompt':
                    self.started.set()
                    sid = params['sessionId']; text = params['prompt'][0]['text']
                    if self.mode == 'late_startup':
                        await self.update(writer, sid, 'Delayed startup must not be spoken.')
                        await self.emit(writer, {'method':'session/update','params':{'sessionId':sid,
                            'update':{'sessionUpdate':'agent_message_chunk','content':{'type':'text','text':'MCP startup banner'},
                                      '_meta':{'piAcp':{'notify':{'level':'info'}}}}}})
                    if self.mode == 'stall': continue
                    if self.mode == 'drop': return
                    if self.mode == 'bad_json':
                        writer.write(b'not json\n'); await writer.drain(); return
                    if self.mode == 'oversize':
                        writer.write(b'x'*(ACPClient.LINE_BYTES+2)+b'\n'); await writer.drain(); return
                    if self.mode == 'metadata_flood':
                        for _ in range(20):
                            await self.update(writer, sid, 'ignored metadata' * 4, 'agent_thought_chunk')
                    if self.mode == 'permission':
                        for method in ('session/request_permission', 'fs/read_text_file', 'terminal/create'):
                            await self.emit(writer, {'id':method, 'method':method, 'params':{'sessionId':sid}})
                            self.client_responses.append(json.loads(await reader.readline()))
                    await self.update(writer, sid, 'Private thoughts', 'agent_thought_chunk')
                    await self.update(writer, sid, 'Tool output', 'tool_call_update')
                    if self.answers:
                        await self.update(writer, sid, self.answers.pop(0))
                    elif self.mode != 'thought_only':
                        await self.update(writer, 'foreign-session' if self.mode=='mismatch' else sid, 'Reply: ')
                        await self.update(writer, sid, 'x'*12001 if self.mode=='answer_limit' else text+' café')
                    if self.mode == 'error':
                        await self.emit(writer, {'id':request_id, 'error':{'code':-1,'message':'synthetic-private-upstream-detail'}})
                        continue
                    result = {'stopReason':'max_tokens' if self.mode=='truncated' else 'end_turn'}
                else:
                    raise AssertionError(method)
                await self.emit(writer, {'id':request_id, 'result':result})
        except (ConnectionError, asyncio.CancelledError):
            pass
        finally:
            writer.close()
            with contextlib.suppress(Exception): await writer.wait_closed()
            self.closed.set(); self.handlers.discard(task)

    async def reply(self, text='hello', **kwargs):
        return await self.runtime.reply_turn(text, [], device='one', conversation=self.conversation, **kwargs)

    def binding(self):
        return self.store.db.execute('SELECT * FROM acp_sessions WHERE conversation=?', (self.conversation,)).fetchone()
