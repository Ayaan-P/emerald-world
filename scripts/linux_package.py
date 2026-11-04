#!/usr/bin/env python3
"""Build a local Linux player archive from trusted, prebuilt release inputs."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tarfile

REPO = Path(__file__).resolve().parents[1]
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?')
WEB_SUFFIXES = {'.html', '.js', '.css', '.svg', '.png', '.ico', '.woff', '.woff2', '.ttf'}


def plain(path):
    """Reject links/special files, including links in ancestor directories."""
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise ValueError(f'Symlink is not a release input/destination: {part}')
        if part.exists():
            info = part.stat()
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise ValueError(f'Special path is not allowed: {part}')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError(f'Hardlinked file is not allowed: {part}')
    return path


def elf_requirements(binary):
    header = binary.read_bytes()[:20]
    if (len(header) < 20 or header[:6] != b'\x7fELF\x02\x01'
            or int.from_bytes(header[18:20], 'little') != 62
            or not os.access(binary, os.X_OK)):
        raise ValueError('Expected an executable Linux x86_64 ELF')
    def readelf(*args):
        return subprocess.run(['readelf', *args, str(binary)], check=True,
                              capture_output=True, text=True).stdout
    libraries = sorted(set(re.findall(r'\(NEEDED\).*?\[(.*?)\]', readelf('-d'))))
    if any(not re.fullmatch(r'[A-Za-z0-9_.+-]+', name) for name in libraries):
        raise ValueError('ELF contains a non-system library path')
    dynamic = readelf('-d')
    if re.search(r'\((?:RPATH|RUNPATH)\)', dynamic):
        raise ValueError('Rebuild native executable without build-machine RPATH/RUNPATH')
    versions = set(re.findall(r'GLIBC_([0-9]+\.[0-9]+(?:\.[0-9]+)?)', readelf('--version-info')))
    versions.add('2.35')  # Oldest supported distro baseline, Ubuntu 22.04.
    return {'python': '>=3.11 (system, standard library only)',
            'native_libraries': libraries,
            'glibc_minimum': max(versions, key=lambda v: tuple(map(int, v.split('.'))), default=None),
            'external_commands': ['bwrap', 'Xephyr'],
            'desktop': 'X11 or XWayland, browser, permitted unprivileged user namespaces',
            'libraries': 'System loader resolves all native dependencies, including SDL2. No libraries bundled.'}


def assemble(binary, web_dist, version, output):
    if not VERSION.fullmatch(version):
        raise ValueError('Version must be MAJOR.MINOR.PATCH with an optional safe prerelease')
    binary, web_dist, output = map(plain, (binary, web_dist, output))
    if output.exists() or output.is_relative_to(web_dist):
        raise ValueError('Output must be fresh and outside the web distribution')
    runtime = elf_requirements(binary)
    frozen = {'build/pokeemerald64': (binary.read_bytes(), 0o755)}
    # Only Git-tracked top-level world Python modules. Never recurse over a
    # checkout, private state, build tree, dependency sysroot or developer venv.
    tracked = subprocess.run(['git', '-C', str(REPO), 'ls-files', '-z', 'world/*.py'],
                             check=True, capture_output=True).stdout.decode().split('\0')
    for name in filter(None, tracked):
        if re.fullmatch(r'world/[A-Za-z0-9_]+\.py', name):
            frozen[name] = (plain(REPO / name).read_bytes(), 0o644)
    # Generated safety catalog is the only non-Python world runtime asset.
    # Runtime catalog reads do not require source data/maps or build tools.
    frozen['world/map_catalog.json'] = (plain(REPO / 'world/map_catalog.json').read_bytes(), 0o644)
    frozen['scripts/__init__.py'] = (b'', 0o644)  # Prevent an installed scripts package shadowing this helper.
    for source, name in [('linux_client.py', 'scripts/linux_client.py'),
                         ('linux_bundle_entry.py', 'entry.py'),
                         ('linux_bundle_install.py', 'install.py')]:
        frozen[name] = (plain(REPO / 'scripts' / source).read_bytes(), 0o644)
    if not (web_dist / 'index.html').is_file():
        raise ValueError('Prebuilt frontend index.html is required')
    for path in sorted(web_dist.rglob('*')):
        plain(path)
        if path.is_dir():
            continue
        relative = path.relative_to(web_dist)
        if (path.suffix not in WEB_SUFFIXES or
                any(not re.fullmatch(r'[A-Za-z0-9_+.-]+', p) or p.startswith('.') for p in relative.parts)):
            raise ValueError(f'Unapproved frontend artifact: {relative}')
        frozen['launcher-web/dist/' + relative.as_posix()] = (path.read_bytes(), 0o644)
    from html.parser import HTMLParser
    from urllib.parse import urlsplit, unquote
    class IndexAssets(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if key not in ('src', 'href') or value is None:
                    continue
                url = urlsplit(value)
                if url.scheme or url.netloc or url.query or url.fragment:
                    raise ValueError('Frontend index must reference local release assets only')
                name = unquote(url.path).lstrip('/')
                if not name or '..' in Path(name).parts or 'launcher-web/dist/' + name not in frozen:
                    raise ValueError(f'Missing frontend asset referenced by index: {value}')
    IndexAssets().feed(frozen['launcher-web/dist/index.html'][0].decode('utf-8'))
    frozen['INSTALL.txt'] = (
        b'Emerald World Linux x86_64\nSystem Python 3.11+ with the standard library is required.\n'
        b'Native libraries are supplied by your distribution. See manifest.json for ELF requirements.\n'
        b'Install bubblewrap, Xephyr, SDL2 and a browser using your distribution package manager.\n'
        b'X11 or XWayland and unprivileged user namespaces are required. No npm or pip needed.\n'
        b'Choose an installed Python 3.11+ as PYTHON below. Python 3.10 is not sufficient.\n'
        b'  "$PYTHON" -I install.py --check\n'
        b'  "$PYTHON" -I entry.py --check\n'
        b'  "$PYTHON" -I install.py\n'
        b'Open Emerald World from the application menu, or run "$PYTHON" -I entry.py.\n'
        b'Rerun install.py from a new extracted version to update. Existing worlds and saves are never copied or removed.\n'
        b'The installer creates ~/.local/share/emerald-world-player and a separate player desktop shortcut.\n'
        b'It never changes ~/.local/bin/emerald-world or existing source-checkout launchers.\n'
        b'Only package trusted clean release builds. Checksums are not signatures.\n', 0o644)
    manifest = {'format': 1, 'version': version, 'architecture': 'x86_64', 'runtime': runtime,
                'files': {name: {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode}
                          for name, (data, mode) in sorted(frozen.items())}}
    frozen['manifest.json'] = ((json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode(), 0o644)
    output.mkdir(parents=True)
    basename = f'EmeraldWorld-{version}-linux-x86_64'
    archive = output / (basename + '.tar.gz')
    with archive.open('xb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode='w') as stream:
            for name, (data, mode) in sorted(frozen.items()):
                info = tarfile.TarInfo(basename + '/' + name)
                info.size, info.mode, info.mtime = len(data), mode, 0
                stream.addfile(info, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + '.sha256')).write_text(checksum + '  ' + archive.name + '\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--web-dist', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(assemble(args.binary, args.web_dist, args.version, args.output))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Package not created: {exc}\n')


if __name__ == '__main__':
    main()
