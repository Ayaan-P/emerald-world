#!/usr/bin/env python3
"""Run the matched Expansion remote guest from a private source handoff."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import struct
import sys

sys.dont_write_bytecode = True


def verify(root):
    manifest = json.loads((root/'provenance.json').read_text(encoding='utf-8'))
    build = manifest.get('build', {})
    if (manifest.get('engine') != 'expansion-native' or build.get('engine') != 'expansion-native'
            or build.get('flags') != {'BITS': '64', 'TARGET_OS': 'windows', 'EW_REGION_STATE': '1',
                'EW_KANTO_CONTENT': '1', 'GENERATED_WORLD_REGIONS': '1', 'MAP_VERSION': 'combined',
                'WORLD_CHARACTER_COOP_EXPERIMENT': '0', 'WORLD_BASE_SHARE_EXPERIMENT': '0'}):
        raise ValueError('Not the matched Expansion Windows cohort')
    files = manifest.get('files', {})
    required = {'scripts/windows_expansion_entry.py', 'world/windows_client.py',
                'world/expansion_species.json', 'game/pokeemerald-native.exe'}
    if not isinstance(files, dict) or not required <= files.keys():
        raise ValueError('Missing matched game or Python guest source')
    seen = set()
    for name, digest in files.items():
        parts = PurePosixPath(name).parts
        if (not re.fullmatch(r'[A-Za-z0-9_+./-]+', name) or not parts or
                any(p in ('.', '..') or p.startswith('.') for p in name.split('/')) or
                name.startswith('/') or name.lower() in seen):
            raise ValueError('Unsafe provenance path')
        seen.add(name.lower())
        path = root.joinpath(*parts)
        for part in [path, *path.parents]:
            if part == root.parent:
                break
            info = part.lstat()
            if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise ValueError('Linked or reparse handoff path')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Handoff hash mismatch')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if actual != set(files) | {'provenance.json'}:
        raise ValueError('Unexpected handoff files. Extract into a fresh directory')
    binary = root/'game/pokeemerald-native.exe'
    data = binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != build.get('binary_sha256') or len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Wrong Expansion game binary')
    offset = struct.unpack_from('<I', data, 60)[0]
    if (offset+26 > len(data) or data[offset:offset+4] != b'PE\0\0'
            or struct.unpack_from('<H', data, offset+4)[0] != 0x8664
            or struct.unpack_from('<H', data, offset+24)[0] != 0x20b):
        raise ValueError('Expected Windows x64 PE32+ engine')
    return binary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true', help='verify hashes only, without launch or profile access')
    parser.add_argument('--self-test', action='store_true', help='verify game and Tk on Windows without joining')
    args = parser.parse_args(argv)
    if not args.verify and (sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64') or struct.calcsize('P') != 8):
        parser.exit(2, 'This guest requires Windows x64 and existing 64-bit Python 3.11+ with tkinter. No WSL or Linux launcher fallback.\n')
    if sys.version_info < (3, 11):
        parser.exit(2, 'Python 3.11+ with tkinter is required. Nothing was installed.\n')
    root = Path(__file__).resolve().parents[1]
    try:
        binary = verify(root)
        if args.verify:
            print(json.dumps({'integrity': 'verified', 'engine': 'expansion-native', 'windows_device_accepted': False}))
            return 0
        sys.path.insert(0, str(root))
        from world import windows_client as guest
        # Bind the existing remote-only UI to the verified Expansion engine.
        # Keep its saves separate from the older vanilla Windows guest namespace.
        base = guest.WindowsGuestSession
        class ExpansionGuestSession(base):
            def __init__(self, host, port, pin, invitation, **kwargs):
                local = os.environ.get('LOCALAPPDATA')
                if not local:
                    raise ValueError('LOCALAPPDATA is required for private Expansion profiles')
                kwargs.update(binary=binary, data_root=Path(local)/'EmeraldWorld', engine='expansion-native')
                super().__init__(host, port, pin, invitation, **kwargs)
        guest.WindowsGuestSession = ExpansionGuestSession
        guest.locate_game = lambda **kwargs: binary
        return guest.main(['--self-test'] if args.self_test else [])
    except (ValueError, OSError, ImportError, RuntimeError):
        parser.exit(2, 'Expansion handoff verification or runtime prerequisites failed. Use a fresh trusted archive and Python with tkinter. No game was selected from the legacy root.\n')


if __name__ == '__main__':
    raise SystemExit(main())
