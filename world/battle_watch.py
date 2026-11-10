"""Voluntary session-only battle telemetry. Never retained as history or outcomes."""
import time
from functools import lru_cache
from .species_cohort import catalogue


@lru_cache(maxsize=1)
def _species():
    return {v:k for k,v in catalogue('expansion-native').items()}


def handle(server,conn,fields):
    if not conn.get('battle_watch_capable'):raise ValueError('Spectating unsupported')
    if fields[1:]==['SHARE','1']:
        conn['watch_sharing']=True;conn.pop('watch_frame',None)
        server._queue(conn,'WATCH_PERMISSION 1\n')
    elif fields[1:]==['SHARE','0']:
        conn['watch_sharing']=False;conn.pop('watch_frame',None)
        server._queue(conn,'WATCH_PERMISSION 0\n')
    elif fields[1:]==['OFF']:
        conn.pop('watch_target',None);conn.pop('watch_list',None)
    elif fields[1:]==['LIST']:
        conn['watch_list']=True;conn.pop('watch_target',None)
    elif len(fields)==3 and fields[1]=='TARGET':
        target=server.peers.get(fields[2])
        if not target or target is conn or target.get('closing') or not target.get('watch_sharing'):raise ValueError('Trainer not sharing')
        conn.pop('watch_list',None)
        conn['watch_target']=target # exact connection, never silently follow reconnect
    elif len(fields)>=4 and fields[1]=='SOLO':
        if not conn.get('watch_sharing'):raise ValueError('Sharing not enabled')
        seq=int(fields[2]);count=int(fields[3])
        if not 0<seq<=2147483647 or seq<=conn.get('watch_sequence',0) or count not in (0,1,2,3,4) or len(fields)!=4+count:raise ValueError('Invalid frame')
        slots=[]
        for token in fields[4:]:
            values=token.split(':')
            if len(values)!=5 or any(not x.isdigit() for x in values):raise ValueError('Invalid battler')
            side,species,level,hp,maxhp=map(int,values)
            if side not in (0,1) or not 1<=level<=100 or not 1<=maxhp<=9999 or not 0<=hp<=maxhp:raise ValueError('Invalid battler bounds')
            name=_species().get(species)
            if name is None:raise ValueError('Unsupported battle species')
            slots.append(dict(side=side,species=name,level=level,hp=hp,maxhp=maxhp))
        if sum(s['side']==0 for s in slots)>2 or sum(s['side']==1 for s in slots)>2:raise ValueError('Invalid sides')
        now=time.monotonic()
        if now-conn.get('watch_received',-100)<0.1:return
        conn.update(watch_sequence=seq,watch_received=now,watch_frame=slots)
    else:raise ValueError('Invalid spectating command')


def lines(server,conn):
    if not conn.get('battle_watch_capable'):return []
    if conn.get('watch_list'):
        names=[name for name,p in server.peers.items() if p is not conn and p.get('watch_sharing') and not p.get('closing')]
        text=['Sharing battles - /watch view NAME']+names[:4] if names else ['No trainers are sharing battles.']
        return ['WATCH_VIEW '+' '.join(t.encode('ascii').hex() for t in text)]
    target=conn.get('watch_target')
    if target is None:return []
    if target.get('closing') or server.peers.get(target.get('id')) is not target or not target.get('watch_sharing'):
        text=['Sharing ended. /watch view NAME to reconnect.']
        conn.pop('watch_target',None)
    elif time.monotonic()-target.get('watch_received',-100)>2 or not target.get('watch_frame'):
        text=[target['id']+': waiting for battle']
    else:
        text=[target['id']+': battle view']
        for s in target['watch_frame']:
            text.append(('%s %s L%d %d/%d'%('A' if s['side']==0 else 'F',s['species'] if len(s['species'])<=16 else s['species'][:15]+'~',s['level'],s['hp'],s['maxhp']))[:57])
    return ['WATCH_VIEW '+' '.join(t[:57].encode('ascii').hex() for t in text)]
