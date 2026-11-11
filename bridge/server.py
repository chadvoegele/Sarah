"""Authenticated speech transport. Reasoning and action authorization belong to ACP."""
import argparse
import asyncio
import hashlib
import ipaddress
import json
import ssl
import time
from collections import defaultdict, deque
from pathlib import Path

from aiohttp import web

from .core import Conflict, Denied, Store, UnconfiguredRuntime, validate_audio


DEVICE_KEY = web.RequestKey('sarah_device', str)


def make_app(store, adapter=None):
    adapter = adapter or UnconfiguredRuntime()
    store.db.execute('CREATE TABLE IF NOT EXISTS response_metrics(turn TEXT PRIMARY KEY, route TEXT NOT NULL, timings TEXT NOT NULL)')
    buckets = defaultdict(deque)
    tasks, streams = {}, {}
    reasoning = set()
    media = store.path.parent / 'media'
    media.mkdir(mode=0o700, exist_ok=True)
    media.chmod(0o700)

    @web.middleware
    async def guard(request, handler):
        try:
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                raise Denied('unauthorized')
            device = store.authenticate(auth[7:])
            bucket, now = buckets[device], time.monotonic()
            while bucket and bucket[0] < now - 60:
                bucket.popleft()
            if len(bucket) >= 90:
                response = web.json_response({'error': 'rate_limited'}, status=429)
            else:
                bucket.append(now)
                request[DEVICE_KEY] = device
                response = await handler(request)
        except Denied as error:
            response = web.json_response({'error': str(error)}, status=403)
        except Conflict as error:
            response = web.json_response({'error': str(error)}, status=409)
        except (json.JSONDecodeError, UnicodeDecodeError, TypeError, KeyError):
            response = web.json_response({'error': 'invalid_request'}, status=400)
        except web.HTTPException as error:
            reason = {404: 'not_found', 413: 'request_too_large'}.get(error.status, 'http_error')
            response = web.json_response({'error': reason}, status=error.status)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    app = web.Application(client_max_size=4*1024*1024, middlewares=[guard])

    async def empty_body(request):
        if await request.json() != {}:
            raise Denied('unexpected_fields')

    async def health(request):
        return web.json_response({'connected': True, 'ready': bool(adapter.ready),
                                  'reason': getattr(adapter, 'reason', ''),
                                  'protocol': 1, 'backend': 'acp'})

    async def conversation(request):
        await empty_body(request)
        return web.json_response({'conversation': store.conversation(request[DEVICE_KEY])}, status=201)

    def active(device, turn):
        return store.get(device, turn)['state'] not in ('done', 'error', 'cancelled', 'uncertain')

    async def transcribe(clip):
        # Native STT cannot be cancelled by cancelling to_thread's await.
        worker = asyncio.create_task(asyncio.to_thread(adapter.transcribe, clip))
        try:
            return await asyncio.shield(worker)
        except asyncio.CancelledError:
            while not worker.done():
                try:
                    await asyncio.shield(worker)
                except asyncio.CancelledError:
                    pass
                except Exception:
                    break
            if not worker.cancelled():
                worker.exception()
            raise

    def clear_chunks(turn):
        streams.pop(turn, None)
        for seq in range(32):
            (media / f'{turn}.{seq}.mp3').unlink(missing_ok=True)

    def released(device, turn, clip, task):
        # Covers Stop before execute's first instruction as well as native cleanup.
        clip.unlink(missing_ok=True)
        tasks.pop(turn, None)
        clear_chunks(turn)
        if store.get(device, turn)['state'] != 'done':
            (media / f'{turn}.mp3').unlink(missing_ok=True)

    async def speak_chunks(turn, text, timings):
        from .warm_voice import sentence_chunks
        stream = streams[turn] = {'count': 0, 'after': 0, 'complete': False}
        total, started = 0, time.monotonic()
        async with asyncio.timeout(240):
            for seq, chunk in enumerate(sentence_chunks(text)):
                while stream['count'] - stream['after'] >= 2:
                    await asyncio.sleep(.05)
                target = media / f'{turn}.{seq}.mp3'
                await adapter.speak(chunk, target)
                size = target.stat().st_size
                total += size
                if size == 0 or total > 4*1024*1024:
                    raise RuntimeError('chunk_audio_limit')
                stream['count'] += 1
                if seq == 0:
                    timings['first_mp3_ms'] = (time.monotonic() - started)*1000
            stream['complete'] = True
            while stream['after'] < stream['count']:
                await asyncio.sleep(.05)

    async def execute(device, turn, clip, admitted, upload_ms, chunked=False):
        transcript = ''
        started = time.monotonic()
        timings = {'upload_read_ms': upload_ms, 'queue_ms': (started-admitted)*1000}
        try:
            transcript = await transcribe(clip)
            timings['stt_ms'] = (time.monotonic()-started)*1000
            if not active(device, turn):
                return
            store.finish(device, turn, 'thinking', 'Sarah is thinking.', transcript)
            conv = store.get(device, turn)['conversation']
            rows = store.db.execute("SELECT transcript,detail FROM turns WHERE device=? AND conversation=? AND state='done' ORDER BY rowid DESC LIMIT 4", (device, conv)).fetchall()
            history = [message for row in reversed(rows) for message in (
                {'role': 'user', 'content': row['transcript']},
                {'role': 'assistant', 'content': row['detail']})]
            reply_started = time.monotonic()
            reasoning.add(turn)
            try:
                text = await adapter.reply_turn(transcript, history, device=device, conversation=conv)
            finally:
                reasoning.discard(turn)
            timings['reply_ms'] = (time.monotonic()-reply_started)*1000
            if not isinstance(text, str) or not text.strip() or len(text) > 12000:
                raise ValueError('invalid_assistant_text')
            if not active(device, turn):
                return
            store.finish(device, turn, 'speaking', text, transcript)
            tts_started = time.monotonic()
            try:
                if chunked:
                    await speak_chunks(turn, text, timings)
                else:
                    target = media / f'{turn}.mp3'
                    await asyncio.wait_for(adapter.speak(text, target), timeout=45)
                    if not 0 < target.stat().st_size <= 4*1024*1024:
                        raise RuntimeError('reply_audio_limit')
            except Exception:
                # Never retry the agent because optional speech failed.
                clear_chunks(turn)
                (media / f'{turn}.mp3').unlink(missing_ok=True)
                timings['tts_failed'] = 1
            timings['tts_ms'] = (time.monotonic()-tts_started)*1000
            if active(device, turn):
                store.finish(device, turn, 'done', text, transcript)
        except Exception as error:
            from .acp_client import ACPError
            if isinstance(error, ACPError) and str(error) == 'acp_backend_requires_new_conversation':
                detail = ('This conversation is incompatible with the generic ACP relay. History is preserved; '
                          'request not sent. Start a new conversation; no migration or automatic replay.')
                state = 'error'
            else:
                detail = ('Voice request failed (' + type(error).__name__ + '). Agent outcome may be unknown; '
                          'no automatic retry. Reconcile with your agent; start a new conversation if uncertain.')
                state = 'uncertain' if getattr(adapter, 'session_uncertain', lambda **kw: False)(device=device, conversation=store.get(device, turn)['conversation']) else 'error'
            if active(device, turn):
                store.finish(device, turn, state, detail, transcript)
        finally:
            timings['server_ms'] = (time.monotonic()-admitted)*1000
            store.db.execute('INSERT OR REPLACE INTO response_metrics VALUES(?,?,?)',
                             (turn, 'acp', json.dumps({k: round(v, 3) for k, v in timings.items()})))

    async def submit(request):
        if not adapter.ready:
            return web.json_response({'error': adapter.reason}, status=503)
        if request.content_type != 'audio/wav':
            raise Denied('audio_content_type')
        if 'X-Clarification-Parent' in request.headers:
            raise Denied('clarification_extension_unsupported')
        device = request[DEVICE_KEY]
        conv = request.headers.get('X-Conversation', '')
        key = request.headers.get('Idempotency-Key', '')
        store.own(device, conv)
        upload_started = time.monotonic()
        data = await request.read()
        validate_audio(data)
        upload_ms = (time.monotonic()-upload_started)*1000
        existing = store.db.execute('SELECT id FROM turns WHERE device=? AND request=?', (device, key)).fetchone()
        if not existing and tasks:
            raise Conflict('voice_worker_busy')
        turn = store.admit(device, conv, key, hashlib.sha256(data).hexdigest())
        if not existing:
            clip = media / f'{turn}.wav'
            clip.touch(mode=0o600, exist_ok=False)
            clip.write_bytes(data)
            task = asyncio.create_task(execute(device, turn, clip, time.monotonic(), upload_ms,
                                              request.headers.get('X-Audio-Chunks') == 'sentence-mp3-v1'))
            tasks[turn] = task
            task.add_done_callback(lambda done: released(device, turn, clip, done))
        return web.json_response({'turn': turn}, status=202)

    def result_audio(result):
        result['audio'] = result['state'] == 'done' and (media / (result['id']+'.mp3')).is_file()
        return result

    async def poll(request):
        turn = request.match_info['turn']
        result = result_audio(store.get(request[DEVICE_KEY], turn))
        stream = streams.get(turn)
        if stream is not None and result['state'] in ('speaking', 'done'):
            after = request.headers.get('X-Audio-After')
            if after is not None:
                if len(after) > 2 or not after.isdecimal() or not stream['after'] <= int(after) <= stream['count']:
                    raise Denied('audio_sequence_denied')
                stream['after'] = int(after)
            result['audio_chunks'] = {'count': stream['count'], 'complete': stream['complete']}
        metric = store.db.execute('SELECT route,timings FROM response_metrics WHERE turn=?', (turn,)).fetchone()
        if metric:
            result['timings'] = {**json.loads(metric['timings']), 'route': metric['route']}
        return web.json_response(result)

    async def lookup(request):
        return web.json_response(result_audio(store.by_request(request[DEVICE_KEY], request.match_info['request'])))

    async def audio(request):
        turn = request.match_info['turn']
        row = store.get(request[DEVICE_KEY], turn)
        path = media / f'{turn}.mp3'
        if row['state'] != 'done' or not path.is_file():
            raise Denied('not_found')
        return web.Response(body=path.read_bytes(), content_type='audio/mpeg')

    async def chunk_audio(request):
        turn = request.match_info['turn']
        row = store.get(request[DEVICE_KEY], turn)
        seq, stream = request.match_info['seq'], streams.get(turn)
        if not seq.isdecimal() or len(seq) > 2 or stream is None or not 0 <= int(seq) < stream['count'] or row['state'] not in ('speaking', 'done'):
            raise Denied('not_found')
        path = media / f'{turn}.{int(seq)}.mp3'
        if not path.is_file():
            raise Denied('not_found')
        return web.Response(body=path.read_bytes(), content_type='audio/mpeg')

    async def cancel(request):
        await empty_body(request)
        turn = request.match_info['turn']
        result = store.cancel(request[DEVICE_KEY], turn, agent_pending=turn in reasoning)
        task = tasks.get(turn)
        if task is not None and not task.cancelling():
            task.cancel()
        return web.json_response(result)

    async def cleanup(app):
        pending = list(tasks.values())
        for task in pending:
            if not task.cancelling():
                task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if hasattr(adapter, 'close'):
            await adapter.close()
        if hasattr(adapter, '_warm_voice'):
            await adapter._warm_voice.close()

    app.on_cleanup.append(cleanup)
    from .diagnostics import install
    install(app, store.path.parent, DEVICE_KEY)
    app.router.add_get('/v1/health', health)
    app.router.add_post('/v1/conversations', conversation)
    app.router.add_get('/v1/requests/{request}', lookup)
    app.router.add_post('/v1/turns', submit)
    app.router.add_get('/v1/turns/{turn}', poll)
    app.router.add_get('/v1/turns/{turn}/audio', audio)
    app.router.add_get('/v1/turns/{turn}/audio/{seq}', chunk_audio)
    app.router.add_post('/v1/turns/{turn}/cancel', cancel)
    return app


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--cert')
    parser.add_argument('--key')
    parser.add_argument('--http', action='store_true', help='Explicit loopback HTTP behind a trusted TLS proxy')
    parser.add_argument('--bind', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8787)
    args = parser.parse_args(argv)
    if args.http:
        try:
            loopback = ipaddress.ip_address(args.bind).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            parser.error('--http requires a literal loopback bind address')
        if args.cert or args.key:
            parser.error('--http cannot be combined with TLS certificate/key options')
    elif not args.cert or not args.key:
        parser.error('--cert and --key are required unless --http is explicitly selected')
    return args


def main():
    args = parse_args()
    store = Store(args.db)
    store.recover()
    from .acp_runtime import create_runtime
    adapter = create_runtime(store)
    tls = None
    if not args.http:
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(args.cert, args.key)
    web.run_app(make_app(store, adapter), host=args.bind, port=args.port, ssl_context=tls, access_log=None)


if __name__ == '__main__':
    main()
