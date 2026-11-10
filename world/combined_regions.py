"""Explicit combined-registry presence cohort. No native save or content authoring."""
import hashlib,json,time
from pathlib import Path
from functools import lru_cache

DIGEST='5e490cc2fce8b420335607661d4c797e6f346088e6fd2478115d71bee3334e92'

@lru_cache(maxsize=1)
def catalog():
    raw=Path(__file__).with_name('combined_map_catalog.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=DIGEST:raise ValueError('Combined registry digest mismatch')
    doc=json.loads(raw)
    if doc['version']!=1:raise ValueError('Unsupported combined registry')
    maps={(m['group'],m['num']):m for m in doc['maps']}
    if len(maps)!=len(doc['maps']):raise ValueError('Duplicate combined maps')
    from .build_catalog import catalog_maps
    for key,base in catalog_maps().items():
        if key not in maps or any(maps[key][f]!=base[f] for f in ('name','width','height','primary_count','secondary_count')):raise ValueError('Combined registry changes baseline geometry')
    return maps


def coords(group,num,x,y):
    if any(type(v) is not int or v<0 for v in (group,num,x,y)):raise ValueError('Invalid combined coordinates')
    m=catalog().get((group,num))
    if not m or x>=m['width'] or y>=m['height']:raise ValueError('Invalid combined coordinates')
    return m


def tile(values):
    group,num,x,y,metatile,collision=values;m=coords(group,num,x,y)
    if type(metatile) is not int or not (0<=metatile<m['primary_count'] or m['secondary_base']<=metatile<m['secondary_base']+m['secondary_count']):raise ValueError('Metatile outside regional allocation')
    if type(collision) is not int or collision not in (0,1):raise ValueError('Invalid collision')


def bind_world(db,enabled):
    if type(enabled) is not bool:raise ValueError('Combined regions must be explicit bool')
    if enabled:catalog()
    # Cohort migrations are deliberately not implicit. Existing unbound worlds remain Hoenn.
    row=db.execute("SELECT 1 FROM sqlite_master WHERE name='world_registry_profile'").fetchone()
    old=db.execute('SELECT profile,digest FROM world_registry_profile').fetchone() if row else None
    expected=('combined',DIGEST) if enabled else ('hoenn','legacy')
    if old and tuple(old)!=expected:raise ValueError('World registry profile mismatch; use the matching authority configuration')
    if not old and enabled and db.execute('SELECT 1 FROM events LIMIT 1').fetchone():raise ValueError('Use a new world directory for the experimental combined cohort')
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS world_registry_profile(profile TEXT PRIMARY KEY,digest TEXT NOT NULL)')
        if not old:db.execute('INSERT INTO world_registry_profile VALUES(?,?)',expected)


def admitted(server,peer):
    if not server.combined_regions:return True
    link=server.link_channels.get(peer.get('id'))
    return bool(link and not link.get('closing') and link.get('presence') is peer and link.get('registry_digest')==DIGEST)


def announce(server,link,raw):
    peer=link['presence']
    if not server.combined_regions or raw not in (('RGC 1 '+DIGEST).encode(),('RGC 2 '+DIGEST).encode()):
        server._error(link,'REGISTRY');server._error(peer,'REGISTRY');return
    link['registry_digest']=DIGEST
    # Version 1 clients do not understand ACK lines; preserve their presence-only path.
    if raw.startswith(b'RGC 2 '):server._queue(link,'RGC OK 2 '+DIGEST+'\n')
    server._queue(peer,server._snapshot(peer))


def pending(server,peer):
    if admitted(server,peer):return False
    if time.monotonic()-peer.get('registry_wait',0)>5:server._error(peer,'REGISTRY_REQUIRED')
    return True
