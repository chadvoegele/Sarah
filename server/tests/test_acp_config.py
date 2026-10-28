"""Explicit ACP transport selection; no shell parsing or provider credentials."""
import os
import unittest
from unittest.mock import patch

from bridge.acp_client import ACPConfig


class ConfigTests(unittest.TestCase):
    def test_environment_socket(self):
        with patch.dict(os.environ, {'SARAH_ACP_CWD':'/work', 'SARAH_ACP_SOCKET':'/run/agent.sock'}, clear=True):
            config = ACPConfig.from_env()
        self.assertEqual(config.socket, '/run/agent.sock')
        self.assertEqual(config.command, ())
        self.assertEqual(config.timeout, 120)

    def test_environment_json_argv_not_shell(self):
        with patch.dict(os.environ, {'SARAH_ACP_CWD':'/work',
                'SARAH_ACP_COMMAND':'["agent", "argument with spaces", ";not a shell"]',
                'SARAH_ACP_TIMEOUT_SECONDS':'30'}, clear=True):
            config = ACPConfig.from_env()
        self.assertEqual(config.command, ('agent', 'argument with spaces', ';not a shell'))
        self.assertEqual(config.timeout, 30)

    def test_reject_invalid_or_ambiguous_transports(self):
        values = [dict(cwd='relative', socket='/run/agent.sock'),
                  dict(cwd='/work'), dict(cwd='/work', socket='relative.sock'),
                  dict(cwd='/work', socket='/run/agent.sock', command=('agent',)),
                  dict(cwd='/work', command=('',)), dict(cwd='/work', command=(1,)),
                  dict(cwd='/work', command=('agent\0injection',)),
                  *[dict(cwd='/work',socket='/run/agent.sock', timeout=t)
                    for t in (0,-1,601,float('nan'),float('inf'))]]
        for kwargs in values:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ACPConfig(**kwargs)
        for raw in ('"agent --option"', '{}', 'null', '[]'):
            with patch.dict(os.environ, {'SARAH_ACP_CWD':'/work','SARAH_ACP_COMMAND':raw}, clear=True):
                with self.assertRaises(ValueError): ACPConfig.from_env()

    def test_backend_identity_changes_with_endpoint_and_cwd(self):
        first = ACPConfig('/work', socket='/run/agent.sock')
        self.assertNotEqual(first.identity, ACPConfig('/other',socket='/run/agent.sock').identity)
        self.assertNotEqual(first.identity, ACPConfig('/work',socket='/run/other.sock').identity)
        self.assertEqual(len(first.identity), 64)
        self.assertNotIn('/run/', first.identity)
