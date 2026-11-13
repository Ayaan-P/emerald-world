"""Publication-bound Secret Base presence. No import, teleport, party or save writes.
The native room digest covers exactly the first 46 bytes of the existing snapshot:
location, owner identity, furniture and positions. It excludes recorded party.
This is matching client-reported local content, not remote attestation.
"""
import hashlib
import re
import time
from .base_neighborhood import setup

def interior(state):
    return bool(state and tuple(state[:2])[0] == 25 and 0 <= state[1] < 24)

def room_map(base_id):
    group,slot=divmod(base_id,10)
    if not 0 <= group < 24 or not 1 <= slot <= (4 if group in (16,17,20) else 3):
        return None
    return (25,(group%4)*6+group//4)

def digest(payload):
    return hashlib.sha256(bytes.fromhex(payload)[:46]).hexdigest()

def _match(server, value, state):
    setup(server.db)
    rows=[(ident,payload) for ident,payload in server.db.execute('SELECT id,payload FROM base_neighborhood')
          if re.fullmatch('[0-9a-f]{308}',payload) and digest(payload)==value and room_map(int(payload[:2],16))==tuple(state[:2])]
    # Copied owner identities published by multiple accounts are ambiguous, never guessed.
    return rows[0][0] if len(rows)==1 else None

def scope(server,peer):
    state=peer.get('state');lease=peer.get('base_room');now=time.monotonic()
    if not interior(state) or not lease or not 0 <= now-lease['at'] < 3:
        return None
    if server.link_channels.get(peer['id']) is not lease['channel']:
        return None
    if not 0 <= now-peer.get('state_time',0) < 3 or tuple(state[:2])!=lease['map']:
        return None
    if _match(server,lease['digest'],state)!=lease['id']:
        return None
    return 'base:'+lease['id']+':'+lease['digest']

def handle(server,conn,raw):
    seq=0
    try:
        f=raw.decode('ascii').split(' ')
        if len(f)<3 or f[:2] not in (['B','ROOM'],['B','LEAVE']) or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
        seq=int(f[2]);peer=conn.get('presence')
        if not 0<seq<=2**32-1 or seq<=conn.get('neighborhood_seq',0):raise ValueError()
        if server.link_channels.get(conn['id']) is not conn or server.peers.get(conn['id']) is not peer:raise ValueError()
        conn['neighborhood_seq']=seq
        peer.pop('base_room',None)
        if f[1]=='LEAVE' and len(f)==3:
            server._schedule_presence(time.monotonic());return f'B ROOM {seq} 0\n'
        state=peer.get('state');now=time.monotonic()
        if len(f)!=4 or not re.fullmatch('[0-9a-f]{64}',f[3]) or not interior(state):raise ValueError()
        if not state[6] or not 0<=now-peer.get('state_time',0)<3:raise ValueError()
        ident=_match(server,f[3],state)
        if not ident:raise ValueError()
        peer['base_room']=dict(id=ident,digest=f[3],map=tuple(state[:2]),at=now,channel=conn)
        server._schedule_presence(now)
        return f'B ROOM {seq} 1\n'
    except (ValueError,KeyError,UnicodeError,TypeError):
        return f'B ROOM {seq} 0\n'

def expire(server,now):
    """Force a new snapshot on lease loss even if every avatar is standing still."""
    changed=False
    for peer in server.peers.values():
        if peer.get('base_room') and scope(server,peer) is None:
            peer.pop('base_room',None);changed=True
    if changed:server._schedule_presence(now)
