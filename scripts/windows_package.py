"""Prepare a local-only portable bundle. Never upload the result automatically."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import io
import stat
import subprocess
import zipfile


def collect_dependencies(binary, search_dirs, imports, is_system):
    index = {}
    for directory in search_dirs:
        for path in Path(directory).glob('*.dll'):
            index.setdefault(path.name.lower(), path)
    found = {}
    pending = [Path(binary)]
    while pending:
        for name in imports(pending.pop()):
            key = name.lower()
            if key in found:
                continue
            if key in index:
                found[key] = index[key]
                pending.append(index[key])
            elif not is_system(name):
                raise ValueError(f'Unresolved non-system DLL: {name}')
    return sorted(found.values(), key=lambda p: p.name.lower())


def pe_imports(path, objdump):
    result = subprocess.run([str(objdump), '-p', str(path)], check=True,
                            capture_output=True, text=True, timeout=30)
    return re.findall(r'DLL Name:\s*([^\s]+)', result.stdout)


def system_dll(name):
    if Path(name).name != name:
        return False
    return (name.lower().startswith(('api-ms-win-', 'ext-ms-win-')) or
            (Path(os.environ['SystemRoot']) / 'System32' / name).is_file())


# Bounded PyInstaller layout. Unknown data requires an explicit policy change,
# not an auto-discovered manifest from the potentially contaminated input tree.
_TCL_SUFFIXES = {'.tcl', '.tm', '.msg', '.enc'}
_STDLIB_MODULES = frozenset('''abc codecs collections copyreg encodings enum
functools genericpath heapq io keyword linecache locale ntpath operator os
posixpath re reprlib sre_compile sre_constants sre_parse stat traceback
traceback types warnings weakref _collections_abc _weakrefset'''.split())
_SECRET = re.compile(
    rb'-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY|OPENSSH PRIVATE KEY)-----|'
    rb'["\'](?:token|invite|invite_token|api_key|password|secret)["\']\s*:|'
    rb'(?im:^\s*(?:set\s+)?(?:invite[_-]?token|api[_-]?key|access[_-]?token|'
    rb'auth[_-]?token|password|secret)\s*(?:=|\s)\s*\S+)')


def check_content(data):
    if (_SECRET.search(data) or data.lstrip().startswith((b'{', b'[', b'SQLite format 3', b'\x80'))):
        raise ValueError('Private or serialized data in runtime artifact')


def validate_runtime(path, relative, data):
    name = relative.as_posix()
    parts = relative.parts
    native = (len(parts) == 2 and parts[0] == '_internal'
              and re.fullmatch(r'[A-Za-z0-9_+.-]+\.(?:dll|pyd)', parts[1], re.I))
    if name == 'EmeraldWorld.exe' or native:
        if not data.startswith(b'MZ'):
            raise ValueError('Expected a Windows PE file')
        # Not authenticity validation: trusted build provenance is prerequisite.
        if _SECRET.search(data):
            raise ValueError('Private data in native artifact')
        return
    if name == '_internal/base_library.zip':
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                seen = set()
                for entry in archive.infolist():
                    member = Path(entry.filename)
                    if (entry.filename in seen or entry.is_dir() or
                            entry.file_size > 16 * 1024 * 1024 or
                            not re.fullmatch(r'[A-Za-z0-9_/]+\.pyc', entry.filename) or
                            member.parts[0].removesuffix('.pyc') not in _STDLIB_MODULES):
                        raise ValueError('Unapproved stdlib archive member')
                    seen.add(entry.filename)
                    if _SECRET.search(archive.read(entry)):
                        raise ValueError('Private data in stdlib artifact')
        except zipfile.BadZipFile as error:
            raise ValueError('Invalid stdlib archive') from error
        return
    tcl = (len(parts) >= 3 and parts[:2] in
           (('_internal', '_tcl_data'), ('_internal', '_tk_data'), ('_internal', 'tcl8')))
    text_data = name in ('_internal/_tk_data/images/README',
                         '_internal/_tk_data/license.terms', '_internal/_tcl_data/license.terms')
    if text_data or (tcl and (path.suffix.lower() in _TCL_SUFFIXES or
                             path.name in ('tclIndex', 'encoding.map'))):
        check_content(data)
        if b'\x00' in data:
            raise ValueError('Binary data in Tcl runtime')
        return
    if (len(parts) == 4 and parts[:3] == ('_internal', '_tk_data', 'images')
            and re.fullmatch(r'(?:logo(?:\d+|Large|Med|Small)|pwrdLogo\d+|tai-ku)\.gif', path.name)
            and data.startswith((b'GIF87a', b'GIF89a'))):
        check_content(data)
        return
    if (name in ('_internal/_tk_data/images/logo.eps', '_internal/_tk_data/images/pwrdLogo.eps')
            and data.startswith(b'%!PS')):
        check_content(data)
        return
    if name == '_internal/certifi/cacert.pem':
        import ssl
        check_content(data)
        text = data.decode('ascii')
        certificates = re.findall(r'-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+?-----END CERTIFICATE-----', text)
        remainder = text
        for certificate in certificates:
            ssl.PEM_cert_to_DER_cert(certificate)
            remainder = remainder.replace(certificate, '', 1)
        if not certificates or any(line.strip() and not line.startswith('#') for line in remainder.splitlines()):
            raise ValueError('Only public CA certificates are allowed')
        try:
            ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT).load_verify_locations(cadata='\n'.join(certificates))
        except ssl.SSLError as error:
            raise ValueError('Invalid public CA certificate') from error
        return
    raise ValueError(f'Unapproved launcher artifact: {relative}')


def checked_path(path):
    # lstat every component before walking or opening it, including roots and
    # ancestors. Junctions and other Windows reparse points are not plain dirs.
    path = Path(os.path.abspath(path))
    for component in [*reversed(path.parents), path]:
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400 or
                not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or
                (stat.S_ISREG(info.st_mode) and info.st_nlink != 1)):
            raise ValueError('Linked, reparse or special paths are forbidden')
    return path


def launcher_files(directory):
    for path in sorted(directory.iterdir()):
        checked_path(path)
        relative = path.relative_to(directory)
        if any(not re.fullmatch(r'[A-Za-z0-9_+.-]+', part) or part.startswith('.') for part in relative.parts):
            raise ValueError('Unapproved runtime path')
        if path.is_dir():
            yield from launcher_files(path)
        else:
            yield path


def assemble(launcher, binary, dependencies, output, *, distribution_authorized=False):
    launcher, binary, output = map(checked_path, (launcher, binary, output))
    dependencies = [checked_path(path) for path in dependencies]
    if output.exists() or output.is_relative_to(launcher):
        raise ValueError('Package destination must be fresh and outside launcher')
    # Freeze validated bytes before creating anything. Never copytree/re-walk
    # unvalidated inputs after validation (including newly introduced files).
    frozen = {}
    names = set()
    for path in launcher_files(launcher):
        relative = path.relative_to(launcher)
        key = relative.as_posix().lower()
        if key in names:
            raise ValueError('Case-colliding launcher paths')
        names.add(key)
        data = path.read_bytes()
        validate_runtime(path, relative, data)
        frozen[relative.as_posix()] = data
    if 'EmeraldWorld.exe' not in frozen:
        raise ValueError('Missing EmeraldWorld.exe')
    for path, name in [(binary, 'game/pokeemerald64.exe'),
                       *((p, 'game/' + p.name) for p in dependencies)]:
        if path != binary and not re.fullmatch(r'[A-Za-z0-9_+.-]+\.dll', path.name, re.I):
            raise ValueError('Only DLL dependencies are allowed')
        if name.lower() in names:
            raise ValueError('Case-colliding package paths')
        names.add(name.lower())
        data = path.read_bytes()
        if not data.startswith(b'MZ') or _SECRET.search(data):
            raise ValueError('Expected a Windows PE file without private data')
        frozen[name] = data
    output.mkdir(parents=True, exist_ok=False)
    stage = output / 'EmeraldWorld'
    for name, data in frozen.items():
        destination = stage / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    (stage / 'INSTALL.txt').write_text(
        'Extract the entire EmeraldWorld folder before opening EmeraldWorld.exe.\n'
        'Keep game and _internal beside EmeraldWorld.exe. No Python or WSL is needed.\n'
        'Use the world address, certificate fingerprint and invite supplied by your host.\n'
        'Never send your invite or save to someone else. Your save stays on this PC.\n'
        'This is a player client, not a world host or GM console.\n'
        + ('Private Windows test build. Share only with invited testers.\n'
           if distribution_authorized else
           'The prepared ZIP is not a release and has not been authorized for upload.\n'), encoding='utf-8')
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    archive = output / 'EmeraldWorld-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(output).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            z.writestr(info, path.read_bytes())
    (output / 'checksums.json').write_text(json.dumps({
        'files': hashes, 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'distribution_authorized': distribution_authorized}, indent=2) + '\n', encoding='utf-8')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--dll-dir', type=Path, action='append', required=True)
    parser.add_argument('--objdump', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--authorize-private-distribution', action='store_true',
                        help='Explicit operator permission for a private Windows test package')
    args = parser.parse_args()
    dependencies = collect_dependencies(args.binary, args.dll_dir,
        lambda path: pe_imports(path, args.objdump), system_dll)
    assemble(args.launcher, args.binary, dependencies, args.output,
             distribution_authorized=args.authorize_private_distribution)
    print('Private Windows package prepared.' if args.authorize_private_distribution else
          'Portable package prepared locally. Distribution is not authorized.')


if __name__ == '__main__':
    main()
