#!/usr/bin/env python3
"""Report FireRed map-script variable aliases and Emerald zero flag placeholders.

Read-only source audit, not proof of runtime behavior or script reachability.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re

# The optional region wrappers keep these values in the default cohort. This
# audit still reports default-source conflicts, not enabled-cohort reachability.
DIRECT_VAR = re.compile(r'^\s*#define\s+(VAR_[A-Z0-9_]+)\s+(?:KANTO_SCENE_VAR\()?(0x[0-9A-Fa-f]+)\b', re.M)
ZERO_FLAG = re.compile(r'^\s*#define\s+(FLAG_[A-Z0-9_]+)\s+(?:0(?:\s|$)|KANTO_SCENE_FLAG\()', re.M)
USED = re.compile(r'\b(?:VAR|FLAG)_[A-Z0-9_]+\b')


def audit(engine):
    engine = Path(engine)
    maps = sorted((engine / 'data/maps').glob('*_Frlg/scripts.inc'))
    if not maps:
        raise ValueError('No FireRed scripts found in the supplied engine source')
    used = set()
    for path in maps:
        text = re.sub(r'/\*.*?\*/|//[^\n]*|@[^\n]*', '', path.read_text(), flags=re.S)
        used.update(USED.findall(text))
    constants = engine / 'include/constants'
    emerald_vars = DIRECT_VAR.findall((constants / 'vars.h').read_text())
    firered_vars = dict(DIRECT_VAR.findall((constants / 'vars_frlg.h').read_text()))
    by_value = defaultdict(list)
    for name, value in emerald_vars:
        if not name.startswith('VAR_UNUSED_'):
            by_value[int(value, 16)].append(name)
    collisions = []
    for name in sorted(used):
        if name in firered_vars:
            value = int(firered_vars[name], 16)
            matches = sorted(n for n in by_value[value] if n != name)
            if matches:
                collisions.append({'firered': name, 'value': f'0x{value:04X}', 'emerald': matches})
    placeholders = sorted(used.intersection(ZERO_FLAG.findall((constants / 'flags.h').read_text())))
    return {'scripts_scanned': len(maps), 'direct_variable_collisions': collisions,
            'emerald_zero_flag_placeholders': placeholders}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(audit(args.engine), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
