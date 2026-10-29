"""Bounded ACP v1 JSON-RPC client for trusted Unix sockets or stdio agents."""
import asyncio
import contextlib
import hashlib
import json
import math
import os
import signal
from dataclasses import dataclass
from pathlib import Path


class ACPError(RuntimeError):
    """Local reason codes only; never expose agent errors or protocol payloads."""


async def settle(task):
    """Finish owned cleanup even when cancellation is repeated."""
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


@dataclass(frozen=True)
class ACPConfig:
    cwd: str
    socket: str = ''
    command: tuple[str, ...] = ()
    timeout: float = 120

    def __post_init__(self):
        if not Path(self.cwd).is_absolute() or '\0' in self.cwd:
            raise ValueError('SARAH_ACP_CWD must be an absolute agent-side directory')
        if bool(self.socket) == bool(self.command):
            raise ValueError('Set exactly one of SARAH_ACP_SOCKET or SARAH_ACP_COMMAND')
        if self.socket and (not Path(self.socket).is_absolute() or '\0' in self.socket):
            raise ValueError('SARAH_ACP_SOCKET must be an absolute Unix socket path')
        if (not isinstance(self.command, tuple) or
                any(not isinstance(arg, str) or not arg or '\0' in arg for arg in self.command)):
            raise ValueError('SARAH_ACP_COMMAND must be a nonempty JSON argv array')
        if not math.isfinite(self.timeout) or not 1 <= self.timeout <= 600:
            raise ValueError('SARAH_ACP_TIMEOUT_SECONDS must be between 1 and 600')

    @classmethod
    def from_env(cls):
        raw = os.getenv('SARAH_ACP_COMMAND', '')
        argv = json.loads(raw) if raw else []
        if not isinstance(argv, list):
            raise ValueError('SARAH_ACP_COMMAND must be a JSON argv array (no shell)')
        return cls(cwd=os.getenv('SARAH_ACP_CWD', ''),
                   socket=os.getenv('SARAH_ACP_SOCKET', ''), command=tuple(argv),
                   timeout=float(os.getenv('SARAH_ACP_TIMEOUT_SECONDS', '120')))

    @property
    def identity(self):
        # Do not store argv or environment secrets in the session-binding table.
        value = json.dumps([self.cwd, self.socket, self.command], separators=(',', ':'))
        return hashlib.sha256(value.encode()).hexdigest()


class ACPClient:
    LINE_BYTES = 256 * 1024
    TOTAL_BYTES = 4 * 1024 * 1024
    MAX_FRAMES = 8192
    ANSWER_CHARS = 12000

    def __init__(self, reader, writer, process=None):
        self.reader, self.writer, self.process = reader, writer, process
        self.sequence = 0
        self.total_bytes = self.frames = 0
        self.session_id = None
        self.collecting = False
        self.parts = []
        self.answer_chars = 0
        self.startup_info = None

    @classmethod
    async def connect(cls, config):
        if config.socket:
            reader, writer = await asyncio.open_unix_connection(config.socket, limit=cls.LINE_BYTES)
            return cls(reader, writer)
        # Administrator-selected argv, never model input, never a shell.
        env = {k: v for k, v in os.environ.items() if not k.startswith('SARAH_')}
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *config.command, cwd=config.cwd, env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=cls.LINE_BYTES,
            start_new_session=True))
        try:
            process = await asyncio.shield(spawn)
        except BaseException:
            async def cleanup_spawn():
                with contextlib.suppress(Exception):
                    process = await spawn
                    await cls(process.stdout, process.stdin, process).close()
            await settle(asyncio.create_task(cleanup_spawn()))
            raise
        return cls(process.stdout, process.stdin, process)

    async def send(self, message):
        data = (json.dumps({'jsonrpc': '2.0', **message}, ensure_ascii=False) + '\n').encode()
        if len(data) > self.LINE_BYTES:
            raise ACPError('acp_outgoing_frame_limit')
        self.writer.write(data)
        await self.writer.drain()

    async def request(self, method, params):
        self.sequence += 1
        request_id = self.sequence
        await self.send({'id': request_id, 'method': method, 'params': params})
        while True:
            try:
                line = await self.reader.readline()
            except (ValueError, asyncio.LimitOverrunError):
                raise ACPError('acp_frame_limit') from None
            if not line or not line.endswith(b'\n'):
                raise ACPError('acp_disconnected')
            self.frames += 1
            self.total_bytes += len(line)
            if len(line) > self.LINE_BYTES or self.total_bytes > self.TOTAL_BYTES or self.frames > self.MAX_FRAMES:
                raise ACPError('acp_stream_limit')
            try:
                message = json.loads(line)
            except (ValueError, UnicodeError):
                raise ACPError('acp_invalid_json') from None
            if not isinstance(message, dict) or message.get('jsonrpc') != '2.0':
                raise ACPError('acp_invalid_message')
            if 'method' in message:
                await self.handle_agent(message)
                continue
            if message.get('id') != request_id or isinstance(message.get('id'), bool):
                raise ACPError('acp_unexpected_response')
            if 'error' in message:
                raise ACPError('acp_request_failed')
            if not isinstance(message.get('result'), dict):
                raise ACPError('acp_invalid_result')
            result = message['result']
            if method in ('session/new', 'session/load'):
                metadata = result.get('_meta')
                pi = metadata.get('piAcp') if isinstance(metadata, dict) else None
                startup = pi.get('startupInfo') if isinstance(pi, dict) else None
                self.startup_info = startup if isinstance(startup, str) else None
            return result

    async def handle_agent(self, message):
        method = message['method']
        if 'id' in message:
            if method == 'session/request_permission':
                await self.send({'id': message['id'], 'result': {'outcome': {'outcome': 'cancelled'}}})
            else:
                # We advertise no filesystem/terminal/delegated execution support.
                await self.send({'id': message['id'], 'error': {'code': -32601, 'message': 'Unsupported client method'}})
            return
        if method != 'session/update' or not self.collecting:
            return
        params = message.get('params')
        if not isinstance(params, dict) or params.get('sessionId') != self.session_id:
            raise ACPError('acp_session_mismatch')
        update = params.get('update')
        if not isinstance(update, dict):
            raise ACPError('acp_invalid_update')
        if update.get('sessionUpdate') != 'agent_message_chunk':
            return  # Never speak thoughts, tool results, usage or command metadata.
        metadata = update.get('_meta')
        pi = metadata.get('piAcp') if isinstance(metadata, dict) else None
        if isinstance(pi, dict) and 'notify' in pi:
            return  # pi extension/UI notifications are not assistant answers.
        content = update.get('content')
        if not isinstance(content, dict) or content.get('type') != 'text':
            return
        text = content.get('text')
        if not isinstance(text, str):
            raise ACPError('acp_invalid_text')
        if text == self.startup_info:
            # pi-acp advertises this exact prelude in session/new metadata but
            # may deliver it only after the first prompt has already started.
            self.startup_info = None
            return
        self.answer_chars += len(text)
        if self.answer_chars > self.ANSWER_CHARS:
            raise ACPError('acp_answer_limit')
        self.parts.append(text)

    async def initialize(self):
        result = await self.request('initialize', {
            'protocolVersion': 1, 'clientCapabilities': {},
            'clientInfo': {'name': 'sarah', 'version': '1'}})
        if result.get('protocolVersion') != 1:
            raise ACPError('acp_version_mismatch')
        return result.get('agentCapabilities') or {}

    async def prompt(self, session_id, text):
        self.session_id = session_id
        self.collecting = True
        result = await self.request('session/prompt', {
            'sessionId': session_id, 'prompt': [{'type': 'text', 'text': text}]})
        self.collecting = False
        answer = ''.join(self.parts).strip()
        if result.get('stopReason') != 'end_turn' or not answer:
            raise ACPError('acp_incomplete_turn')
        return answer

    async def cancel(self):
        if self.session_id is not None:
            with contextlib.suppress(Exception):
                async with asyncio.timeout(1):
                    await self.send({'method': 'session/cancel', 'params': {'sessionId': self.session_id}})

    async def close(self):
        self.writer.close()
        with contextlib.suppress(Exception):
            async with asyncio.timeout(1):
                await self.writer.wait_closed()
        if self.process is not None:
            # Own only the spawned agent's process group, never a shared daemon.
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGTERM)
            try:
                async with asyncio.timeout(1):
                    await self.process.wait()
            except TimeoutError:
                pass
            finally:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(self.process.pid, signal.SIGKILL)
                await self.process.wait()
