"""Private HTTP/TLS speech bridge to a durably bound ACP agent."""
import argparse
import asyncio
import hashlib
import json
import ipaddress
import ssl
import time
from collections import defaultdict, deque
from pathlib import Path
from aiohttp import web
from .core import UnconfiguredRuntime, Conflict, Denied, Store, validate_audio


def make_app(store, adapter=None):
    adapter = adapter or UnconfiguredRuntime()
    buckets=defaultdict(deque); tasks={}
    media=store.path.parent/'media'; media.mkdir(mode=0o700, exist_ok=True);media.chmod(0o700)
    @web.middleware
    async def guard(request,handler):
        try:
            auth=request.headers.get('Authorization','')
            if not auth.startswith('Bearer '):raise Denied('unauthorized')
            device=store.authenticate(auth[7:])
            q=buckets[device];now=time.monotonic()
            while q and q[0]<now-60:q.popleft()
            if len(q)>=90:return web.json_response({'error':'rate_limited'},status=429)
            q.append(now);request['device']=device
            response=await handler(request)
        except Denied as e:response=web.json_response({'error':str(e)},status=403)
        except Conflict as e:response=web.json_response({'error':str(e)},status=409)
        except (json.JSONDecodeError,UnicodeDecodeError,TypeError,KeyError):response=web.json_response({'error':'invalid_request'},status=400)
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff'
        return response
    app=web.Application(client_max_size=4*1024*1024,middlewares=[guard])
    async def body(request,keys):
        value=await request.json()
        if not isinstance(value,dict) or set(value)!=set(keys):raise Denied('unexpected_fields')
        return value
    async def health(request):
        return web.json_response({'connected':True,'ready':bool(adapter.ready),
            'reason':getattr(adapter,'reason',''),'protocol':1,
            'backend':'acp'})
    async def conversation(request):
        await body(request,[])
        return web.json_response({'conversation':store.conversation(request['device'])},status=201)
    def active(device,turn):return store.get(device,turn)['state'] not in ('done','error','cancelled','uncertain')
    async def execute(device,turn,clip):
        transcript=''
        try:
            transcript=await asyncio.to_thread(adapter.transcribe,clip)
            if not active(device,turn):return
            store.finish(device,turn,'thinking','S.A.R.A.H is thinking.',transcript)
            conversation=store.get(device,turn)['conversation']
            rows=store.db.execute("SELECT transcript,detail FROM turns WHERE device=? AND conversation=? AND state='done' ORDER BY rowid DESC LIMIT 4",(device,conversation)).fetchall()
            history=[]
            for row in reversed(rows):history.extend([{'role':'user','content':row['transcript']},{'role':'assistant','content':row['detail']}])
            text=await adapter.reply_turn(transcript,history,device=device,conversation=conversation)
            if not active(device,turn):return
            store.finish(device,turn,'speaking','Preparing spoken reply',transcript)
            try:await asyncio.wait_for(adapter.speak(text,media/(turn+'.mp3')),timeout=45)
            except Exception:
                (media/(turn+'.mp3')).unlink(missing_ok=True)
                # Text remains usable when optional free TTS unavailable.
            if active(device,turn):store.finish(device,turn,'done',text,transcript)
        except Exception as e:
            # Never include raw upstream exceptions/tokens in device output.
            if active(device,turn):store.finish(device,turn,'error','Voice request failed ('+type(e).__name__+'). Any dispatched action outcome may be unknown; no automatic retry.',transcript)
        finally:
            clip.unlink(missing_ok=True);tasks.pop(turn,None)
            if not active(device,turn) and store.get(device,turn)['state']!='done':(media/(turn+'.mp3')).unlink(missing_ok=True)
    async def submit(request):
        if not adapter.ready:return web.json_response({'error':adapter.reason},status=503)
        if request.content_type!='audio/wav':raise Denied('audio_content_type')
        device=request['device'];conversation=request.headers.get('X-Conversation','');key=request.headers.get('Idempotency-Key','')
        store.own(device,conversation)
        data=await request.read();validate_audio(data)
        fingerprint=hashlib.sha256(data).hexdigest()
        existing=store.db.execute('SELECT id FROM turns WHERE device=? AND request=?',(device,key)).fetchone()
        if not existing and tasks:raise Conflict('voice_worker_busy')
        turn=store.admit(device,conversation,key,fingerprint)
        if not existing:
            clip=media/(turn+'.wav');clip.touch(mode=0o600,exist_ok=False);clip.write_bytes(data)
            tasks[turn]=asyncio.create_task(execute(device,turn,clip))
        return web.json_response({'turn':turn},status=202)
    async def poll(request):
        turn=request.match_info['turn'];result=store.get(request['device'],turn)
        result['audio']=result['state']=='done' and (media/(turn+'.mp3')).is_file()
        return web.json_response(result)
    async def lookup(request):
        # Read-only, authenticated device ownership; never admits or dispatches.
        result=store.by_request(request['device'],request.match_info['request'])
        result['audio']=result['state']=='done' and (media/(result['id']+'.mp3')).is_file()
        return web.json_response(result)
    async def audio(request):
        turn=request.match_info['turn'];row=store.get(request['device'],turn)
        path=media/(turn+'.mp3')
        if row['state']!='done' or not path.is_file():raise Denied('not_found')
        return web.Response(body=path.read_bytes(),content_type='audio/mpeg')
    async def cancel(request):
        await body(request,[])
        # Discard output; cancellation cannot undo an ACP agent action.
        turn=request.match_info['turn'];result=store.cancel(request['device'],turn)
        task=tasks.get(turn)
        if task is not None: task.cancel()
        return web.json_response(result)
    async def cleanup(app):
        pending=list(tasks.values())
        for task in pending:task.cancel()
        await asyncio.gather(*pending,return_exceptions=True)
    app.on_cleanup.append(cleanup)
    app.router.add_get('/v1/health',health);app.router.add_post('/v1/conversations',conversation)
    app.router.add_get('/v1/requests/{request}',lookup)
    app.router.add_post('/v1/turns',submit);app.router.add_get('/v1/turns/{turn}',poll)
    app.router.add_get('/v1/turns/{turn}/audio',audio);app.router.add_post('/v1/turns/{turn}/cancel',cancel)
    return app

def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--cert');p.add_argument('--key')
    p.add_argument('--http',action='store_true',help='Explicit loopback-only HTTP behind a trusted TLS proxy')
    p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=8787)
    args=p.parse_args(argv)
    if args.http:
        try: loopback=ipaddress.ip_address(args.bind).is_loopback
        except ValueError: loopback=False
        if not loopback: p.error('--http requires a literal loopback bind address')
        if args.cert or args.key: p.error('--http cannot be combined with TLS certificate/key options')
    elif not args.cert or not args.key:
        p.error('--cert and --key are required unless --http is explicitly selected')
    return args


def main():
    args=parse_args();store=Store(args.db);store.recover()
    from .acp_runtime import create_runtime
    adapter=create_runtime(store)
    tls=None
    if not args.http:
        tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);tls.minimum_version=ssl.TLSVersion.TLSv1_2
        tls.load_cert_chain(args.cert,args.key)
    web.run_app(make_app(store,adapter),host=args.bind,port=args.port,ssl_context=tls,access_log=None)

if __name__=='__main__':main()
