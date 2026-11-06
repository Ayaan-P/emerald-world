"""Canonical bounded durable overlay for a generated outdoor area."""
MAX_TILES=64

def validate(cave,payload):
    if type(payload) is not bytes or not payload or payload[0]>MAX_TILES or len(payload)!=1+3*payload[0]:raise ValueError('invalid shared terrain')
    result={};last=None
    for i in range(payload[0]):
        x,y,kind=payload[1+3*i:4+3*i]
        if kind>1 or not cave.walkable(x,y) or (x,y) in ((1,1),(61,60),(61,61)) or (last is not None and (x,y)<=last):raise ValueError('invalid shared terrain')
        result[(x,y)]=kind;last=(x,y)
    return result

def encode(cave,tiles):
    if type(tiles) is not dict or len(tiles)>MAX_TILES:raise ValueError('invalid shared terrain')
    payload=bytearray([len(tiles)])
    for (x,y),kind in sorted(tiles.items()):payload.extend((x,y,kind))
    result=bytes(payload);validate(cave,result);return result
