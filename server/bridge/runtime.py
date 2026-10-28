"""OpenAI-compatible local-model voice; optional server-owned tool dispatch."""
import asyncio
import os
import json
import re
import sys
import threading
from pathlib import Path
import httpx
from .clock import spoken_clocks
from faster_whisper import WhisperModel

from .llm_config import LLMConfig

LLM_TOTAL_SECONDS = 90
SSE_LINE_BYTES = 64 * 1024
SSE_TOTAL_BYTES = 1024 * 1024
TTS_STAGE_SECONDS = 20
TTS_TERMINATE_GRACE = 1


async def _sse_lines(response, deadline):
    # Raw identity bytes: do not let iter_lines or decompression accumulate an
    # unbounded line before our limits run. Count comments/metadata too.
    if response.headers.get('content-encoding', 'identity') != 'identity':
        raise RuntimeError('llm_sse_encoding_denied')
    pending = bytearray()
    total = 0
    async for chunk in response.aiter_raw():
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError('llm_deadline')
        total += len(chunk)
        if total > SSE_TOTAL_BYTES:
            raise RuntimeError('llm_sse_total_too_large')
        # Explicit LF boundaries preserve split UTF-8 and unfinished lines.
        pieces = chunk.split(b'\n')
        for index, piece in enumerate(pieces):
            if len(pending) + len(piece) > SSE_LINE_BYTES:
                raise RuntimeError('llm_sse_line_too_large')
            pending.extend(piece)
            if index < len(pieces) - 1:
                yield bytes(pending).rstrip(b'\r').decode('utf-8')
                pending.clear()
    if pending:
        yield bytes(pending).rstrip(b'\r').decode('utf-8')


async def _settle(task):
    """Finish owned cleanup even if its caller receives repeated cancellation."""
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


async def _reap_spawn(spawn):
    # Shielding spawn prevents losing the process handle at the fork/exec await.
    proc = await spawn
    if proc.returncode is None:
        try:
            proc.terminate()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), TTS_TERMINATE_GRACE)
        except TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
    await proc.wait()  # Always reap, including successful/nonzero exits.


async def _tts_process(*args, input=None, failure, **kwargs):
    spawn = asyncio.create_task(asyncio.create_subprocess_exec(*args, **kwargs))
    try:
        async with asyncio.timeout(TTS_STAGE_SECONDS):
            proc = await asyncio.shield(spawn)
            await proc.communicate(input)
            if proc.returncode:
                raise RuntimeError(failure)
    finally:
        await _settle(asyncio.create_task(_reap_spawn(spawn)))


def _money_words(match):
    """Bounded English dollar amounts only; no general numeric/prose parser."""
    before, after, amount, fraction = match.groups()
    if before and after:
        return match.group(0)
    digits = amount.replace(',', '')
    if len(digits) > 12:
        return match.group(0)
    dollars = int(digits)
    small = ('zero one two three four five six seven eight nine ten eleven twelve '
             'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
    tens = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
    def words(n):
        if n < 20:
            return small[n]
        if n < 100:
            return tens[n // 10] + (' ' + small[n % 10] if n % 10 else '')
        for scale, label in ((10**9, 'billion'), (10**6, 'million'),
                             (1000, 'thousand'), (100, 'hundred')):
            if n >= scale:
                return words(n // scale) + ' ' + label + (' ' + words(n % scale) if n % scale else '')
    cents = int(fraction or '0')
    parts = []
    if dollars or not cents:
        parts.append(words(dollars) + (' dollar' if dollars == 1 else ' dollars'))
    if cents:
        parts.append(words(cents) + (' cent' if cents == 1 else ' cents'))
    return ('minus ' if (before or after) and (dollars or cents) else '') + ' and '.join(parts)


def speech_text(text):
    """Remove presentation Markdown only at the speech boundary, not from history.

    Keep code contents/escaped symbols literal; never globally delete punctuation.
    Conservative delimiter boundaries preserve arithmetic and model identifiers.
    """
    literals = []
    def protect(value):
        literals.append(value)
        return '\x00' + str(len(literals) - 1) + '\x00'
    def literal(match):
        return protect(match.group(1))
    text = re.sub(r'(?m)^ {0,3}(`{3,}|~{3,})[^\n`~]*\n([\s\S]*?)^ {0,3}\1[ \t]*(?:\n|$)',
                  lambda m: protect(m.group(2)), text)
    text = re.sub(r'(?m)^ {0,3}(?:`{3,}|~{3,})[\w+-]*[ \t]*(?:\n|$)', '', text)
    text = re.sub(r'`+([^`\n]+)`+', literal, text)
    text = re.sub(r'\\([\\`*_{}\[\]()#+.!>~$-])', literal, text)
    text = re.sub(r'!?\[([^\]\n]+)\]\((?:[^()\n]|\([^()\n]*\))*\)', r'\1', text)
    text = re.sub(r'(?m)^ {0,3}#{1,6}[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$', r'\1', text)
    text = re.sub(r'(?m)^[ \t]*(?:[-+*]|\d+[.)])[ \t]+', '', text)
    for marker in ('***', '___', '**', '__', '*', '_'):
        pattern = r'(?<!\w)' + re.escape(marker) + r'(\S(?:[^\n]*?\S)?)' + re.escape(marker) + r'(?!\w)'
        text = re.sub(pattern, r'\1', text)
    # Before literal restoration: code and escaped dollars never become money.
    text = re.sub(r'(?<![\w\\$+./-])(-)?\$(-)?([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.([0-9]{2}))?(?![\w$/-]|[.,]\d)',
                  _money_words, text)
    text = spoken_clocks(text)
    return re.sub(r'\x00(\d+)\x00', lambda m: literals[int(m.group(1))], text).strip()


class VoiceRuntime:
    ready = True
    reason = 'Local-model voice conversation; integrations disabled unless explicitly configured'
    def __init__(self, config=None):
        config = config or LLMConfig.from_env()
        self.base_url = config.base_url
        self.api_key = config.api_key
        self.model = config.model
        self.whisper = None
        self.lock = threading.Lock()

    def transcribe(self, path):
        # Local-only: missing model fails; never cloud fallback/download.
        with self.lock:
            if self.whisper is None:
                self.whisper = WhisperModel('base', device='cpu', compute_type='int8', download_root=os.getenv('R1_WHISPER_MODELS', str(Path(__file__).resolve().parents[1]/'.build/whisper-models')), local_files_only=True)
            segments, _ = self.whisper.transcribe(str(path), beam_size=3, language='en', vad_filter=True)
            text = ' '.join(s.text.strip() for s in segments).strip()
        if not text or len(text)>8000:
            raise ValueError('empty_or_oversize_transcript')
        return text

    async def reply(self, text, history=(), dispatch=None):
        # One deadline across all HTTP attempts, not a per-read timeout and not
        # wait_for(to_thread(...)): cancellation closes the owned upstream socket.
        deadline = asyncio.get_running_loop().time() + LLM_TOTAL_SECONDS
        async with asyncio.timeout_at(deadline):
            inputs = list(history)+[{'role':'user','content':text}]
            results = []
            for _ in range(10):
                try:
                    result = await self._reply(text, history, deadline, inputs, dispatch is not None)
                except Exception:
                    if results: return 'I could not finish summarizing the tool results ('+type(sys.exc_info()[1]).__name__+').'
                    raise
                if isinstance(result, str):
                    return result
                if dispatch is None: raise RuntimeError('llm_tool_denied')
                for call in result:
                    try:
                        outcome = await dispatch(call['name'], json.loads(call['arguments']))
                    except (ValueError, TypeError, KeyError):
                        outcome = {'reply':'Home Assistant request denied. Nothing dispatched.'}
                    results.append(outcome)
                    inputs.extend([call, {'type':'function_call_output','call_id':call['call_id'],'output':json.dumps(outcome)}])
            return 'Tool request limit reached before I could finish the answer.'

    async def _reply(self, text, history, deadline, inputs=None, tools=False):
        from .ha import TOOLS as HA_TOOLS, LIGHT_GUIDANCE
        from .siyuan import TOOLS as SY_TOOLS, GUIDANCE
        from .calendar import TOOLS as CALENDAR_TOOLS, GUIDANCE as CALENDAR_GUIDANCE
        from datetime import datetime
        from zoneinfo import ZoneInfo
        calendar_clock=' Current server time in '+os.getenv('R1_TIMEZONE','UTC')+': '+datetime.now(ZoneInfo(os.getenv('R1_TIMEZONE','UTC'))).isoformat()+'. Resolve today/tomorrow against this clock, not training knowledge.'
        from .tvtime import TOOLS as TVTIME_TOOLS, GUIDANCE as TVTIME_GUIDANCE
        TOOLS=HA_TOOLS+SY_TOOLS+CALENDAR_TOOLS+TVTIME_TOOLS
        instructions = ('You are S.A.R.A.H, pronounced Sarah, your R1 voice companion. This identity applies only to this R1 instance. Converse naturally and reply briefly. Interpret free language and contextual followups from conversation; no command phrase or Home Assistant prefix is required. Tools are available on every turn, not mandatory. Ordinary discussion, quoted examples and negation are not action requests. Only supplied HA, SiYuan, Calendar and TV time functions exist. '+LIGHT_GUIDANCE+' '+GUIDANCE+' '+CALENDAR_GUIDANCE+' '+TVTIME_GUIDANCE+' Use ha_get_state for detailed current state, ha_list_services for actual service parameters, and ha_call_service for requested actions without repeated routine approval. No entity/action allowlist or spoken authorization gate applies. Never invent entities, service availability, tool outcomes or physical success. An accepted service is not necessarily a verified outcome. Use actual returned states and errors; do not automatically retry uncertain writes. No host shell, administration or arbitrary network tool exists.' if tools else 'You are S.A.R.A.H, pronounced Sarah, your R1 voice companion. This identity applies only to this R1 instance. Reply briefly in plain spoken English. No tools or Home Assistant actions are available. Never claim actions were performed.')
        if tools:
            instructions += calendar_clock
        messages = [{'role': 'system', 'content': instructions}]
        for item in inputs if inputs is not None else list(history)+[{'role':'user','content':text}]:
            if item.get('type') == 'function_call':
                messages.append({'role':'assistant', 'content':None, 'tool_calls':[{
                    'id':item['call_id'], 'type':'function',
                    'function':{'name':item['name'], 'arguments':item['arguments']}}]})
            elif item.get('type') == 'function_call_output':
                messages.append({'role':'tool', 'tool_call_id':item['call_id'], 'content':item['output']})
            else:
                messages.append(item)
        payload = {'model':self.model, 'messages':messages, 'stream':True,
                   'max_tokens':2048, 'chat_template_kwargs':{'enable_thinking':False}}
        if tools:
            payload.update(tools=[{'type':'function', 'function':{k:v for k,v in t.items() if k!='type'}} for t in TOOLS],
                           tool_choice='auto', parallel_tool_calls=False)
        headers = {'Accept':'text/event-stream', 'Accept-Encoding':'identity'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        # Explicit origin only: no pool, fallback, redirects, proxies, or retries.
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15),
                                     follow_redirects=False, trust_env=False) as client:
            async with client.stream('POST', self.base_url+'/chat/completions',
                                     headers=headers, json=payload) as response:
                if response.status_code != 200:
                    raise RuntimeError('llm_http_'+str(response.status_code))
                parts=[]; calls={}; output_chars=0; completed=None
                async for line in _sse_lines(response, deadline):
                    if not line.startswith('data:'):
                        continue
                    data=line[5:].strip()
                    if data=='[DONE]':
                        break
                    event=json.loads(data)
                    if event.get('error'):
                        raise RuntimeError('llm_response_failed')
                    choices=event.get('choices', [])
                    if not choices:
                        continue  # Usage-only chunk.
                    if len(choices)!=1 or choices[0].get('index',0)!=0:
                        raise RuntimeError('llm_invalid_choices')
                    choice=choices[0]; delta=choice.get('delta') or {}
                    content=delta.get('content') or ''
                    if not isinstance(content,str):
                        raise RuntimeError('llm_invalid_content')
                    output_chars+=len(content)
                    if output_chars>12000:
                        raise RuntimeError('reply_too_long')
                    parts.append(content)
                    # reasoning_content is intentionally never displayed/spoken.
                    for chunk in delta.get('tool_calls') or []:
                        if not tools or chunk.get('index')!=0 or chunk.get('type','function')!='function':
                            raise RuntimeError('llm_tool_denied')
                        call=calls.setdefault(0, {'type':'function_call','call_id':'','name':'','arguments':''})
                        function=chunk.get('function') or {}
                        for key,value in (('call_id',chunk.get('id','')),
                                          ('name',function.get('name','')),
                                          ('arguments',function.get('arguments',''))):
                            if not isinstance(value,str):
                                raise RuntimeError('llm_tool_denied')
                            call[key]+=value
                        if len(call['arguments'])>20000 or len(call['call_id'])>256 or len(call['name'])>100:
                            raise RuntimeError('llm_tool_denied')
                    if choice.get('finish_reason') is not None:
                        completed=choice['finish_reason']
                        break  # Terminal, even if upstream never sends EOF.
        if calls:
            call=calls[0]
            if completed!='tool_calls' or not call['call_id'] or call['name'] not in {t['name'] for t in TOOLS}:
                raise RuntimeError('llm_tool_denied')
            return [call]
        result=''.join(parts).strip()
        if completed!='stop' or not result:
            raise RuntimeError('llm_incomplete_response')
        return result

    async def speak(self, text, path):
        # Local CPU voice; no external speech fallback.
        # No eSpeak speech route, download, cloud or paid fallback.
        import tempfile
        path = Path(path)
        root = Path(os.getenv('R1_KOKORO_ROOT', str(Path(__file__).resolve().parents[1]/'.build/kokoro-audition')))
        # Same-filesystem private scratch; final media name never holds partial
        # output. No await between successful encode and atomic publication.
        with tempfile.TemporaryDirectory(prefix='.r1-tts-', dir=path.parent) as tmp:
            wav=Path(tmp)/'speech.wav'
            encoded=Path(tmp)/'speech.mp3'
            await _tts_process(str(root/'venv/bin/python'), '-I',
                str(Path(__file__).with_name('kokoro_tts.py')), '--output', str(wav),
                input=speech_text(text).encode(), failure='local_tts_failed',
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            await _tts_process('/usr/bin/ffmpeg','-nostdin','-loglevel','error','-y','-i',str(wav),'-codec:a','libmp3lame',str(encoded),
                failure='tts_encoding_failed',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            if not encoded.is_file() or encoded.stat().st_size == 0:
                raise RuntimeError('tts_encoding_failed')
            encoded.chmod(0o600)
            encoded.replace(path)
