#!/usr/bin/env python3
"""Label canonical engine enums without parsing their numeric expressions.

This does not determine supported Pokémon. The linked engine's gSpeciesInfo
supplies enabled species, Dex membership and battle data at runtime.
"""
import argparse
from pathlib import Path
import re


def export_names(source, destination):
    text = Path(source).read_text()
    names = re.findall(r'^\s*(SPECIES_[A-Z0-9_]+)\s*=', text, flags=re.MULTILINE)
    if not names or len(names) != len(set(names)):
        raise ValueError('expected unique canonical species enum declarations')
    lines = ['/* Generated from the selected engine. Numeric IDs remain engine-owned. */',
             'static const char *const sEngineSpeciesLabels[NUM_SPECIES] = {']
    lines.extend(f'    [{name}] = "{name.removeprefix("SPECIES_")}",' for name in names
                 if name not in ('SPECIES_EGG', 'SPECIES_NONE'))
    lines.append('};\n')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('species_header', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    export_names(args.species_header, args.output)


if __name__ == '__main__':
    main()
