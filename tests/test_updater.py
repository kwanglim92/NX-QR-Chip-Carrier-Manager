import hashlib
import sys

from src.updater import client


def test_version_compare_pads_missing_segments():
    assert not client._is_newer("2.2.0", "2.2")
    assert client._is_newer("2.2.1", "2.2")
    assert client._parse("2.2") == (2, 2, 0, 0)


def test_candidate_from_valid_manifest():
    manifest = {
        "latest_version": "2.3.0",
        "min_required_version": "2.2.0",
        "download_url": "http://10.4.1.141:8006/McQrManager-Setup-2.3.0.exe",
        "sha256": "a" * 64,
        "release_notes": "- update",
    }
    candidate = client._candidate_from_manifest(manifest, "2.2.0")
    assert candidate is not None
    assert candidate.latest_version == "2.3.0"
    assert candidate.sha256 == "a" * 64


def test_invalid_manifest_is_rejected():
    manifest = {
        "latest_version": "../2.3.0",
        "download_url": "http://10.4.1.141:8006/McQrManager-Setup-2.3.0.exe",
        "sha256": "a" * 64,
    }
    assert client._candidate_from_manifest(manifest, "2.2.0") is None


def test_sha256_match_and_mismatch(tmp_path):
    payload = b"hello updater"
    path = tmp_path / "setup.exe"
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    assert client._file_sha256_matches(path, digest)
    assert not client._file_sha256_matches(path, "0" * 64)


def test_check_and_apply_noop_when_not_frozen(monkeypatch):
    if hasattr(sys, "frozen"):
        monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(client, "UPDATE_ENABLED", True)
    assert not client.check_and_apply()


def test_check_and_apply_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(client, "UPDATE_ENABLED", False)
    assert not client.check_and_apply()


def test_check_and_apply_rejects_invalid_manifest(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(client, "UPDATE_ENABLED", True)
    monkeypatch.setattr(
        client,
        "_fetch_manifest",
        lambda: {"latest_version": "bad-version"},
    )
    assert not client.check_and_apply()
