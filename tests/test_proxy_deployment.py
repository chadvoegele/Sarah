"""Proxy-only HTTP is explicit/loopback-only; API-key provisioning is fail closed."""
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bridge.core import Denied, Store
from bridge.provision_device import provision
from bridge.server import parse_args


class ProxyTests(unittest.TestCase):
    def test_tls_still_required_by_default(self):
        with self.assertRaises(SystemExit): parse_args(['--db','state.db'])
        args = parse_args(['--db','state.db','--cert','server.pem','--key','server.key'])
        self.assertFalse(args.http)

    def test_http_only_on_explicit_literal_loopback(self):
        for bind in ('127.0.0.1','::1'):
            self.assertTrue(parse_args(['--db','state.db','--http','--bind',bind]).http)
        for bind in ('0.0.0.0','::','localhost','host.example.invalid'):
            with self.subTest(bind=bind), self.assertRaises(SystemExit):
                parse_args(['--db','state.db','--http','--bind',bind])
        with self.assertRaises(SystemExit):
            parse_args(['--db','state.db','--http','--cert','server.pem','--key','server.key'])

    def test_key_provisioning_idempotent_hashed_and_owned(self):
        with TemporaryDirectory() as tmp:
            db=Path(tmp)/'state.db'; token='a'*48
            provision(db,'android',token); provision(db,'android',token)
            store=Store(db)
            try:
                self.assertEqual(store.authenticate(token),'android')
                row=store.db.execute('SELECT * FROM devices').fetchone()
                self.assertEqual(row['digest'],hashlib.sha256(token.encode()).hexdigest())
                self.assertNotIn(token,str(dict(row)))
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM devices').fetchone()[0],1)
                with self.assertRaises(ValueError): provision(db,'android','b'*48)
                store.revoke('android')
                with self.assertRaises(ValueError): provision(db,'android',token)
                with self.assertRaises(Denied): store.authenticate(token)
            finally: store.close()

    def test_invalid_tokens_rejected_before_creation(self):
        with TemporaryDirectory() as tmp:
            for token in ('short','x'*257,'x'*40+'\n','x'*40+' ', 'ä'*48):
                with self.subTest(length=len(token)), self.assertRaises(ValueError):
                    provision(Path(tmp)/'state.db','android',token)
            self.assertFalse((Path(tmp)/'state.db').exists())
