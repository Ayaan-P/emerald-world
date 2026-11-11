"""Ephemeral opt-in Cut relay. Client completion reports, not save authority."""
from .link_sessions import LinkError

def handle(server, conn, raw):
    actor=conn['id']; proto=server.link_protocol
    state=getattr(server,'_shared_cut',None)
    if state is None: state=server._shared_cut={}
    # Bound all retained entries to currently active tags/connections.
    for who,entry in tuple(state.items()):
        tag=proto._tags.get(proto._tag_actor.get(who))
        if tag is None or not tag.active or tag.id!=entry[0]:state.pop(who,None)
    try:
        parts=raw.decode('ascii').split(' ')
        if len(raw)>160 or not parts or parts[0]!='CT' or any(not x for x in parts):return []
        op=parts[1]; nums=parts[2:]
        if any(not n.isascii() or not n.isdecimal() or len(n)>20 for n in nums):return []
        values=list(map(int,nums))
        if len(values)<2:return []
        tag_id,visit=values[:2]
        tag=proto._tags.get(proto._tag_actor.get(actor))
        if tag is None or not tag.active or tag.id!=tag_id or not 0<visit<2**32:return []
        if op=='OFF' and len(values)==2:
            if state.get(actor,(None,))[0]==tag_id:state.pop(actor,None)
            return []
        presence=server._link_presence(); origin=presence.get(actor)
        if not origin or len(origin)!=7 or origin[6]!=1:return []
        if op=='JOIN' and len(values)==4:
            group,map_id=values[2:]
            if group!=0 or not 0<=map_id<=255 or list(origin[:2])!=[group,map_id]:return []
            old=state.get(actor)
            if old and old[0]==tag_id and visit<old[1]:return []
            if old and old[:4]==(tag_id,visit,group,map_id):pass
            elif old and old[0]==tag_id and visit==old[1]:return []
            else:state[actor]=(tag_id,visit,group,map_id,0)
            return [(actor,f'CT JOINED {tag_id} {visit} {group} {map_id}\n')]
        if op!='CUT' or len(values)!=8:return []
        _,_,seq,group,map_id,local_id,x,y=values
        own=state.get(actor)
        if (not own or own[:4]!=(tag_id,visit,group,map_id) or group!=0
            or list(origin[:2])!=[group,map_id] or not 0<seq<2**32
            or not 0<local_id<=255 or not 0<=x<=32767 or not 0<=y<=32767
            or abs(origin[2]-x)>8 or abs(origin[3]-y)>8):return []
        ack=(actor,f'CT ACK {tag_id} {visit} {seq}\n')
        if seq<=own[4]:return [ack] # replay never causes another removal
        state[actor]=(*own[:4],seq)
        target=next(p for p in tag.participants if p!=actor)
        other=state.get(target); destination=presence.get(target)
        if not other or other[0]!=tag_id or other[2:4]!=(group,map_id):return [ack]
        try:proto.sessions._near(presence,actor,target,coop=True)
        except LinkError:return [ack]
        if abs(destination[2]-x)>8 or abs(destination[3]-y)>8:return [ack]
        # Target visit is explicit. No deferred queue or late-arrival replay.
        return [ack,(target,f'CT APPLY {tag_id} {other[1]} {group} {map_id} {local_id} {x} {y}\n')]
    except (ValueError,UnicodeError,IndexError,KeyError,TypeError):return []
