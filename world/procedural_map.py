"""Deterministic, non-executable map plans for experimental generated worlds.

The module is deliberately pure: no LLM calls, filesystem, game sessions, or
network mutations. Art, game integration and authoritative placement are
separate concerns. Never apply generated grids to a live trainer map without a
server-owned reserved instance and occupancy/event/exit validation.
"""
from collections import deque
import hashlib
import json

ALGORITHM = 'maze-rooms-v1'
SCHEMA = 1
MAX_SIDE = 63
MAX_POINTS = 8
BIOMES = frozenset(('forest', 'cave', 'ruins'))
POINT_KINDS = frozenset(('encounter', 'landmark', 'treasure'))
PLAN_KEYS = frozenset(('schema', 'seed', 'width', 'height', 'rooms', 'room_size', 'biome', 'points'))
RESULT_KEYS = frozenset(('algorithm', 'plan', 'rows', 'spawn', 'exit', 'points', 'sha256'))


class PlanError(ValueError):
    pass


def _integer(value, lo, hi, label):
    if type(value) is not int or not lo <= value <= hi:
        raise PlanError(f'{label} must be an integer from {lo} through {hi}')
    return value


def validate_plan(plan):
    if type(plan) is not dict or set(plan) != PLAN_KEYS:
        raise PlanError('plan has missing or unknown fields')
    if type(plan['schema']) is not int or plan['schema'] != SCHEMA:
        raise PlanError('unsupported plan schema')
    _integer(plan['seed'], 0, (1 << 64) - 1, 'seed')
    for field in ('width', 'height'):
        value = _integer(plan[field], 9, MAX_SIDE, field)
        if value % 2 == 0:
            raise PlanError(f'{field} must be odd')
    _integer(plan['rooms'], 0, 12, 'rooms')
    size = _integer(plan['room_size'], 3, 7, 'room_size')
    if size % 2 == 0:
        raise PlanError('room_size must be odd')
    if type(plan['biome']) is not str or plan['biome'] not in BIOMES:
        raise PlanError('unsupported biome')
    if type(plan['points']) is not list or len(plan['points']) > MAX_POINTS or any(type(x) is not str or x not in POINT_KINDS for x in plan['points']):
        raise PlanError('invalid points')
    # Return an independent value; callers cannot mutate the generator's input.
    return {**plan, 'points': list(plan['points'])}


class _Rng:
    """SHA-256 counter stream with explicitly defined byte order and sampling."""
    def __init__(self, seed):
        self.seed = seed.to_bytes(8, 'big')
        self.counter = 0
    def below(self, n):
        if not 0 < n <= 0xffffffff:
            raise PlanError('invalid random range')
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            block = hashlib.sha256(b'emerald-world:'+ALGORITHM.encode()+b':' + self.seed + self.counter.to_bytes(8, 'big')).digest()
            self.counter += 1
            value = int.from_bytes(block[:8], 'big')
            if value < limit:
                return value % n
    def shuffle(self, items):
        for i in range(len(items)-1, 0, -1):
            j = self.below(i+1)
            items[i], items[j] = items[j], items[i]


def _distances(rows, start):
    width, height = len(rows[0]), len(rows)
    queue = deque([start]); distance = {start: 0}
    while queue:
        x,y = queue.popleft()
        for nx,ny in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if 0 <= nx < width and 0 <= ny < height and rows[ny][nx] == '.' and (nx,ny) not in distance:
                distance[(nx,ny)] = distance[(x,y)] + 1
                queue.append((nx,ny))
    return distance


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')).hexdigest()


def generate(plan):
    """Generate a connected layout and a canonical content hash from a plan."""
    plan = validate_plan(plan)
    w,h = plan['width'], plan['height']
    rng = _Rng(plan['seed'])
    grid = [['#'] * w for _ in range(h)]
    grid[1][1] = '.'
    stack = [(1,1)]
    while stack:
        x,y = stack[-1]
        directions = [(0,-2),(2,0),(0,2),(-2,0)]
        rng.shuffle(directions)
        choices = [(dx,dy) for dx,dy in directions if 1 <= x+dx < w-1 and 1 <= y+dy < h-1 and grid[y+dy][x+dx] == '#']
        if not choices:
            stack.pop(); continue
        dx,dy = choices[0]
        grid[y+dy//2][x+dx//2] = '.'
        grid[y+dy][x+dx] = '.'
        stack.append((x+dx,y+dy))
    centers = [(x,y) for y in range(1,h-1,2) for x in range(1,w-1,2)]
    rng.shuffle(centers)
    radius = plan['room_size']//2
    for cx,cy in centers[:plan['rooms']]:
        for y in range(max(1,cy-radius), min(h-1,cy+radius+1)):
            for x in range(max(1,cx-radius), min(w-1,cx+radius+1)):
                grid[y][x] = '.'
    rows = [''.join(row) for row in grid]
    distances = _distances(rows, (1,1))
    # Stable tie break, independent of dict/hash order.
    finish = min(distances, key=lambda p: (-distances[p], p[1], p[0]))
    candidates = sorted((p for p in distances if p not in ((1,1),finish)), key=lambda p:(p[1],p[0]))
    rng.shuffle(candidates)
    if len(candidates) < len(plan['points']):
        raise PlanError('not enough reachable tiles for points')
    points = [{'kind': kind, 'x': pos[0], 'y': pos[1]} for kind,pos in zip(plan['points'],candidates)]
    result = {'algorithm': ALGORITHM, 'plan': plan, 'rows': rows,
              'spawn': [1,1], 'exit': list(finish), 'points': points}
    return {**result, 'sha256': _digest(result)}


def _validate_geometry(rows, w, h, spawn_value, exit_value, points, expected_kinds=None):
    if type(rows) is not list or len(rows) != h or any(type(row) is not str or len(row) != w or set(row) - {'.','#'} for row in rows):
        raise PlanError('invalid grid')
    if any(rows[0][x] != '#' or rows[-1][x] != '#' for x in range(w)) or any(row[0] != '#' or row[-1] != '#' for row in rows):
        raise PlanError('grid boundary must be closed')
    def position(value):
        if type(value) is not list or len(value) != 2 or any(type(n) is not int for n in value):
            raise PlanError('invalid position')
        x,y=value
        if not (1 <= x < w-1 and 1 <= y < h-1 and rows[y][x] == '.'):
            raise PlanError('position is not on walkable interior')
        return x,y
    spawn, finish = position(spawn_value), position(exit_value)
    if spawn == finish: raise PlanError('spawn and exit must differ')
    distances = _distances(rows,spawn)
    if finish not in distances or len(distances) != sum(row.count('.') for row in rows):
        raise PlanError('grid contains unreachable walkable tiles')
    if type(points) is not list or len(points) > MAX_POINTS:
        raise PlanError('invalid points')
    if expected_kinds is not None and len(points) != len(expected_kinds):
        raise PlanError('point count does not match plan')
    seen={spawn,finish}
    for i,item in enumerate(points):
        if type(item) is not dict or set(item) != {'kind','x','y'} or type(item['kind']) is not str or item['kind'] not in POINT_KINDS:
            raise PlanError('invalid point')
        if expected_kinds is not None and item['kind'] != expected_kinds[i]:
            raise PlanError('point kind does not match plan')
        point=position([item['x'],item['y']])
        if point in seen: raise PlanError('overlapping points')
        seen.add(point)


def validate_generated(result):
    """Reject altered, disconnected, noncanonical or incompatible generated maps."""
    if type(result) is not dict or set(result) != RESULT_KEYS or result.get('algorithm') != ALGORITHM:
        raise PlanError('invalid generated map envelope')
    plan = validate_plan(result['plan'])
    _validate_geometry(result['rows'],plan['width'],plan['height'],result['spawn'],result['exit'],result['points'],plan['points'])
    content={k:v for k,v in result.items() if k != 'sha256'}
    if type(result['sha256']) is not str or result['sha256'] != _digest(content):
        raise PlanError('content hash mismatch')
    if result != generate(plan):
        raise PlanError('map does not match deterministic plan')
    return True


def accept_proposal(proposal):
    """Validate a model- or human-proposed grid as inert data, never code.

    This checks abstract reachability only. It does not establish engine tile
    safety, correct exits, game progression or authorization to deploy a map.
    """
    keys={'schema','biome','rows','spawn','exit','points'}
    if type(proposal) is not dict or set(proposal) != keys:
        raise PlanError('proposal has missing or unknown fields')
    if type(proposal['schema']) is not int or proposal['schema'] != SCHEMA:
        raise PlanError('unsupported proposal schema')
    if type(proposal['biome']) is not str or proposal['biome'] not in BIOMES:
        raise PlanError('unsupported biome')
    rows=proposal['rows']
    if type(rows) is not list or not rows or type(rows[0]) is not str:
        raise PlanError('invalid grid')
    w,h=len(rows[0]),len(rows)
    _integer(w,9,MAX_SIDE,'width');_integer(h,9,MAX_SIDE,'height')
    _validate_geometry(rows,w,h,proposal['spawn'],proposal['exit'],proposal['points'])
    # Copy mutable fields and canonicalize independently of source JSON order.
    content={'schema':SCHEMA,'biome':proposal['biome'],'rows':list(rows),
             'spawn':list(proposal['spawn']),'exit':list(proposal['exit']),
             'points':[dict(item) for item in proposal['points']]}
    return {**content,'sha256':_digest(content)}


def render_preview(result):
    """Render an inspection-only ASCII preview. It is not a playable map."""
    validate_generated(result)
    grid=[list(row) for row in result['rows']]
    for item in result['points']:
        grid[item['y']][item['x']]={'encounter':'E','landmark':'L','treasure':'T'}[item['kind']]
    sx,sy=result['spawn'];ex,ey=result['exit']
    grid[sy][sx]='S';grid[ey][ex]='X'
    return '\n'.join(''.join(row) for row in grid)
