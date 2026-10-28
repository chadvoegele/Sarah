"""Explicit live voice smoke test. Uses a private device token; never prints it."""
import argparse
import json
import ssl
import time
import uuid
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--wav', type=Path, required=True)
    parser.add_argument('--ca', type=Path, required=True)
    parser.add_argument('--require-audio', action='store_true')
    args = parser.parse_args()
    settings = json.loads((args.state / 'native-settings.json').read_text())
    tls = ssl.create_default_context(cafile=str(args.ca))
    with httpx.Client(base_url=settings['base'], verify=tls, trust_env=False,
                      follow_redirects=False, timeout=60) as client:
        assert client.get('/v1/health').status_code == 403
        client.headers['Authorization'] = 'Bearer ' + settings['token']
        health = client.get('/v1/health')
        health.raise_for_status()
        assert health.json()['ready'] and health.json()['protocol'] == 1
        assert not health.json()['tools'], 'Live smoke test requires integrations disabled'
        conversation = client.post('/v1/conversations', json={})
        conversation.raise_for_status()
        headers = {'Content-Type':'audio/wav',
                   'X-Conversation':conversation.json()['conversation'],
                   'Idempotency-Key':uuid.uuid4().hex}
        wav = args.wav.read_bytes()
        uploaded = client.post('/v1/turns', headers=headers, content=wav)
        assert uploaded.status_code == 202, uploaded.status_code
        turn = uploaded.json()['turn']
        duplicate = client.post('/v1/turns', headers=headers, content=wav)
        assert duplicate.status_code == 202 and duplicate.json()['turn'] == turn
        lookup = client.get('/v1/requests/' + headers['Idempotency-Key'])
        lookup.raise_for_status()
        assert lookup.json()['id'] == turn
        print('PASS TLS, authentication, health, conversation, upload, deduplication, lookup', flush=True)
        deadline = time.monotonic() + 150
        previous = None
        while time.monotonic() < deadline:
            response = client.get('/v1/turns/' + turn)
            response.raise_for_status()
            row = response.json()
            if row['state'] != previous:
                print('Stage:', row['state'], flush=True)
                previous = row['state']
            if row['state'] in ('done', 'error', 'cancelled', 'uncertain'):
                break
            time.sleep(2)
        else:
            raise TimeoutError('voice turn deadline')
        assert row['state'] == 'done', row['detail']
        assert row['transcript'].strip() and row['detail'].strip()
        print('Transcript:', row['transcript'])
        print('Reply:', row['detail'])
        if row['audio']:
            audio = client.get('/v1/turns/' + turn + '/audio')
            audio.raise_for_status()
            assert audio.headers['content-type'].startswith('audio/mpeg') and audio.content
            target = args.state / 'smoke-reply.mp3'
            target.touch(mode=0o600, exist_ok=True)
            target.write_bytes(audio.content)
            print('PASS reply MP3:', len(audio.content), 'bytes')
        elif args.require_audio:
            raise AssertionError('Expected synthesized reply audio')
        else:
            print('Text-only reply (optional TTS unavailable)')
        print('PASS live voice round trip', flush=True)


if __name__ == '__main__':
    main()
