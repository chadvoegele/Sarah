#!/usr/bin/env python3
"""Heuristic publication hygiene scan. Never prints matching sensitive values."""
import argparse
import ipaddress
import os
import stat
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit, parse_qsl

MANIFEST = 'PUBLICATION-MANIFEST.txt'
FORBIDDEN_DIRS = {'.git', '.backups', '.state', '.build', 'evidence', 'artifacts',
                  '__pycache__', '.pytest_cache', '.venv', '.verify', 'build', 'package'}
FORBIDDEN_SUFFIXES = {'.pem', '.key', '.p12', '.pfx', '.db', '.sqlite', '.wav', '.mp3', '.mp4', '.png', '.jpg', '.click', '.log', '.pyc'}
# GitHub hosts the explicitly pinned Docker speech dependencies.
PUBLIC_HOSTS = {'github.com', 'chatgpt.com', 'www.w3.org', 'docs.aiohttp.org', 'docs.pytest.org'}
URL = re.compile(r'https?://[^\s\"\'<>`)]+')
EMAIL = re.compile(r'\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b')
IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
PATTERNS = {
    'private-home-path': re.compile('/' + r'(?:root|Users)/[^\s\"\']+|' + '/ho' + r'me/(?![\"\'])[^\s\"\']+'),
    'matrix-id': re.compile(r'[!@][A-Za-z0-9_-]{8,}:[A-Za-z0-9.-]+'),
    'private-key': re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    'credential-shape': re.compile(r'\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,})\b'),
    'device-serial': re.compile(r'\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b'),
    'literal-secret-assignment': re.compile(r'''(?i)\b[\w-]*(?:token|api[_-]?key|password|secret)[\w-]*["']?\s*[:=]\s*["']?[A-Za-z0-9_+/.=-]{24,}'''),
}


def scan(root, literals=()):
    root = Path(root)
    findings = []
    if root.is_symlink() or not root.is_dir():
        return [('.', 0, 'invalid-publication-root')]
    root = root.resolve()
    expected = set()
    try:
        manifest = root / MANIFEST
        if manifest.is_symlink():
            raise ValueError('symlink manifest')
        for entry in manifest.read_text(encoding='utf-8').splitlines():
            candidate = Path(entry)
            if not entry or candidate.is_absolute() or '..' in candidate.parts or candidate.as_posix() != entry or entry in expected:
                raise ValueError('invalid manifest entry')
            expected.add(entry)
        if MANIFEST not in expected:
            raise ValueError('manifest must list itself')
    except (OSError, UnicodeError, ValueError):
        findings.append((MANIFEST, 0, 'invalid-or-missing-manifest'))
    directories = {str(parent) for entry in expected for parent in Path(entry).parents if str(parent) != '.'}
    observed = set()
    def walk_error(error):
        findings.append(('.', 0, 'unreadable-directory'))
    for directory, children, files in os.walk(root, followlinks=False, onerror=walk_error):
        for name in children:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                findings.append((relative, 0, 'symlink'))
            elif name in FORBIDDEN_DIRS:
                findings.append((relative, 0, 'forbidden-directory'))
            elif relative not in directories:
                findings.append((relative, 0, 'unmanifested-directory'))
        for name in files:
            observed.add((Path(directory) / name).relative_to(root).as_posix())
    for entry in sorted(expected - observed):
        findings.append((entry, 0, 'missing-manifest-entry'))
    for entry in sorted(observed):
        path = root / entry
        relative = Path(entry)
        if entry not in expected:
            findings.append((entry, 0, 'unmanifested-file'))
        if path.is_symlink():
            findings.append((entry, 0, 'symlink'))
            continue
        private_env = re.search(r'(^|\.)env($|\.)', path.name.lower()) and entry != 'config/bridge.env.example'
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or private_env or path.name in {'settings.json', 'native-settings.json'}:
            findings.append((entry, 0, 'private-or-generated-file'))
        try:
            if not stat.S_ISREG(path.stat().st_mode):
                findings.append((entry, 0, 'non-regular-file'))
                continue
            text = path.read_text(encoding='utf-8')
            if '\x00' in text:
                raise ValueError('binary text')
        except (UnicodeError, OSError, ValueError):
            findings.append((entry, 0, 'unreviewed-binary'))
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((str(relative), number, kind))
            for value in EMAIL.findall(line):
                if not value.lower().endswith(('.invalid', '.test', '@example.com', '@example.org')):
                    findings.append((str(relative), number, 'non-example-email'))
            for value in IPV4.findall(line):
                try:
                    address = ipaddress.ip_address(value)
                except ValueError:
                    continue
                if not address.is_loopback and value != '0.0.0.0' and not any(address in block for block in (ipaddress.ip_network('192.0.2.0/24'), ipaddress.ip_network('198.51.100.0/24'), ipaddress.ip_network('203.0.113.0/24'))):
                    findings.append((str(relative), number, 'non-example-address'))
            for value in URL.findall(line):
                try:
                    parsed = urlsplit(value)
                    host = parsed.hostname or ''
                    sensitive_query = any(re.search(r'(?i)token|key|secret|password|credential|signature', key) for key, _ in parse_qsl(parsed.query))
                    if parsed.username is not None or parsed.password is not None or sensitive_query:
                        findings.append((str(relative), number, 'url-credentials'))
                except ValueError:
                    findings.append((str(relative), number, 'malformed-url'))
                    continue
                if host not in PUBLIC_HOSTS and not host.endswith(('.invalid', '.test', '.example')) and host not in {'127.0.0.1', 'localhost', '::1'}:
                    findings.append((str(relative), number, 'unexpected-endpoint'))
            if any(value and value.casefold() in line.casefold() for value in literals):
                findings.append((str(relative), number, 'private-literal'))
    return sorted(set(findings))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', nargs='?', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--literal-file', type=Path)
    args = parser.parse_args()
    literals = ()
    if args.literal_file:
        private = args.literal_file.resolve()
        if private.is_relative_to(args.root.resolve()):
            parser.error('literal file must remain outside scanned tree')
        literals = tuple(value.strip() for value in private.read_text().splitlines() if value.strip())
    findings = scan(args.root, literals)
    for relative, number, kind in findings:
        print(f'{relative}:{number}: {kind}')
    print(f'privacy scan: {len(findings)} finding(s); heuristic only')
    return bool(findings)


if __name__ == '__main__':
    sys.exit(main())
