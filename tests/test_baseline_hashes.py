import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_baseline_hashes_match_manifest():
    expected = {}
    for line in (ROOT / "BASELINE_SHA256.txt").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(maxsplit=1)
        expected[name.strip()] = digest
    for name, digest in expected.items():
        assert _sha(ROOT / name) == digest, name
