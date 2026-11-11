"""Generic ACP sessions: durable ownership, bounded warm transport, no prompt replay."""
import asyncio
import os

from .acp_client import ACPClient, ACPConfig, ACPError, settle
from .runtime import VoiceRuntime


class ACPRuntime(VoiceRuntime):
    ready = True
    backend = 'acp'
    reason = ('Generic ACP agent configured; the agent owns reasoning, tools and authorization. '
              'No bridge-owned integrations. Cancelled or uncertain agent turns are never replayed.')
    IDLE_SECONDS = 300

    def __init__(self, store, config=None):
        super().__init__()
        self.store = store
        self.config = config or ACPConfig.from_env()
        self._worker = self._worker_key = self._idle = None
        self._worker_lock = asyncio.Lock()
        self._closed = False
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS acp_sessions(
            device TEXT NOT NULL, conversation TEXT NOT NULL,
            backend TEXT NOT NULL, session TEXT NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(device,conversation), UNIQUE(backend,session))''')

    async def _evict(self):
        idle, self._idle = self._idle, None
        if idle is not None and idle is not asyncio.current_task():
            idle.cancel()
            await asyncio.gather(idle, return_exceptions=True)
        client, self._worker = self._worker, None
        self._worker_key = None
        if client is not None:
            await settle(asyncio.create_task(client.close()))

    async def close(self):
        self._closed = True
        async with self._worker_lock:
            await settle(asyncio.create_task(self._evict()))

    async def _expire(self):
        await asyncio.sleep(self.IDLE_SECONDS)
        async with self._worker_lock:
            await self._evict()

    def session_uncertain(self, *, device, conversation):
        row = self.store.db.execute('SELECT state FROM acp_sessions WHERE device=? AND conversation=?',
                                    (device, conversation)).fetchone()
        return row is not None and row['state'] != 'ready'

    def _binding(self, device, conversation, history):
        self.store.own(device, conversation)
        # Additive boundary: old databases stay readable, but no old conversation
        # is silently rebound, imported, replayed or assigned a replacement agent.
        if not self.store.db.execute('SELECT 1 FROM relay_conversations WHERE id=?', (conversation,)).fetchone():
            raise ACPError('acp_backend_requires_new_conversation')
        row = self.store.db.execute(
            'SELECT backend,session,state FROM acp_sessions WHERE device=? AND conversation=?',
            (device, conversation)).fetchone()
        if row and (row['backend'] != self.config.identity or row['state'] != 'ready'):
            raise ACPError('acp_session_uncertain_or_changed')
        prior = self.store.db.execute("SELECT 1 FROM turns WHERE device=? AND conversation=? AND state='done' LIMIT 1",
                                     (device, conversation)).fetchone()
        if not row and (history or prior):
            raise ACPError('acp_backend_requires_new_conversation')
        return row

    async def _open_session(self, client, row):
        capabilities = await client.initialize()
        params = {'cwd': self.config.cwd, 'mcpServers': []}
        if row:
            if not isinstance(capabilities, dict) or capabilities.get('loadSession') is not True:
                raise ACPError('acp_session_load_unsupported')
            await client.request('session/load', {**params, 'sessionId': row['session']})
            return row['session']
        result = await client.request('session/new', params)
        session_id = result.get('sessionId')
        if (not isinstance(session_id, str) or not session_id or len(session_id) > 256
                or any(ord(char) < 32 for char in session_id)):
            raise ACPError('acp_invalid_session')
        return session_id

    async def reply_turn(self, text, history, *, device, conversation):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ACPError('acp_invalid_prompt')
        if self._closed or self._worker_lock.locked():
            raise ACPError('acp_worker_unavailable')
        row = self._binding(device, conversation, history)
        async with self._worker_lock:
            client, admitted, success = None, False, False
            try:
                # Connection, initialization, load/new and prompt share one bound.
                async with asyncio.timeout(self.config.timeout):
                    key = (device, conversation, self.config.identity, row['session'] if row else None)
                    client = self._worker
                    if client is not None and (self._worker_key != key or client.reader.at_eof()
                            or (client.process is not None and client.process.returncode is not None)):
                        await self._evict()
                        client = None
                    if self._idle is not None:
                        self._idle.cancel()
                        await asyncio.gather(self._idle, return_exceptions=True)
                        self._idle = None
                    if client is None:
                        client = await ACPClient.connect(self.config)
                        self._worker = client
                        session_id = await self._open_session(client, row)
                        if row is None:
                            # Persist identity BEFORE any prompt can be sent.
                            self.store.db.execute('INSERT INTO acp_sessions VALUES(?,?,?,?,?)',
                                (device, conversation, self.config.identity, session_id, 'ready'))
                        self._worker_key = (device, conversation, self.config.identity, session_id)
                    else:
                        session_id = row['session']
                    claimed = self.store.db.execute(
                        "UPDATE acp_sessions SET state='inflight' WHERE device=? AND conversation=? AND backend=? AND session=? AND state='ready'",
                        (device, conversation, self.config.identity, session_id))
                    if claimed.rowcount != 1:
                        raise ACPError('acp_session_busy')
                    admitted = True
                    answer = await client.prompt(session_id, text)
                    self.store.db.execute(
                        "UPDATE acp_sessions SET state='ready' WHERE device=? AND conversation=? AND state='inflight'",
                        (device, conversation))
                    admitted = False
                    success = True
                    return answer
            except BaseException:
                if admitted:
                    self.store.db.execute("UPDATE acp_sessions SET state='uncertain' WHERE device=? AND conversation=?",
                                          (device, conversation))
                raise
            finally:
                if not success:
                    async def cleanup():
                        if client is not None and admitted:
                            await client.cancel()
                        await self._evict()
                    await settle(asyncio.create_task(cleanup()))
                elif self.IDLE_SECONDS <= 0:
                    await settle(asyncio.create_task(self._evict()))
                else:
                    self._idle = asyncio.create_task(self._expire())


def create_runtime(store):
    if os.getenv('SARAH_BACKEND', 'acp') != 'acp':
        raise ValueError('SARAH_BACKEND must be acp')
    allowed = {'SARAH_BACKEND', 'SARAH_ACP_CWD', 'SARAH_ACP_SOCKET', 'SARAH_ACP_COMMAND',
               'SARAH_ACP_TIMEOUT_SECONDS', 'R1_WHISPER_MODELS', 'R1_KOKORO_ROOT', 'R1_TIMEZONE'}
    legacy_prefixes = ('R1_', 'SARAH_', 'SIYUAN_', 'MATON_', 'HERMES_GLOBAL_HOME')
    if any(name.startswith(legacy_prefixes) and name not in allowed for name in os.environ):
        raise ValueError('Unsupported legacy Sarah configuration; remove integration/profile settings and configure generic ACP')
    return ACPRuntime(store)
