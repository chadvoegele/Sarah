"""Warm transport stays bound to one durable generic ACP owner at a time."""
import asyncio
import unittest
from unittest.mock import patch

from acp_fixture import ACPFixture
from bridge.acp_client import ACPClient, ACPConfig, ACPError


class WarmACPTests(ACPFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.runtime.IDLE_SECONDS = 300

    def methods(self):
        return [message['method'] for message in self.requests]

    async def test_success_reuses_worker_without_replayed_answer_or_new_session(self):
        self.assertEqual(await self.reply('first'), 'Reply: first café')
        session = self.binding()['session']
        self.assertEqual(await self.reply('second'), 'Reply: second café')
        self.assertEqual(self.binding()['session'], session)
        self.assertEqual(self.methods(), ['initialize', 'session/new', 'session/prompt', 'session/prompt'])
        self.assertFalse(self.closed.is_set())
        await self.runtime.close()
        await asyncio.wait_for(self.closed.wait(), 1)
        with self.assertRaisesRegex(ACPError, 'worker_unavailable'):
            await self.reply()

    async def test_owner_change_evicts_and_return_loads_exact_session(self):
        first = self.conversation
        await self.reply('one')
        session = self.binding()['session']
        other = self.store.conversation('two')
        self.assertEqual(await self.runtime.reply_turn('two', [], device='two', conversation=other), 'Reply: two café')
        self.assertEqual(await self.reply('return'), 'Reply: return café')
        loads = [message['params']['sessionId'] for message in self.requests if message['method'] == 'session/load']
        self.assertEqual(loads, [session])
        self.assertEqual(self.conversation, first)
        self.assertEqual(self.methods().count('session/new'), 2)

    async def test_idle_expiry_closes_then_loads_not_replaces(self):
        self.runtime.IDLE_SECONDS = .02
        await self.reply('first')
        session = self.binding()['session']
        await asyncio.wait_for(self.closed.wait(), 1)
        self.assertEqual(await self.reply('second'), 'Reply: second café')
        self.assertEqual(self.binding()['session'], session)
        self.assertEqual(self.methods().count('session/new'), 1)
        self.assertEqual(self.methods().count('session/load'), 1)

    async def test_warm_error_poison_closes_and_never_reprompts(self):
        await self.reply('first')
        self.mode = 'drop'
        with self.assertRaises(ACPError):
            await self.reply('second')
        self.assertEqual(self.binding()['state'], 'uncertain')
        self.assertIsNone(self.runtime._worker)
        with self.assertRaisesRegex(ACPError, 'uncertain'):
            await self.reply('never send')
        self.assertEqual(self.methods().count('session/prompt'), 2)

    async def test_warm_cancel_is_uncertain_and_reaps_before_return(self):
        await self.reply('first')
        self.started.clear()
        self.mode = 'stall'
        task = asyncio.create_task(self.reply('second'))
        await asyncio.wait_for(self.started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(self.cancelled.wait(), 1)
        await asyncio.wait_for(self.closed.wait(), 1)
        self.assertEqual(self.binding()['state'], 'uncertain')
        self.assertIsNone(self.runtime._worker)

    async def test_inflight_owner_rejects_other_turn_without_queuing(self):
        self.mode = 'stall'
        task = asyncio.create_task(self.reply('first'))
        await asyncio.wait_for(self.started.wait(), 1)
        try:
            with self.assertRaisesRegex(ACPError, 'worker_unavailable'):
                await self.reply('never queue')
            self.assertEqual(self.methods().count('session/prompt'), 1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_metadata_limit_resets_per_prompt_but_not_per_frame(self):
        await self.reply('first')
        self.mode = 'metadata_flood'
        with patch.object(ACPClient, 'MAX_FRAMES', 5):
            with self.assertRaisesRegex(ACPError, 'stream_limit'):
                await self.reply('second')
        self.assertEqual(self.binding()['state'], 'uncertain')

    async def test_config_change_cannot_use_cached_session(self):
        await self.reply('first')
        self.runtime.config = ACPConfig(str(self.root/'other'), socket=self.socket)
        with self.assertRaisesRegex(ACPError, 'changed'):
            await self.reply('never send')
        self.assertEqual(self.methods().count('session/prompt'), 1)

    async def test_legacy_conversation_never_imported_even_without_history(self):
        self.store.db.execute('DELETE FROM relay_conversations WHERE id=?', (self.conversation,))
        with self.assertRaisesRegex(ACPError, 'new_conversation'):
            await self.reply()
        self.assertEqual(self.requests, [])
        self.conversation = self.store.conversation('one')
        self.assertEqual(await self.reply(), 'Reply: hello café')

    async def test_completed_history_cannot_be_bypassed_by_empty_argument(self):
        turn = self.store.admit('one', self.conversation, 'legacy-done', 'synthetic')
        self.store.finish('one', turn, 'done', 'old answer', 'old request')
        with self.assertRaisesRegex(ACPError, 'new_conversation'):
            await self.reply()
        self.assertEqual(self.requests, [])
