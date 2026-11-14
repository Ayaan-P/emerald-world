"""Stock Emerald-mode contest admission and result gate on authenticated channels."""
import secrets,time
from .contest_admission import ContestAdmission
from .contest_completion import ContestCompletion

def handle(server,conn,raw):
    out=[];proto=server.link_protocol;actor=conn['id'];connection=str(id(conn));now=time.monotonic()
    if not hasattr(server,'_contest_sessions'):
        server._contest_sessions={'admission':ContestAdmission(clock=time.monotonic,ticket_id=lambda:secrets.randbits(64) or 1),'results':{}}
    state=server._contest_sessions;a=state['admission'];results=state['results']
    def cancel(members):
        for who in members:out.append((who,'CN CANCEL\n'))
    for expired in a.expire():cancel(expired['members'])
    # Session-ended records are not kept as a result journal or replay authority.
    for wire in tuple(results):
        if wire not in proto._wire:results.pop(wire,None)
    try:
        p=raw.decode('ascii').strip().split(' ')
        if len(raw)>256 or len(p)<2 or p[0]!='CN' or any(not x for x in p):return out
        op=p[1];presence=server._link_presence()
        if op in ('JOIN','READY','CANCEL'):
            tag=proto._tags.get(proto._tag_actor.get(actor))
            if not tag or not tag.active or len(tag.participants)!=2:return out
            own=presence.get(actor)
            if op=='CANCEL':
                r=a.cancel(tag=tag.id,owner=actor,connection=connection)
                if r:cancel(r['members'])
                return out
            if not own or tuple(own[:2])!=(13,4):return out
            if op=='JOIN' and len(p)==6:
                visit,revision,category,tag_id=map(int,p[2:])
                if tag_id!=tag.id:return out
                r=a.enroll(owner=actor,connection=connection,visit=visit,selection_revision=revision,
                    category=category,tag=tag.id,members=tag.participants,counter=True,local_ready=True)
                if r['state']=='different_categories':cancel(r['owners'])
                if r['state']=='prepared':
                    for who in r['members']:
                        v,rev=r['selections'][who]
                        out.append((who,f"CN PREPARE {tag.id} {r['ticket']} {v} {rev} {r['category']}\n"))
            elif op=='READY' and len(p)==6:
                ticket,visit,revision,tag_id=map(int,p[2:])
                if tag_id!=tag.id:return out
                r=a.ready(tag=tag.id,ticket=ticket,owner=actor,connection=connection,visit=visit,selection_revision=revision)
                if r['state']=='admitted':
                    frozen=a.active[tag.id]
                    # Both actual native link connections, same registered counter/map.
                    if hasattr(presence,'scopes') and len({presence.scopes.get(w) for w in r['members']})!=1:raise ValueError('different region')
                    projected=dict(presence)
                    for who,e in frozen['entries'].items():
                        channel=server.link_channels.get(who);pos=presence.get(who)
                        if not channel or str(id(channel))!=e.connection or channel.get('closing') or not pos or tuple(pos[:2])!=(13,4):raise ValueError('counter departed')
                        projected[who]=(*pos[:6],1)
                    wire,admitted=proto.admit_contest(r['members'],projected)
                    results[wire]=ContestCompletion(wire,{w:e.connection for w,e in frozen['entries'].items()},r['category'],now+3600)
                    a.consume(tag=tag.id,ticket=ticket)
                    for who in r['members']:out.append((who,f'CN START {ticket} {wire}\n'))
                    out.extend(admitted)
        elif op in ('RESULT','SAVED'):
            if len(p)<3:return out
            wire=int(p[2]);entry=proto._entry(actor,wire)
            if entry.mode!=5:return out
            result=results.get(wire)
            if not result:return out
            if op=='RESULT' and len(p)==6:
                category=int(p[3]);ranks=p[4]
                if len(ranks)!=4 or any(c not in '0123' for c in ranks):return out
                r=result.report(owner=actor,connection=connection,session=wire,category=category,
                    standings=tuple(map(int,ranks)),contestants_digest=p[5],now=now)
                if r['state']=='agreed':
                    for who in entry.participants:out.append((who,f'CN AGREED {wire} {ranks}\n'))
                elif r['state']=='aborted':cancel(entry.participants)
            elif op=='SAVED' and len(p)==4 and p[3] in ('0','1'):
                result.save_ack(owner=actor,connection=connection,session=wire,success=p[3]=='1')
        return out
    except (ValueError,KeyError,TypeError,UnicodeError):
        # A malformed report never converts to a successful native result.
        out.append((actor,'CN CANCEL\n'));return out
