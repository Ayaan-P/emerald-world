#!/usr/bin/env python3
"""Export the selected Expansion build's enabled species from compiler-preprocessed metadata."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def export_catalogue(engine, output, *, compiler=None):
    engine = Path(engine).resolve()
    compiler = compiler or shutil.which('gcc') or shutil.which('cc')
    if not compiler:
        raise RuntimeError('host C compiler is required to preprocess Expansion species metadata')

    constants = (engine / 'include/constants/species.h').read_text()
    raw_enums = dict(re.findall(
        r'^\s*(SPECIES_[A-Z0-9_]+)\s*=\s*([^,]+),?\s*$', constants, re.M))
    enums = {}
    def species_value(name, trail=()):
        if name in enums:
            return enums[name]
        if name in trail or name not in raw_enums:
            raise ValueError(f'unresolvable canonical species ID: {name}')
        raw = raw_enums[name].strip()
        value = int(raw) if raw.isdigit() else species_value(raw, trail + (name,))
        enums[name] = value
        return value
    entries = re.compile(r'^\s*\[SPECIES_([A-Z0-9_]+)\]\s*=', re.M)
    catalog = {}
    family_files = sorted((engine / 'src/data/pokemon/species_info').glob('gen_*_families.h'))
    if not family_files:
        raise ValueError('canonical species family headers not found')
    for path in family_files:
        command = [compiler, '-E', '-P', '-x', 'c', '-I', str(engine / 'include'),
                   '-include', str(engine / 'include/global.h'), str(path)]
        preprocessed = subprocess.run(command, cwd=engine, check=True,
                                      capture_output=True, text=True).stdout
        for name in entries.findall(preprocessed):
            enum = 'SPECIES_' + name
            catalog[name] = species_value(enum)
    if not catalog:
        raise ValueError('compiler preprocessing found no enabled canonical gSpeciesInfo family entries')
    data = {'cohort': 'expansion-native',
            'catalogue_source': 'compiler-preprocessed enabled gSpeciesInfo family definitions',
            'species': dict(sorted(catalog.items(), key=lambda item: item[1]))}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2) + '\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--compiler')
    args = parser.parse_args()
    result = export_catalogue(args.engine, args.output, compiler=args.compiler)
    print(f"Exported {len(result['species'])} compiler-enabled species from {args.engine}")


if __name__ == '__main__':
    main()
