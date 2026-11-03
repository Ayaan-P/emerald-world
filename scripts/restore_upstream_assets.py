#!/usr/bin/env python3
"""Restore only the three pinned upstream build assets, never overwrite files."""
import argparse
import hashlib
import json
import os
import stat
import sys
import tempfile
import urllib.request
from pathlib import Path
import re

UPSTREAM = "https://github.com/alanb2305/pokeemerald-native"
ALLOWED_PATHS = frozenset(("data/mb_berry_fix.gba", "data/mb_colosseum.gba", "data/mb_ereader.gba"))
DEFAULT_MANIFEST = Path(__file__).resolve().with_name("upstream_assets.json")
DEFAULT_ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 4 * 1024 * 1024


def load_manifest(path=DEFAULT_MANIFEST):
    """Read JSON and reject any source or target outside the fixed policy."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"upstream", "commit", "assets"}:
        raise ValueError("Invalid manifest fields")
    if data["upstream"] != UPSTREAM:
        raise ValueError("Only the fixed HTTPS upstream is allowed")
    if not isinstance(data["commit"], str) or not re.fullmatch(r"[0-9a-fA-F]{40}", data["commit"]):
        raise ValueError("Commit must be 40 hexadecimal characters")
    assets = data["assets"]
    if not isinstance(assets, list) or len(assets) != 3:
        raise ValueError("Manifest must contain exactly three assets")
    paths = []
    for asset in assets:
        if not isinstance(asset, dict) or set(asset) != {"path", "sha256"}:
            raise ValueError("Invalid asset fields")
        if not isinstance(asset["path"], str) or asset["path"] not in ALLOWED_PATHS:
            raise ValueError("Asset path is not allowed")
        if not isinstance(asset["sha256"], str) or not re.fullmatch(r"[0-9a-fA-F]{64}", asset["sha256"]):
            raise ValueError("SHA256 must be 64 hexadecimal characters")
        paths.append(asset["path"])
    if set(paths) != ALLOWED_PATHS:
        raise ValueError("Each allowed asset must appear exactly once")
    return data


def _safe_path(path):
    """Reject links (including Windows junctions) before resolving any path."""
    for component in reversed((path, *path.parents)):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Symlink/reparse point refused: " + str(component))
    return path


def _present(target, expected):
    _safe_path(target)
    try:
        info = target.lstat()
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
        raise ValueError("Not a bounded regular asset: " + str(target))
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(target, flags), "rb") as stream:
        if not os.path.samestat(info, os.fstat(stream.fileno())):
            raise ValueError("Asset changed while opening: " + str(target))
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != expected.lower():
        raise ValueError("SHA256 mismatch, refusing overwrite: " + str(target))
    return True


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Upstream redirects are not allowed")


def _download(url, opener):
    # Disable environment proxies and redirects. Neither credentials nor auth handlers are used.
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect()).open
    with opener(url, timeout=30) as response:
        if hasattr(response, "geturl") and response.geturl() != url:
            raise ValueError("Unexpected response URL")
        if getattr(response, "status", 200) != 200:
            raise ValueError("Unexpected upstream HTTP status")
        chunks = []
        size = 0
        while True:
            chunk = response.read(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                return b"".join(chunks)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Upstream response exceeds 4 MiB")
            chunks.append(chunk)


def _publish(root, target, data):
    """Hard-link a complete same-directory temp file, atomically and without replacement."""
    _safe_path(root)
    _safe_path(target)
    target.parent.mkdir(exist_ok=True)
    _safe_path(target.parent)
    parent_info = target.parent.stat()
    directory_fd = None
    temporary = None
    try:
        # Anchor creation/publication to the checked directory on POSIX.
        if os.name == "posix":
            directory_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            if not os.path.samestat(parent_info, os.fstat(directory_fd)):
                raise ValueError("Asset directory changed")
            import secrets
            temporary = ".upstream-" + secrets.token_hex(16) + ".tmp"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory_fd)
        else:
            fd, temporary = tempfile.mkstemp(prefix=".upstream-", suffix=".tmp", dir=target.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _safe_path(root)
        _safe_path(target)
        if not os.path.samestat(parent_info, target.parent.stat()):
            raise ValueError("Asset directory changed")
        if directory_fd is not None:
            os.link(temporary, target.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd,
                    follow_symlinks=False)
        else:
            # os.link fails if destination exists on Windows too. Never use replace/rename.
            os.link(temporary, target)
    finally:
        if temporary is not None:
            if directory_fd is not None:
                os.unlink(temporary, dir_fd=directory_fd)
            else:
                os.unlink(temporary)
        if directory_fd is not None:
            os.close(directory_fd)


def restore(root=DEFAULT_ROOT, manifest=DEFAULT_MANIFEST, *, check=False, opener=None):
    """Validate all existing assets, then restore missing ones. opener is a unit-test seam.

    Returns the number of validated assets (3). Raises ValueError/OSError on refusal.
    The explicit root must already exist. --check never creates files or uses the network.
    """
    data = load_manifest(manifest)
    root = Path(root).absolute()
    if ".." in root.parts:
        raise ValueError("Root cannot contain parent traversal")
    _safe_path(root)
    if not root.is_dir():
        raise ValueError("Root must be an existing project/test directory")
    missing = []
    for asset in data["assets"]:
        target = root / asset["path"]
        _safe_path(target)
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError("Asset escapes project root")
        if not _present(target, asset["sha256"]):
            missing.append((target, asset))
    if check and missing:
        raise ValueError("Missing upstream assets: " + ", ".join(a["path"] for _, a in missing))
    for target, asset in missing:
        url = "https://raw.githubusercontent.com/alanb2305/pokeemerald-native/" + data["commit"] + "/" + asset["path"]
        content = _download(url, opener)
        if hashlib.sha256(content).hexdigest() != asset["sha256"].lower():
            raise ValueError("Downloaded SHA256 mismatch: " + asset["path"])
        _publish(root, target, content)
    for asset in data["assets"]:
        if not _present(root / asset["path"], asset["sha256"]):
            raise ValueError("Asset disappeared during validation")
    return len(data["assets"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate all assets offline, without writes")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="Explicit project or research test root")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="JSON manifest (same bounded source/path policy)")
    args = parser.parse_args(argv)
    try:
        count = restore(args.root, args.manifest, check=args.check)
    except (ValueError, OSError) as exc:
        print("Upstream asset validation failed: " + str(exc), file=sys.stderr)
        return 1
    print(str(count) + " upstream assets verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
