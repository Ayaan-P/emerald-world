"""Prepare a local-only portable bundle. Never upload the result automatically."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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


def assemble(launcher, binary, dependencies, output):
    launcher, binary, output = Path(launcher), Path(binary), Path(output)
    sources = list(launcher.rglob('*')) + [binary, *dependencies]
    for path in sources:
        if path.is_symlink():
            raise ValueError('Symlinks are not allowed in the package')
        if path.suffix.lower() in ('.sav', '.gba', '.ini', '.conf', '.pem', '.key'):
            raise ValueError(f'Private or game-state file forbidden: {path.suffix}')
    if not (launcher / 'EmeraldWorld.exe').is_file():
        raise ValueError('Missing EmeraldWorld.exe')
    for path in [launcher / 'EmeraldWorld.exe', binary, *dependencies]:
        with path.open('rb') as stream:
            if stream.read(2) != b'MZ':
                raise ValueError('Expected a Windows PE file')
    output.mkdir(parents=True, exist_ok=True)
    stage = output / 'EmeraldWorld'
    if stage.exists():
        raise ValueError('Package destination must be fresh')
    shutil.copytree(launcher, stage)
    game = stage / 'game'
    game.mkdir()
    shutil.copy2(binary, game / 'pokeemerald64.exe')
    for path in dependencies:
        shutil.copy2(path, game / path.name)
    (stage / 'INSTALL.txt').write_text(
        'Extract the entire EmeraldWorld folder before opening EmeraldWorld.exe.\n'
        'Keep game and _internal beside EmeraldWorld.exe. No Python or WSL is needed.\n'
        'Use the world address, certificate fingerprint and invite supplied by your host.\n'
        'Never send your invite or save to someone else. Your save stays on this PC.\n'
        'This is a player client, not a world host or GM console.\n'
        'The prepared ZIP is not a release and has not been authorized for upload.\n', encoding='utf-8')
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    hashes = {p.relative_to(output).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    archive = output / 'EmeraldWorld-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, path.relative_to(output).as_posix())
    (output / 'checksums.json').write_text(json.dumps({
        'files': hashes, 'zip_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'distribution_authorized': False}, indent=2) + '\n', encoding='utf-8')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--dll-dir', type=Path, action='append', required=True)
    parser.add_argument('--objdump', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    dependencies = collect_dependencies(args.binary, args.dll_dir,
        lambda path: pe_imports(path, args.objdump), system_dll)
    assemble(args.launcher, args.binary, dependencies, args.output)
    print('Portable package prepared locally. Distribution is not authorized.')


if __name__ == '__main__':
    main()
