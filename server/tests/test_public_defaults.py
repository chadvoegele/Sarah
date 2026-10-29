"""Publication-default and privacy regression tests; all values synthetic."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('privacy_scan', ROOT/'tools/privacy_scan.py')
scanner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scanner)


def test_privacy_scan_positive_and_negative_controls(tmp_path):
    (tmp_path/'PUBLICATION-MANIFEST.txt').write_text('PUBLICATION-MANIFEST.txt\nsource.py\n')
    sample = tmp_path/'source.py'
    sample.write_text('origin = "https://ha.example.invalid"\n')
    assert scanner.scan(tmp_path) == []
    sample.write_text('origin = "https://' + 'gateway.maton.ai"\n')
    assert any(kind == 'unexpected-endpoint' for _,_,kind in scanner.scan(tmp_path))
    sample.write_text('private origin = "http://' + '.'.join(('10','20','30','40')) + '"\n')
    assert any(kind == 'non-example-address' for _,_,kind in scanner.scan(tmp_path))
    sample.write_text('synthetic-private-canary')
    assert any(kind == 'private-literal' for _,_,kind in scanner.scan(tmp_path, ('synthetic-private-canary',)))
    sample.unlink()
    (tmp_path/'server.key').write_text('synthetic')
    assert any(kind == 'private-or-generated-file' for _,_,kind in scanner.scan(tmp_path))
    (tmp_path/'pointer').symlink_to(tmp_path/'server.key')
    assert any(kind == 'symlink' for _,_,kind in scanner.scan(tmp_path))


def test_project_mit_license_metadata():
    license_text = (ROOT / "LICENSE").read_text()
    assert license_text.startswith("MIT License\n\nCopyright (c) 2026 serexe\n")
    assert "Permission is hereby granted, free of charge" in license_text
    assert 'THE SOFTWARE IS PROVIDED "AS IS"' in license_text
    assert "LICENSE" in (ROOT / "PUBLICATION-MANIFEST.txt").read_text().splitlines()


def test_public_source_privacy_hygiene(tmp_path):
    # Scan the tracked publication, not private runtime state/dependencies.
    # The scanner still rejects every unmanifested or forbidden published file.
    import shutil
    import subprocess
    paths = subprocess.check_output(['git','ls-files','-z','.'], cwd=ROOT).decode().split('\0')
    for name in filter(None, paths):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    assert scanner.scan(tmp_path) == []
