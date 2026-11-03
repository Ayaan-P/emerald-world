"""Restorer tests use synthetic bytes, never game binaries or the network."""
import copy
import hashlib
import importlib.util
import json
import io
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[2]
SCRIPT = PROJECT / "scripts/restore_upstream_assets.py"
PATHS = ("data/mb_berry_fix.gba", "data/mb_colosseum.gba", "data/mb_ereader.gba")
PAYLOAD = b"explicit synthetic unit-test fixture, not a game binary"


def module():
    spec = importlib.util.spec_from_file_location("restore_upstream_assets", SCRIPT)
    assert spec is not None and spec.loader is not None
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixture():
    return {"upstream": "https://github.com/alanb2305/pokeemerald-native",
            "commit": "a" * 40,
            "assets": [{"path": p, "sha256": hashlib.sha256(PAYLOAD).hexdigest()} for p in PATHS]}


class ManifestTests(unittest.TestCase):
    def test_validates_exact_pinned_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(fixture()), encoding="utf-8")
            self.assertEqual(module().load_manifest(path), fixture())

    def test_rejects_unbounded_paths_hashes_and_sources(self):
        cases = []
        for path in ("../escape", "/data/mb_berry_fix.gba", "data\\mb_berry_fix.gba", "data/other.gba"):
            item = fixture()
            item["assets"][0]["path"] = path
            cases.append(item)
        for field, value in (("upstream", "http://github.com/alanb2305/pokeemerald-native"),
                             ("upstream", "https://evil.test/repo"),
                             ("upstream", "https://github.com/alanb2305/pokeemerald-native/"),
                             ("commit", "main"), ("commit", "g" * 40)):
            item = fixture()
            item[field] = value
            cases.append(item)
        for value in ("0" * 63, "g" * 64, None):
            item = fixture()
            item["assets"][0]["sha256"] = value
            cases.append(item)
        item = fixture()
        item["assets"][1] = copy.deepcopy(item["assets"][0])
        cases.extend([item, {**fixture(), "assets": fixture()["assets"][:2]}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            for data in cases:
                with self.subTest(data=data):
                    path.write_text(json.dumps(data), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        module().load_manifest(path)


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(fixture()), encoding="utf-8")
        self.api = module()
        self.urls = []

    def opener(self, url, timeout):
        self.urls.append(url)
        return io.BytesIO(PAYLOAD)

    def run_restore(self, **kwargs):
        return self.api.restore(self.root, self.manifest, opener=kwargs.pop("opener", self.opener), **kwargs)

    def test_restores_verified_bytes_with_exact_urls_and_no_rewrites(self):
        self.run_restore()
        self.assertEqual(len(self.urls), 3)
        for path in PATHS:
            self.assertEqual((self.root / path).read_bytes(), PAYLOAD)
            self.assertIn("https://raw.githubusercontent.com/alanb2305/pokeemerald-native/" + "a" * 40 + "/" + path, self.urls)
        before = [(self.root / p).stat().st_mtime_ns for p in PATHS]
        self.urls.clear()
        self.run_restore()
        self.assertEqual(self.urls, [])
        self.assertEqual(before, [(self.root / p).stat().st_mtime_ns for p in PATHS])

    def test_check_never_opens_network_and_requires_all_assets(self):
        with self.assertRaises(ValueError):
            self.run_restore(check=True)
        self.assertEqual(self.urls, [])
        self.run_restore()
        self.urls.clear()
        self.run_restore(check=True)
        self.assertEqual(self.urls, [])

    def test_wrong_existing_file_refused_before_any_network_or_write(self):
        target = self.root / PATHS[-1]
        target.parent.mkdir()
        target.write_bytes(b"do not overwrite")
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(target.read_bytes(), b"do not overwrite")
        self.assertEqual(self.urls, [])
        self.assertFalse((self.root / PATHS[0]).exists())

    def test_hash_mismatch_and_response_cap_leave_no_asset_or_temp(self):
        for data, message in ((b"wrong hash", "SHA256 mismatch"),
                              (b"x" * (4 * 1024 * 1024 + 1), "exceeds 4 MiB")):
            with self.subTest(size=len(data)):
                with self.assertRaisesRegex(ValueError, message):
                    self.run_restore(opener=lambda url, timeout: io.BytesIO(data))
                self.assertEqual(list((self.root / "data").glob("*")), [])

    def test_rejects_symlink_file_directory_and_root(self):
        outside = self.root / "outside"
        outside.mkdir()
        data = self.root / "data"
        try:
            data.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Symlink creation unavailable: " + str(exc))
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(list(outside.iterdir()), [])
        data.unlink()
        data.mkdir()
        (data / "mb_berry_fix.gba").symlink_to(outside / "missing")
        with self.assertRaises(ValueError):
            self.run_restore()
        root_link = self.root / "root-link"
        root_link.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.api.restore(root_link, self.manifest, opener=self.opener)
        self.assertEqual(self.urls, [])

    def test_concurrent_file_is_never_overwritten(self):
        target = self.root / PATHS[0]
        def racing_opener(url, timeout):
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(b"concurrent writer")
            return io.BytesIO(PAYLOAD)
        with self.assertRaises((ValueError, FileExistsError)):
            self.run_restore(opener=racing_opener)
        self.assertEqual(target.read_bytes(), b"concurrent writer")
        self.assertEqual([p.name for p in target.parent.iterdir()], [target.name])

    def test_invalid_manifest_has_no_filesystem_or_network_effect(self):
        data = fixture()
        data["assets"][0]["path"] = "../outside.gba"
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_restore()
        self.assertEqual(self.urls, [])
        self.assertFalse((self.root / "data").exists())

    def test_cli_check_actual_project_assets_from_unrelated_cwd(self):
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--check"], cwd=self.root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3", result.stdout)

    def test_cli_explicit_root_manifest_and_missing_check_failure(self):
        args = [sys.executable, "-B", str(SCRIPT), "--check", "--root", str(self.root),
                "--manifest", str(self.manifest)]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.run_restore()
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
