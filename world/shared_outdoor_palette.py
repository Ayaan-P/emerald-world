"""Compile capability-gated shared outdoor terrain using reviewed native metatiles."""
from .cave_blueprint import proposal_from_blueprint
from .xl_wilds import encode as encode_geometry
MAGIC=b'EWGMAP1A';SIDE=127

def encode(proposal,paint):
    base=encode_geometry(proposal);cells=bytearray(base[8:])
    if type(paint) is not list or len(paint)>64:raise ValueError('paint must be at most 64 rectangles')
    colors={'water':ord('#'),'grass':ord('.'),'tall_grass':ord('t'),'sand':ord('s'),'long_grass':ord('g'),'rock':ord('r')}
    for rect in paint:
        if type(rect) is not dict or set(rect)!={'x','y','width','height','terrain'}:raise ValueError('invalid paint rectangle')
        x,y,w,h=(rect[k] for k in ('x','y','width','height'));kind=rect['terrain']
        if any(type(v) is not int for v in (x,y,w,h)) or x<1 or y<1 or w<1 or h<1 or x+w>126 or y+h>126 or type(kind) is not str or kind not in colors:raise ValueError('invalid paint rectangle')
        for yy in range(y,y+h):cells[yy*SIDE+x:yy*SIDE+x+w]=bytes([colors[kind]])*w
    if any(cells[y*SIDE+x]!=ord('.') for x,y in ((1,1),(125,124),(125,125))):raise ValueError('protected entrance or exit')
    geometry=bytes(ord('#') if c in (ord('#'),ord('r')) else ord('.') for c in cells)
    encode_geometry({'rows':[geometry[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)],'spawn':[1,1],'exit':[125,125]})
    return MAGIC+bytes(cells)


def paint_biome(proposal, biome, seed):
    """Decorate walkable ground deterministically, without changing connectivity.

    This only chooses already supported shared metatiles; it does not generate art.
    """
    import random
    palettes = {
        'meadow': ('.', 't', 'g'),
        'dunes': ('s', 's', '.'),
        'grassland': ('g', 't', '.'),
        'scrub': ('.', 's', 't'),
    }
    if type(biome) is not str or biome not in palettes:
        raise ValueError('unknown biome')
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    cells = bytearray(encode_geometry(proposal)[8:])
    rng = random.Random(seed)
    # Overlapping organic ellipses form large continuous patches, not per-tile noise.
    for _ in range(80):
        cx, cy = rng.randrange(2, 125), rng.randrange(2, 125)
        rx, ry = rng.randrange(4, 17), rng.randrange(3, 13)
        kind = ord(rng.choice(palettes[biome]))
        for y in range(max(1, cy-ry), min(126, cy+ry+1)):
            for x in range(max(1, cx-rx), min(126, cx+rx+1)):
                if (x-cx)**2 * ry**2 + (y-cy)**2 * rx**2 <= rx**2 * ry**2 and cells[y*SIDE+x] == ord('.'):
                    cells[y*SIDE+x] = kind
    for x,y in ((1,1),(125,124),(125,125)):
        cells[y*SIDE+x] = ord('.')
    return MAGIC + bytes(cells)


def add_ponds(blob, seed, count):
    """Add bounded impassable ponds without disconnecting any walkable tile.

    A requested count is a target, not a promise: narrow geometry may not fit.
    Existing terrain and the protected entry and exit remain intact.
    """
    import random
    if not isinstance(blob, bytes) or blob[:8] != MAGIC or len(blob) != 8+SIDE*SIDE:
        raise ValueError('expected shared painted landscape')
    if type(seed) is not int or not 0 <= seed <= 0xffffffff:
        raise ValueError('seed must be an unsigned 32-bit integer')
    if type(count) is not int or not 0 <= count <= 8:
        raise ValueError('pond count must be between 0 and 8')
    cells=bytearray(blob[8:]); rng=random.Random(seed ^ 0x504f4e44); made=0
    protected={(1,1),(125,124),(125,125)}
    for _ in range(count*24):
        if made == count: break
        cx,cy=rng.randrange(5,122),rng.randrange(5,122)
        rx,ry=rng.randrange(2,7),rng.randrange(2,6)
        points=[(x,y) for y in range(max(1,cy-ry),min(126,cy+ry+1))
                for x in range(max(1,cx-rx),min(126,cx+rx+1))
                if (x-cx)**2*ry**2+(y-cy)**2*rx**2 <= rx**2*ry**2]
        if any((x,y) in protected or cells[y*SIDE+x] in (ord('#'),ord('r')) for x,y in points): continue
        trial=cells.copy()
        for x,y in points: trial[y*SIDE+x]=ord('#')
        geometry=bytes(ord('#') if c in (ord('#'),ord('r')) else ord('.') for c in trial)
        try:
            encode_geometry({'rows':[geometry[y*SIDE:(y+1)*SIDE].decode('ascii') for y in range(SIDE)],'spawn':[1,1],'exit':[125,125]})
        except ValueError:
            continue
        cells=trial;made+=1
    return MAGIC+bytes(cells),made

def add_trail(blob, terrain, width):
    """Mark a walkable route through the exact saved terrain, avoiding obstacles.

    Uses existing ordinary grass or sand tiles, not a new road asset. Collision,
    water, rock and the protected entrance/exit never change.
    """
    from collections import deque
    if type(blob) is not bytes or blob[:8] != MAGIC or len(blob) != 8 + SIDE * SIDE:
        raise ValueError('expected shared painted landscape')
    if terrain not in ('grass', 'sand') or type(terrain) is not str:
        raise ValueError('trail terrain must be grass or sand')
    if type(width) is not int or width not in (1, 3):
        raise ValueError('trail width must be 1 or 3')
    cells = bytearray(blob[8:]); start = (1, 1); end = (125, 125)
    blocked = (ord('#'), ord('r'))
    if cells[start[1]*SIDE+start[0]] in blocked or cells[end[1]*SIDE+end[0]] in blocked:
        raise ValueError('trail endpoints are blocked')
    queue = deque([start]); previous = {start: None}
    while queue and end not in previous:
        x, y = queue.popleft()
        for point in ((x+1,y),(x,y+1),(x-1,y),(x,y-1)):
            px, py = point
            if (1 <= px < 126 and 1 <= py < 126 and point not in previous
                    and cells[py*SIDE+px] not in blocked):
                previous[point] = (x,y); queue.append(point)
    if end not in previous:
        raise ValueError('no connected trail to the exit')
    path=[]; point=end
    while point is not None:
        path.append(point); point=previous[point]
    protected={(1,1),(125,124),(125,125)}
    color=ord('.' if terrain=='grass' else 's'); changed=set()
    for x,y in path:
        for dy in range(-(width//2), width//2+1):
            for dx in range(-(width//2), width//2+1):
                px,py=x+dx,y+dy
                if (1 <= px < 126 and 1 <= py < 126 and (px,py) not in protected
                        and cells[py*SIDE+px] not in blocked):
                    if cells[py*SIDE+px] != color: changed.add((px,py))
                    cells[py*SIDE+px]=color
    return MAGIC + bytes(cells), len(path)-1, len(changed)


def compile_document(doc):
    if type(doc) is not dict or set(doc)!={'blueprint','paint'}:raise ValueError('expected blueprint and paint')
    return encode(proposal_from_blueprint(doc['blueprint'],side=SIDE),doc['paint'])

def main(argv=None):
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--replace-output',action='store_true');a=p.parse_args(argv)
    with a.input.open('rb') as f:data=f.read(32769)
    if len(data)>32768:p.error('input too large')
    try:blob=compile_document(json.loads(data.decode('utf-8')))
    except (ValueError,UnicodeError):p.error('invalid XL terrain blueprint')
    from .map_store import write_map
    write_map(a.output,blob,replace=a.replace_output)
    print('Wrote validated offline XL terrain:',a.output)
if __name__=='__main__':main()
