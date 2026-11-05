#!/usr/bin/env python3
"""Turn an inert cave proposal into a validated offline native template.

Input is a JSON object containing exactly ``rows``, ``spawn`` and ``exit``.
Rows are 31 strings of 31 '.' (floor) or '#' (wall) characters. This tool does
not call a model or run content as code. It only replaces an existing file with an explicit --replace option.
"""
import argparse
from collections import deque
import json
import os
from pathlib import Path
import tempfile

SIDE = 31
MAGIC = b'EWGMAP01'
MAGIC_PROFILE = b'EWGMAP02'
ENCOUNTER_PROFILES = {'granite': 0, 'meteor': 1, 'ice': 2, 'victory': 3}
MAX_INPUT = 16384


def encode(proposal, *, encounter_profile=None):
    if type(proposal) is not dict or set(proposal) != {'rows', 'spawn', 'exit'}:
        raise ValueError('expected only rows, spawn and exit')
    if proposal['spawn'] != [1, 1] or proposal['exit'] != [29, 29]:
        raise ValueError('spawn must be [1,1] and exit must be [29,29]')
    # bool is a subclass of int, so require exact integer types.
    if any(type(n) is not int for key in ('spawn', 'exit') for n in proposal[key]):
        raise ValueError('coordinates must be integers')
    rows = proposal['rows']
    if type(rows) is not list or len(rows) != SIDE or any(
        type(row) is not str or len(row) != SIDE or set(row) - {'.', '#'} for row in rows
    ):
        raise ValueError('rows must be 31 strings of 31 floor or wall characters')
    if any(c != '#' for c in rows[0] + rows[-1]) or any(row[0] != '#' or row[-1] != '#' for row in rows):
        raise ValueError('perimeter must be closed')
    if any(rows[y][x] != '.' for x, y in ((1, 1), (29, 28), (29, 29))):
        raise ValueError('spawn, exit and exit approach must be floor')
    queue = deque([(1, 1)])
    visited = {(1, 1)}
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if 0 <= nx < SIDE and 0 <= ny < SIDE and rows[ny][nx] == '.' and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
    if len(visited) != sum(row.count('.') for row in rows):
        raise ValueError('all floor tiles must be connected to spawn')
    cells = ''.join(rows).encode('ascii')
    if encounter_profile is None:
        return MAGIC + cells
    if type(encounter_profile) is not str or encounter_profile not in ENCOUNTER_PROFILES:
        raise ValueError('invalid offline encounter profile')
    return MAGIC_PROFILE + bytes([ENCOUNTER_PROFILES[encounter_profile]]) + cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proposal', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--encounter-profile', choices=tuple(ENCOUNTER_PROFILES), help='opt in to a versioned offline encounter preset')
    parser.add_argument('--replace', action='store_true', help='atomically replace the output, if it already exists')
    args = parser.parse_args()
    try:
        with args.proposal.open('rb') as stream:
            raw = stream.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError('proposal exceeds size limit')
        data = encode(json.loads(raw), encounter_profile=args.encounter_profile)
        if args.proposal.resolve() == args.output.resolve():
            raise ValueError('proposal and output must be different files')
        if args.output.exists() and os.path.samefile(args.proposal, args.output):
            raise ValueError('proposal and output must not be the same file')
        if args.replace:
            # The temporary file is in the destination directory so a client
            # observes either the old complete template or the new one.
            fd, temp_path = tempfile.mkstemp(prefix='.generated-cave-', dir=args.output.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, args.output)
            finally:
                if os.path.exists(temp_path): os.unlink(temp_path)
        else:
            with args.output.open('xb') as stream:
                stream.write(data)
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, f'Cannot export cave: {error}\n')


if __name__ == '__main__':
    main()
