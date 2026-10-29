"""Speech bridge to isolated, durably bound ACP agent sessions."""
import asyncio
import os

from .acp_client import ACPClient, ACPConfig, ACPError, settle
from .runtime import SpeechRuntime


class ACPRuntime(SpeechRuntime):
    ready = True
    backend = 'acp'
    reason = ('ACP agent backend configured; agent controls its own tools. '
              'Client permission requests are denied; no bridge-owned integrations.')

    def __init__(self, store, config=None):
        super().__init__()
        self.store = store
        self.config = config or ACPConfig.from_env()
        self.store.db.execute('''CREATE TABLE IF NOT EXISTS acp_sessions(
            device TEXT NOT NULL, conversation TEXT NOT NULL,
            backend TEXT NOT NULL, session TEXT NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(device,conversation), UNIQUE(backend,session))''')

    async def reply_turn(self, text, history, *, device, conversation):
        self.store.own(device, conversation)
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ACPError('acp_invalid_prompt')
        row = self.store.db.execute(
            'SELECT backend,session,state FROM acp_sessions WHERE device=? AND conversation=?',
            (device, conversation)).fetchone()
        if row and (row['backend'] != self.config.identity or row['state'] != 'ready'):
            raise ACPError('acp_session_uncertain_or_changed')
        if not row and history:
            raise ACPError('acp_backend_requires_new_conversation')
        client = None
        admitted = False
        try:
            # One deadline includes connection, initialization, load/new and prompt.
            async with asyncio.timeout(self.config.timeout):
                client = await ACPClient.connect(self.config)
                capabilities = await client.initialize()
                params = {'cwd': self.config.cwd, 'mcpServers': []}
                if row:
                    if not isinstance(capabilities, dict) or capabilities.get('loadSession') is not True:
                        raise ACPError('acp_session_load_unsupported')
                    session_id = row['session']
                    await client.request('session/load', {**params, 'sessionId': session_id})
                else:
                    result = await client.request('session/new', params)
                    session_id = result.get('sessionId')
                    if (not isinstance(session_id, str) or not session_id or len(session_id) > 256 or
                            any(ord(c) < 32 for c in session_id)):
                        raise ACPError('acp_invalid_session')
                    # Durable identity before any prompt is submitted.
                    self.store.db.execute('INSERT INTO acp_sessions VALUES(?,?,?,?,?)',
                        (device, conversation, self.config.identity, session_id, 'ready'))
                claimed = self.store.db.execute(
                    "UPDATE acp_sessions SET state='inflight' WHERE device=? AND conversation=? AND state='ready'",
                    (device, conversation))
                if claimed.rowcount != 1:
                    raise ACPError('acp_session_busy')
                admitted = True
                answer = await client.prompt(session_id, text)
                self.store.db.execute("UPDATE acp_sessions SET state='ready' WHERE device=? AND conversation=?",
                                      (device, conversation))
                admitted = False
                return answer
        except BaseException:
            if admitted:
                # A transport error, timeout, cancellation or restart cannot prove
                # what the agent did. Never replace the session or replay a prompt.
                self.store.db.execute("UPDATE acp_sessions SET state='uncertain' WHERE device=? AND conversation=?",
                                      (device, conversation))
            raise
        finally:
            if client is not None:
                async def cleanup():
                    if admitted:
                        await client.cancel()
                    await client.close()
                await settle(asyncio.create_task(cleanup()))


def create_runtime(store):
    # Retain the deployed selector as a compatibility assertion, not a fallback.
    if os.getenv('SARAH_BACKEND', 'acp') != 'acp':
        raise ValueError('SARAH_BACKEND must be acp')
    return ACPRuntime(store)
