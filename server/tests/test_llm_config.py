"""Provider configuration and malformed chat streams; no real credentials/network."""
import json
import os
from unittest.mock import patch

import pytest

from bridge.llm_config import LLMConfig
from bridge.runtime import VoiceRuntime
from test_runtime import Stream, Transport, runtime, tool_events, text_events


@pytest.mark.parametrize('url', [
    'http://provider.example/v1', 'http://'+'192.168.'+'1.10/v1',
    'https://'+'user:password@provider.invalid/v1', 'https://provider.example/v1?'+'token=x',
    'https://provider.example/v1#fragment', 'file:///tmp/model', 'https://'+'[bad/v1',
    'https://'+'provider.example:bad/v1', 'https://provider.example/v1\n', '',
])
def test_rejects_unsafe_endpoint(url):
    with pytest.raises(ValueError):
        LLMConfig(url)


@pytest.mark.parametrize('url', ['http://127.0.0.1:8012/v1', 'http://[::1]:8080/v1',
                                 'http://localhost:8080/v1', 'https://provider.example/api/v1/'])
def test_explicit_endpoints(url):
    assert LLMConfig(url).base_url == url.rstrip('/')


def test_environment_and_token_file(tmp_path):
    secret = tmp_path / 'token'
    secret.write_text('synthetic-token\n')
    values = {'SARAH_LLM_BASE_URL':'https://provider.example/custom/v1/',
              'SARAH_LLM_MODEL':'qwen-test', 'SARAH_LLM_API_KEY_FILE':str(secret)}
    with patch.dict(os.environ, values, clear=True):
        config = LLMConfig.from_env()
        adapter = VoiceRuntime()
        assert adapter.base_url == 'https://provider.example/custom/v1'
        assert adapter.model == 'qwen-test'
        assert adapter.api_key == 'synthetic-token'
        assert 'synthetic-token' not in repr(config)
        os.environ['SARAH_LLM_API_KEY'] = 'other'
        with pytest.raises(ValueError, match='only one'):
            LLMConfig.from_env()


@pytest.mark.parametrize('token', ['bad\r\nheader', 'bad\x00', 'nonascii-ä'])
def test_header_injection_rejected(token):
    with pytest.raises(ValueError):
        LLMConfig(api_key=token)


def test_blank_model_rejected():
    with pytest.raises(ValueError):
        LLMConfig(model=' ')


async def run_stream(events, *, dispatch=None):
    adapter, _ = runtime()
    chunks = [('data: '+json.dumps(e)+'\n\n').encode() for e in events]
    with Transport([(200, Stream(chunks))]) as transport:
        result = await adapter.reply('hello', dispatch=dispatch)
    return result, transport


class TestStreams:
    # Use asyncio.run so pytest-asyncio isn't needed.
    def test_incomplete_and_length_limited_answers_fail(self):
        import asyncio
        for finish in (None, 'length', 'content_filter'):
            events = [{'choices':[{'index':0,'delta':{'content':'partial'},'finish_reason':finish}]}]
            with pytest.raises(RuntimeError, match='llm_incomplete_response'):
                asyncio.run(run_stream(events))

    def test_fragmented_tool_call_and_chat_tool_result(self):
        import asyncio
        events = [
            {'choices':[{'index':0,'delta':{'tool_calls':[{'index':0,'id':'call-1',
                'type':'function','function':{'name':'ha_get_state','arguments':'{"entity_'}}]},'finish_reason':None}]},
            {'choices':[{'index':0,'delta':{'tool_calls':[{'index':0,
                'function':{'arguments':'id":"light.test"}'}}]},'finish_reason':'tool_calls'}]},
        ]
        chunks = [('data: '+json.dumps(e)+'\n\n').encode() for e in events]
        called = []

        async def dispatch(name, args):
            called.append((name,args))
            return {'state':'on'}

        async def check():
            adapter, _ = runtime()
            answer = Stream([('data: '+json.dumps(text_events('It is on.')[0])+'\n\n').encode()])
            with Transport([(200, Stream(chunks)), (200,answer)]) as transport:
                assert await adapter.reply('state?', dispatch=dispatch) == 'It is on.'
            payload = json.loads(transport.requests[1].content)
            assert payload['messages'][-1] == {'role':'tool','tool_call_id':'call-1','content':'{"state": "on"}'}
            assert payload['messages'][-2]['tool_calls'][0]['function']['name'] == 'ha_get_state'
        asyncio.run(check())
        assert called == [('ha_get_state', {'entity_id':'light.test'})]

    @pytest.mark.parametrize('name', ['unknown_shell_tool', 'ha_get_state'])
    def test_unknown_or_unrequested_tools_never_dispatch(self, name):
        import asyncio
        event = tool_events({'call_id':'x','name':name,'arguments':'{}'})
        with pytest.raises(RuntimeError, match='llm_tool_denied'):
            asyncio.run(run_stream(event))

    def test_no_token_omits_auth_header(self):
        import asyncio
        async def check():
            adapter = VoiceRuntime(LLMConfig('http://localhost:8000/v1', 'qwen'))
            with Transport([(200,Stream())]) as transport:
                assert await adapter.reply('hi') == 'hello'
            assert 'Authorization' not in transport.requests[0].headers
        asyncio.run(check())
