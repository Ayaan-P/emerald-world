#!/usr/bin/env python3
"""Local-only private RC12 Expansion source/runtime handoff. No network calls."""
import struct
import hashlib
import json
import os
import stat
import subprocess
import zipfile
import re
from pathlib import Path

# Explicit OS imports only. A random installed DLL is not a system dependency.
SYSTEM_DLLS = frozenset('''kernel32.dll user32.dll gdi32.dll winmm.dll
imm32.dll ole32.dll oleaut32.dll shell32.dll version.dll advapi32.dll
setupapi.dll ws2_32.dll msvcrt.dll ucrtbase.dll comdlg32.dll comctl32.dll
rpcrt4.dll cfgmgr32.dll shlwapi.dll bcrypt.dll secur32.dll ntdll.dll
powrprof.dll hid.dll dwmapi.dll dxgi.dll d3d9.dll d3d11.dll'''.split())


def dll_closure(binary, candidates, imports):
    index = {}
    for path in candidates:
        if not re.fullmatch(r'[A-Za-z0-9_+.-]+\.dll', path.name, re.I):
            raise ValueError('Invalid DLL filename')
        key = path.name.lower()
        if key in index:
            raise ValueError('Case-ambiguous DLL candidates')
        index[key] = path
    found, edges, pending = {}, {}, [binary]
    while pending:
        path = pending.pop()
        edge = {'system': [], 'bundled': []}
        for name in sorted(set(imports(path)), key=str.lower):
            if not re.fullmatch(r'[A-Za-z0-9_+.-]+\.dll', name, re.I):
                raise ValueError('Invalid DLL import path')
            key = name.lower()
            if key in SYSTEM_DLLS or key.startswith(('api-ms-win-', 'ext-ms-win-')):
                edge['system'].append(key)
            elif key in index:
                edge['bundled'].append(index[key].name)
                if key not in found:
                    found[key] = index[key]
                    pending.append(index[key])
            else:
                raise ValueError('Unresolved non-system DLL: ' + name)
        edges[path.name] = edge
    return sorted(found.values(), key=lambda p: p.name.lower()), edges



def check_pe(data, *, dll=False):
    if len(data) < 64 or data[:2] != b'MZ':
        raise ValueError('Expected an x64 Windows PE, not a Linux or legacy root binary')
    offset = struct.unpack_from('<I', data, 60)[0]
    if offset + 26 > len(data) or data[offset:offset+4] != b'PE\0\0':
        raise ValueError('Invalid Windows PE header')
    machine = struct.unpack_from('<H', data, offset+4)[0]
    flags = struct.unpack_from('<H', data, offset+22)[0]
    magic = struct.unpack_from('<H', data, offset+24)[0]
    if machine != 0x8664 or magic != 0x20b or bool(flags & 0x2000) != dll:
        raise ValueError('Expected x64 PE32+ DLL' if dll else 'Expected x64 PE32+ executable')

# Match the selected Linux cohort, including its explicit manifest arguments.
# The generic release default alone does not select generated regions.
BUILD_ARGUMENTS = json.loads((Path(__file__).resolve().parents[1] /
                             'engines/living-cast-candidate.json').read_text())['build_arguments']
FLAGS = {'BITS': '64', 'TARGET_OS': 'windows', 'EW_REGION_STATE': '1',
         'EW_KANTO_CONTENT': '1',
         'GENERATED_WORLD_REGIONS': '1' if '--generated-regions' in BUILD_ARGUMENTS else '0',
         'MAP_VERSION': 'combined', 'WORLD_CHARACTER_COOP_EXPERIMENT': '0',
         'WORLD_BASE_SHARE_EXPERIMENT': '0'}
SECRET = re.compile(rb'-----BEGIN (?:[A-Z ]*PRIVATE KEY)-----|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}')
DATA = {'world/expansion_species.json', 'world/map_catalog.json',
        'world/trainer_reference.json', 'world/trainer_experience_catalog.json',
        'world/companion_move_names.json', 'world/encounter_traits.json',
        'world/practice_trainer_sources.json', 'world/rental_catalog.json'}
ENTRY = 'scripts/windows_expansion_entry.py'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    parts = name.split('/')
    devices = {'CON', 'PRN', 'AUX', 'NUL', *('COM'+str(i) for i in range(10)), *('LPT'+str(i) for i in range(10))}
    if any(not re.fullmatch(r'[A-Za-z0-9_+.-]+', p) or p.startswith('.') or p.endswith(('.', ' ')) or p.split('.')[0].upper() in devices for p in parts):
        raise ValueError('Unsafe archive path')


def check_source(name, data):
    safe_name(name)
    allowed = (name == ENTRY or name in DATA or
               re.fullmatch(r'world/[A-Za-z0-9_]+\.py', name) or
               name in {'launcher-web/package.json', 'launcher-web/package-lock.json',
                        'launcher-web/index.html', 'launcher-web/vite.config.js'} or
               (re.fullmatch(r'launcher-web/src/[A-Za-z0-9_.-]+\.(?:jsx|js|css|webp)', name)
                and '.test.' not in name and '.spec.' not in name))
    CREDENTIAL = re.compile(rb'''(?i)(?:["']?(?:api_key|password|secret|token|invite_token|access_token)["']?\s*[:=]\s*["'][A-Za-z0-9_+./=-]{16,}["'])''')
    if not allowed or SECRET.search(data) or CREDENTIAL.search(data):
        raise ValueError('Unapproved source path or secret-bearing source: ' + name)


def verify_receipt(receipt, app_pin, engine_pin, binary, integration):
    if not isinstance(receipt, dict):
        raise ValueError('Build receipt must be a JSON object')
    for pin in (app_pin, engine_pin):
        if not re.fullmatch(r'[0-9a-f]{40}', pin):
            raise ValueError('Pins must be exact lowercase 40-character Git commits')
    expected = {'schema': 1, 'engine': 'expansion-native', 'app_commit': app_pin,
                'engine_commit': engine_pin, 'flags': FLAGS,
                'binary_sha256': sha256(binary), 'integration_sha256': sha256(integration)}
    if any(receipt.get(k) != v for k, v in expected.items()) or not receipt.get('command') or not receipt.get('tools'):
        raise ValueError('Build receipt does not match pinned Expansion cohort, flags or binary')
    check_pe(binary)


def plain_path(path):
    path = Path(os.path.abspath(path))
    for part in [*reversed(path.parents), path]:
        if not part.exists() and not part.is_symlink():
            continue
        info = part.lstat()
        if (stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)) or
                (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
            raise ValueError('Linked, reparse or special paths are forbidden')
    return path


def write_archive(payload, provenance, output):
    output = plain_path(output)
    if output.exists():
        raise ValueError('Archive destination must be new')
    seen = set()
    for name in payload:
        safe_name(name)
        if name.lower() in seen or name.lower() == 'provenance.json':
            raise ValueError('Case-colliding archive paths')
        seen.add(name.lower())
    manifest = dict(provenance, files={n: sha256(b) for n, b in sorted(payload.items())},
                    distribution='manual-private-handoff-only', windows_device_accepted=False)
    payload = dict(payload, **{'provenance.json': (json.dumps(manifest, indent=2, sort_keys=True)+'\n').encode()})
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(payload.items()):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        with zipfile.ZipFile(output) as archive:
            if archive.testzip() is not None or any(sha256(archive.read(n)) != sha256(b) for n, b in payload.items()):
                raise ValueError('Archive read-back verification failed')
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return sha256(output.read_bytes())


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], timeout=30)


def verify_checkout(root, pin):
    if not re.fullmatch(r'[0-9a-f]{40}', pin):
        raise ValueError('Pin must be an exact lowercase 40-character Git commit')
    if git(root, 'rev-parse', 'HEAD').decode().strip() != pin:
        raise ValueError('Checkout does not match requested pin')
    if git(root, 'status', '--porcelain', '--untracked-files=normal').strip():
        raise ValueError('Checkout contains tracked or untracked changes; commit the final cohort before building')


def pinned_sources(app, pin):
    payload = {}
    records = git(app, 'ls-tree', '-rz', pin, '--', 'world', 'launcher-web', ENTRY).split(b'\0')
    for record in filter(None, records):
        metadata, raw_name = record.split(b'\t', 1)
        name = raw_name.decode('utf-8')
        if (name.endswith('.md') or name == 'launcher-web/.gitignore' or
                (name.startswith('launcher-web/src/') and ('.test.' in name or '.spec.' in name))):
            continue
        if not metadata.startswith(b'100644 ') and not metadata.startswith(b'100755 '):
            raise ValueError('Only ordinary committed source files are permitted')
        data = git(app, 'show', pin + ':' + name)
        check_source(name, data)
        payload[name] = data
    required = DATA | {'world/windows_client.py', 'launcher-web/index.html', ENTRY}
    if not required <= payload.keys():
        raise ValueError('Pinned app is missing matched UI, Python modules or Expansion entry point')
    return payload


def pe_imports(path, objdump):
    result = subprocess.run([objdump, '-p', str(path)], check=True,
                            capture_output=True, text=True, timeout=30)
    # GNU objdump lists normal and supported delay-import descriptors here.
    if 'pei-x86-64' not in result.stdout:
        raise ValueError('objdump did not identify an x64 PE')
    if re.search(r'Entry d\s+[0-9a-f]*[1-9a-f][0-9a-f]*\s+', result.stdout, re.I):
        raise ValueError('Delay import table requires explicit closure support; refusing partial DLL closure')
    return re.findall(r'DLL Name:\s*([^\s]+)', result.stdout)


def assemble(app, app_pin, engine_pin, receipt_path, dll_dirs, output, *, imports=None, objdump='objdump'):
    app = plain_path(app)
    engine = plain_path(app/'engines/expansion-native')
    verify_checkout(app, app_pin)
    verify_checkout(engine, engine_pin)
    link = git(app, 'ls-tree', app_pin, 'engines/expansion-native').decode().strip()
    if not link.startswith('160000 commit ' + engine_pin + '\t'):
        raise ValueError('App submodule pin does not match requested engine cohort')
    binary = plain_path(engine/'build/native64-windows/pokeemerald-native.exe')
    data = binary.read_bytes()
    receipt = json.loads(plain_path(receipt_path).read_text(encoding='utf-8'))
    integration = git(app, 'show', app_pin + ':engines/expansion.mk')
    verify_receipt(receipt, app_pin, engine_pin, data, integration)
    payload = pinned_sources(app, app_pin)
    if (receipt.get('source_sha256') != {n: sha256(b) for n, b in payload.items()} or
            receipt.get('catalogue_sha256') != sha256(payload['world/expansion_species.json'])):
        raise ValueError('Build receipt does not match pinned source modules or species catalogue')
    candidates = []
    for directory in dll_dirs:
        directory = plain_path(directory)
        if not directory.is_dir():
            raise ValueError('DLL directory does not exist')
        candidates += [plain_path(p) for p in directory.iterdir() if p.suffix.lower() == '.dll']
    dependencies, edges = dll_closure(binary, candidates, imports or (lambda p: pe_imports(p, objdump)))
    payload['game/pokeemerald-native.exe'] = data
    for path in dependencies:
        dll = path.read_bytes()
        check_pe(dll, dll=True)
        if SECRET.search(dll):
            raise ValueError('Secret marker in DLL')
        payload['game/'+path.name] = dll
    if SECRET.search(data):
        raise ValueError('Secret marker in engine')
    payload['Start-Expansion.cmd'] = b'@echo off\r\ncd /d "%~dp0"\r\npy -3 scripts\\windows_expansion_entry.py %*\r\nif errorlevel 1 pause\r\n'
    payload['PRIVATE-HANDOFF.txt'] = (
        'Private local handoff only. Do not upload to GitHub artifacts or releases.\n'
        'Extract the full archive. Requires existing Python 3.11+ with tkinter on Windows x64.\n'
        'Run Start-Expansion.cmd. This is the remote guest UI, not the Linux browser host.\n'
        'The launcher-web directory is matching source, not a prebuilt Windows browser UI.\n'
        'Get a fresh Expansion invitation and TLS fingerprint privately from your host.\n'
        'Never share invitations, saves or profiles. Real Windows device acceptance is still required.\n').encode()
    return write_archive(payload, {'schema': 1, 'engine': 'expansion-native', 'build': receipt,
                         'dll_imports': edges, 'runtime': 'windows-x64-python-source-guest'}, output)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--app-pin', required=True)
    parser.add_argument('--engine-pin', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--dll-dir', type=Path, action='append', required=True)
    parser.add_argument('--objdump', default='objdump')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--private-handoff', action='store_true', required=True,
                        help='explicitly authorize a local-only private archive, never an upload')
    args = parser.parse_args(argv)
    try:
        digest = assemble(args.app, args.app_pin, args.engine_pin, args.receipt, args.dll_dir,
                          args.output, objdump=args.objdump)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(2, 'Expansion handoff failed: ' + str(exc) + '\n')
    print(json.dumps({'archive_sha256': digest, 'distribution': 'manual-private-only',
                      'windows_device_accepted': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
