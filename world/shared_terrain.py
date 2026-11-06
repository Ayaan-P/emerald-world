"""Canonical bounded durable terrain overlay and connected geometry."""
from collections import deque
MAX_TILES=64

def _npc(cave):
    return {(cave.cast[2+61*i],cave.cast[3+61*i]) for i in range(cave.cast[0])}

def validate(cave,payload):
    if type(payload) is not bytes or not payload or payload[0]>MAX_TILES or len(payload)!=1+3*payload[0]:raise ValueError('invalid shared terrain')
    result={};last=None;npcs=_npc(cave)
    for i in range(payload[0]):
        x,y,kind=payload[1+3*i:4+3*i]
        if kind>2 or not 0<x<62 or not 0<y<62 or (x,y) in npcs or (x,y) in ((1,1),(61,60),(61,61)) or (last is not None and (x,y)<=last):raise ValueError('invalid shared terrain')
        result[(x,y)]=kind;last=(x,y)
    floor={(x,y) for y,row in enumerate(cave._rows) for x,v in enumerate(row) if v==ord('.') and (x,y) not in npcs}
    for point,kind in result.items():
        if kind==2:floor.discard(point)
        else:floor.add(point)
    if any(not any((x+dx,y+dy) in floor for dx,dy in ((0,-1),(1,0),(0,1),(-1,0))) for x,y in npcs):raise ValueError('shared terrain isolates a character')
    seen={(1,1)};q=deque(seen)
    while q:
        x,y=q.popleft()
        for point in ((x,y-1),(x+1,y),(x,y+1),(x-1,y)):
            if point in floor and point not in seen:seen.add(point);q.append(point)
    if len(seen)!=len(floor):raise ValueError('shared terrain disconnects the map')
    return result

def encode(cave,tiles):
    if type(tiles) is not dict or len(tiles)>MAX_TILES:raise ValueError('invalid shared terrain')
    payload=bytearray([len(tiles)])
    for (x,y),kind in sorted(tiles.items()):payload.extend((x,y,kind))
    result=bytes(payload);validate(cave,result);return result

def needs_geometry(cave,payload):
    tiles=validate(cave,payload)
    return any(kind==2 or not cave.walkable(x,y) for (x,y),kind in tiles.items())

def walkable(cave,payload,x,y):
    if type(x) is not int or type(y) is not int or not 0<=x<63 or not 0<=y<63 or (x,y) in _npc(cave):return False
    tiles=validate(cave,payload);kind=tiles.get((x,y))
    return cave.walkable(x,y) if kind is None else kind!=2

def project(cave,payload):
    tiles=validate(cave,payload);npcs=_npc(cave)
    floor={(x,y) for y,row in enumerate(cave._rows) for x,v in enumerate(row) if v==ord('.') and (x,y) not in npcs}
    for point,kind in tiles.items():
        if kind==2:floor.discard(point)
        else:floor.add(point)
    return frozenset(floor)
