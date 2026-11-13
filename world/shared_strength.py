"""Authenticated, ephemeral two-client native Strength transactions.

No items, story flags, or save credit. Native clients remain responsible for
collision and actual movement; both must acknowledge each phase.
"""
import time
from .strength_transaction import StrengthRoom,layout,FIERY_PATH

def encode(rows):return ''.join(f'{v:02x}' for _,x,y in rows for v in (x,y))
def decode(s):
    if len(s)!=24 or any(c not in '0123456789abcdef' for c in s):raise ValueError('layout')
    values=bytes.fromhex(s)
    return layout([(i+2,values[i*2],values[i*2+1]) for i in range(6)])

def handle(server,conn,raw):
    now=time.monotonic();actor=conn['id'];proto=server.link_protocol
    if not hasattr(server,'_strength_state'):server._strength_state={'joins':{},'rooms':{},'bindings':{}}
    state=server._strength_state;joins=state['joins'];rooms=state['rooms'];out=[]
    bindings=state['bindings']
    if server.link_channels.get(actor) is not conn or conn.get('closing'):return out
    def emit(room,msg):
        for who in room.owners:
            prefix=f"ST {msg['phase'].upper()} {room.tag} {room.visits[who]}"
            if msg['phase']=='closed':out.append((who,prefix+'\n'))
            else:out.append((who,prefix+f" {msg['revision']} {msg['identity']} {msg['old'][0]} {msg['old'][1]} {msg['new'][0]} {msg['new'][1]}\n"))
    presence=server._link_presence()
    def scope(who):return getattr(presence,'scopes',{}).get(who)
    for tag_id,room in tuple(rooms.items()):
        tag=proto._tags.get(tag_id)
        valid=tag and tag.active and set(tag.participants)==set(room.owners)
        valid=valid and all(w in presence and tuple(presence[w][:2])==FIERY_PATH for w in room.owners)
        channels,region=bindings[tag_id]
        valid=valid and all(server.link_channels.get(w) is channels[w]
            and not channels[w].get('closing') and scope(w)==region for w in room.owners)
        msg=room.tick(now) if valid else room.close('lost session')
        if msg:emit(room,msg);rooms.pop(tag_id,None);bindings.pop(tag_id,None)
    try:
        p=raw.decode('ascii').strip().split(' ')
        if len(raw)>180 or len(p)<4 or p[0]!='ST' or any(not x for x in p):return out
        op=p[1];tag_id=int(p[2]);visit=int(p[3])
        tag=proto._tags.get(proto._tag_actor.get(actor))
        if not tag or not tag.active or tag.id!=tag_id or len(tag.participants)!=2 or not 0<visit<2**32:return out
        if op=='CLOSE' and len(p)==4:
            room=rooms.get(tag_id)
            if room and room.visits.get(actor)==visit:emit(room,room.close('participant stopped'));rooms.pop(tag_id,None);bindings.pop(tag_id,None)
            joins.pop(actor,None);return out
        origin=presence.get(actor)
        if not origin or len(origin)!=7 or tuple(origin[:2])!=FIERY_PATH:return out
        room=rooms.get(tag_id)
        if op=='JOIN' and len(p)==5 and not room:
            if origin[6]!=1:return out
            rows=decode(p[4]);old=joins.get(actor)
            if old and old[0]==tag_id and (visit<old[1] or (visit==old[1] and old[2]!=rows)):return out
            joins[actor]=(tag_id,visit,rows,now,conn)
            peer=next(w for w in tag.participants if w!=actor);other=joins.get(peer)
            if not other or other[0]!=tag_id or other[2]!=rows or now-other[3]>15:return out
            if server.link_channels.get(peer) is not other[4] or other[4].get('closing') or scope(actor)!=scope(peer):return out
            dest=presence.get(peer)
            if not dest or len(dest)!=7 or dest[6]!=1 or tuple(dest[:2])!=FIERY_PATH:return out
            room=rooms[tag_id]=StrengthRoom(tuple(tag.participants),tag_id,{actor:visit,peer:other[1]},rows)
            bindings[tag_id]=({actor:conn,peer:other[4]},scope(actor))
            for who in room.owners:out.append((who,f'ST JOINED {tag_id} {room.visits[who]} 0\n'))
            return out
        if not room:return out
        if op=='PROPOSE' and len(p)==10:
            if origin[6]!=1:return out
            rev,identity,x,y,nx,ny=map(int,p[4:])
            # Native source must stand next to this boulder; no remote pushing.
            if abs(origin[2]-x)+abs(origin[3]-y)!=1:return out
            msg=room.propose(actor,tag_id,visit,rev,identity,(x,y),(nx,ny),now)
        elif op in ('READY','APPLIED') and len(p)==6:
            # Own native transaction locks controls after PREPARE, so ordinary
            # presence readiness is intentionally not required in these phases.
            fn=room.ready if op=='READY' else room.applied
            msg=fn(actor,tag_id,visit,int(p[4]),decode(p[5]),now)
        else:return out
        if msg:emit(room,msg)
    except (ValueError,UnicodeError,KeyError,TypeError,IndexError):return out
    finally:
        for who,entry in tuple(joins.items()):
            if now-entry[3]>20:joins.pop(who,None)
    return out
