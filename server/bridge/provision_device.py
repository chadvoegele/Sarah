"""Idempotent local provisioning from a private API-key file, not an admin HTTP API."""
import argparse
import hashlib
import hmac
from pathlib import Path

from .core import Store, ident


def provision(path, device, token):
    ident(device)
    if not 40 <= len(token) <= 256 or any(not 33 <= ord(c) <= 126 for c in token):
        raise ValueError('Device token must be 40-256 printable ASCII characters without whitespace')
    store = Store(path)
    try:
        row = store.db.execute('SELECT digest,revoked FROM devices WHERE id=?', (device,)).fetchone()
        if row:
            digest = hashlib.sha256(token.encode()).hexdigest()
            if row['revoked'] or not hmac.compare_digest(row['digest'], digest):
                raise ValueError('Existing device token differs or is revoked; refusing implicit rotation')
            return
        store.provision(device, token)
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--device', default='android')
    parser.add_argument('--token-file', type=Path, required=True)
    args = parser.parse_args()
    provision(args.db, args.device, args.token_file.read_text().strip())
    print('Device API key provisioned/verified; token not printed.')


if __name__ == '__main__':
    main()
