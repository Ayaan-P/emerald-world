"""Add connected frontier courtyards without erasing existing XL geography.

Walls use the existing impassable outdoor palette, not new building artwork.
Construction is owner-operated and applies only to the empty shared XL slot.
"""
import argparse
from collections import deque
import json
from pathlib import Path

from .shared_cave import SharedCave
from .xl_wilds import encode


def compile_outpost(blob, plan):
    cave = SharedCave(blob)
    if cave.version != 16:
        raise ValueError('construction requires a plain XL outdoor map')
    if type(plan) is not dict or set(plan) != {'x', 'y', 'width', 'height', 'gate', 'reservations'}:
        raise ValueError('expected x, y, width, height, gate and reservations')
    x, y, width, height = (plan[key] for key in ('x', 'y', 'width', 'height'))
    if (any(type(v) is not int for v in (x, y, width, height))
            or not 5 <= width <= 15 or not 5 <= height <= 15
            or x < 3 or y < 3 or x + width > 124 or y + height > 124):
        raise ValueError('outpost must be 5..15 tiles wide and high, inside 3..123')
    if type(plan['gate']) is not str or plan['gate'] not in ('north', 'east', 'south', 'west'):
        raise ValueError('invalid gate direction')
    reservations = plan['reservations']
    if type(reservations) is not list or len(reservations) > 32:
        raise ValueError('use at most 32 reserved rectangles')
    protected = set()
    for rect in reservations:
        if type(rect) is not list or len(rect) != 4 or any(type(v) is not int for v in rect):
            raise ValueError('reservation must be [x,y,width,height]')
        rx, ry, rw, rh = rect
        if min(rx, ry, rw, rh) < 1 or rx + rw > 126 or ry + rh > 126:
            raise ValueError('invalid reserved rectangle')
        protected.update((xx, yy) for xx in range(rx, rx + rw) for yy in range(ry, ry + rh))
    old = {(xx, yy) for yy, row in enumerate(cave._rows) for xx, cell in enumerate(row) if cell == ord('.')}
    footprint = {(xx, yy) for xx in range(x, x + width) for yy in range(y, y + height)}
    # A one-tile rock buffer keeps the courtyard walls intact and makes additions
    # reject overlap with old trails, previously built sites and native endpoints.
    buffer = {(xx, yy) for xx in range(x - 1, x + width + 1) for yy in range(y - 1, y + height + 1)}
    if buffer & old or footprint & protected:
        raise ValueError('outpost overlaps existing routes or reserved terrain')
    gates = {'north': ((x + width // 2, y), (0, -1)),
             'east': ((x + width - 1, y + height // 2), (1, 0)),
             'south': ((x + width // 2, y + height - 1), (0, 1)),
             'west': ((x, y + height // 2), (-1, 0))}
    gate, direction = gates[plan['gate']]
    approach = (gate[0] + direction[0], gate[1] + direction[1])
    forbidden = (buffer - {approach}) | protected
    queue = deque([approach]); previous = {approach: None}; target = None
    if approach in protected:
        raise ValueError('gate approach is reserved')
    while queue:
        point = queue.popleft()
        if point in old:
            target = point
            break
        xx, yy = point
        for step in ((xx, yy - 1), (xx + 1, yy), (xx, yy + 1), (xx - 1, yy)):
            if (1 <= step[0] <= 125 and 1 <= step[1] <= 125
                    and step not in forbidden and step not in previous):
                previous[step] = point; queue.append(step)
    if target is None:
        raise ValueError('reserved terrain separates the outpost from existing routes')
    trail = []
    while target is not None:
        trail.append(target); target = previous[target]
    trail.reverse()
    if len(trail) > 128:
        raise ValueError('outpost needs more than 128 access trail tiles')
    courtyard = {(xx, yy) for xx in range(x + 1, x + width - 1) for yy in range(y + 1, y + height - 1)}
    additions = courtyard | {gate} | set(trail)
    rows = [bytearray(row) for row in cave._rows]
    for xx, yy in additions:
        rows[yy][xx] = ord('.')
    result = encode(dict(rows=[row.decode('ascii') for row in rows], spawn=[1, 1], exit=[125, 125]))
    return result, dict(previous_revision=cave.identity, revision=SharedCave(result).identity,
                       footprint=[x, y, width, height], gate=list(gate),
                       access_trail=[list(p) for p in trail], added_walkable_tiles=len(additions - old),
                       preserved_walkable_tiles=len(old))


def construct(server, request):
    """Owner admin operation. Validation and publication share the authority lock."""
    required = {'command', 'plan', 'label', 'previous_revision', 'expected_world_id', 'expected_sequence'}
    if set(request) != required:
        raise ValueError('invalid frontier construction request')
    with server.lock:
        cave = server.shared_cave
        if not server.archive_generated_areas or cave is None or cave.identity != request['previous_revision']:
            raise ValueError('active archived area changed; inspect before construction')
        if any(obj.get('region_revision') == cave.identity for obj in server.objects):
            raise ValueError('move or retire placed characters before changing their exact map revision')
        stored = server.db.execute('SELECT template FROM generated_cave WHERE singleton=1').fetchone()
        if stored is None or SharedCave(stored[0]).identity != cave.identity:
            raise ValueError('active area is not durably published')
        blob, report = compile_outpost(stored[0], request['plan'])
        revision = server._replace_cave(blob, label=request['label'], previous_revision=cave.identity,
            expected_world_id=request['expected_world_id'], expected_sequence=request['expected_sequence'],
            history_evidence=[])
        return dict(ok=True, revision=revision, place_id=server.memory.place(revision),
                    persistent=True, construction=report)


def main(argv=None):
    from .client import admin_request
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--admin-socket', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--apply', action='store_true', help='Commit construction; otherwise preview only')
    args = parser.parse_args(argv)
    def call(request):
        result = admin_request('', request, admin_path=args.admin_socket)
        if type(result) is not dict or result.get('ok') is not True:
            raise ValueError(result.get('error', 'authority rejected request') if type(result) is dict else 'invalid authority reply')
        return result
    try:
        with args.plan.open('rb') as stream:
            data = stream.read(16385)
        if len(data) > 16384:
            raise ValueError('construction plan too large')
        plan = json.loads(data)
        inspection = call(dict(command='inspect'))
        memory = inspection['world_memory']; active = memory['active_area']
        saved = call(dict(command='inspect_saved_place', revision=active['revision']))
        if saved['template_version'] != 16:
            raise ValueError('construction requires a plain XL outdoor map')
        if saved['world_id'] != memory['world_id'] or saved['captured_at_seq'] != memory['through']:
            raise ValueError('world changed during inspection')
        blob = encode(dict(rows=saved['rows'], spawn=[1, 1], exit=[125, 125]))
        _, report = compile_outpost(blob, plan)
        result = dict(ok=True, applied=False, construction=report)
        if args.apply:
            result = call(dict(command='construct_outpost', plan=plan, label=args.label,
                previous_revision=active['revision'], expected_world_id=memory['world_id'],
                expected_sequence=memory['through']))
            result['applied'] = True
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
