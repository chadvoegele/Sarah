"""Bridge-only export gate; tests never include live state or Android binary assets."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('privacy_scan', ROOT / 'tools/privacy_scan.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_manifest_is_complete_bridge_source_inventory():
    entries = (ROOT / 'PUBLICATION-MANIFEST.txt').read_text().splitlines()
    assert len(entries) == len(set(entries))
    assert 'LICENSE' in entries
    assert all(not path.startswith('android/') for path in entries)
    for directory in ('bridge', 'tests', 'config', 'docs', 'tools'):
        files = {path.relative_to(ROOT).as_posix() for path in (ROOT / directory).rglob('*')
                 if path.is_file() and '__pycache__' not in path.parts}
        assert files <= set(entries)


def test_staged_manifest_has_no_privacy_findings(tmp_path):
    entries = (ROOT / 'PUBLICATION-MANIFEST.txt').read_text().splitlines()
    for entry in entries:
        source = ROOT / entry
        destination = tmp_path / entry
        assert source.is_file() and not source.is_symlink()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    assert scanner.scan(tmp_path) == []


def test_packaging_uses_root_bridge_loopback_and_private_provisioning():
    docker = (ROOT / 'Dockerfile').read_text()
    entrypoint = ROOT / 'docker-entrypoint.sh'
    compose = (ROOT / 'compose.example.yaml').read_text()
    assert 'COPY bridge/ ./bridge/' in docker
    assert 'COPY LICENSE THIRD-PARTY-NOTICES.md' in docker
    assert 'USER sarah' in docker
    assert 'sha256sum -c -' in docker
    assert '127.0.0.1' in docker
    assert 'umask 077' in entrypoint.read_text()
    assert '--token-file "$key_path"' in entrypoint.read_text()
    assert 'network_mode: host' in compose
    assert 'read_only: true' in compose
    assert entrypoint.stat().st_mode & 0o111
    subprocess.run(['sh', '-n', str(entrypoint)], check=True)


def test_original_copyright_and_permission_notice_preserved():
    license_text = (ROOT / 'LICENSE').read_text()
    assert 'Copyright (c) 2026 serexe' in license_text
    assert 'The above copyright notice and this permission notice' in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text
