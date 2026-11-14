"""Two-owner, current-visit Strength transaction kernel.

This module does not authorize moves or mutate a native map. Transport must bind
owners to the active tag, and each native participant must validate/freeze locally.
"""
from dataclasses import dataclass, field

FIERY_PATH=(24,14)  # Exact published native map_groups.json, #121.
INITIAL=((2,10,15),(3,17,15),(4,8,11),(5,3,12),(6,6,23),(7,5,24))

def layout(rows):
    if type(rows) not in (list,tuple) or len(rows)!=6:raise ValueError('six native boulders required')
    result=[]
    for row in rows:
        if type(row) not in (list,tuple) or len(row)!=3 or any(type(n) is not int for n in row):raise ValueError('invalid boulder')
        identity,x,y=row
        if identity not in range(2,8) or not 0<=x<35 or not 0<=y<38:raise ValueError('out of reviewed map bounds')
        result.append(tuple(row))
    result=tuple(sorted(result))
    if tuple(r[0] for r in result)!=tuple(range(2,8)) or len({r[1:] for r in result})!=6:raise ValueError('duplicate boulder/position')
    return result

@dataclass
class StrengthRoom:
    owners: tuple
    tag: int
    visits: dict
    positions: tuple
    revision: int=0
    pending: dict|None=None
    closed: bool=False
    history: list=field(default_factory=list)

    def __post_init__(self):
        if len(self.owners)!=2 or len(set(self.owners))!=2 or set(self.visits)!=set(self.owners):raise ValueError('two authenticated owners required')
        if type(self.tag) is not int or not 0<self.tag<2**64 or any(type(v) is not int or not 0<v<2**32 for v in self.visits.values()):raise ValueError('invalid visit/tag')
        self.positions=layout(self.positions)
        self.visits=dict(self.visits)

    def _owner(self,owner,tag,visit):
        if self.closed or owner not in self.owners or type(tag) is not int or type(visit) is not int or tag!=self.tag or visit!=self.visits[owner]:raise ValueError('stale owner/tag/visit')

    def propose(self,owner,tag,visit,revision,identity,old,new,now):
        self._owner(owner,tag,visit)
        if self.pending or type(revision) is not int or revision!=self.revision or self.revision>=2**31-1:raise ValueError('busy or stale layout')
        if type(identity) is not int or type(old) not in (tuple,list) or type(new) not in (tuple,list) or len(old)!=2 or len(new)!=2 or any(type(n) is not int for n in (*old,*new)) or (identity,*old) not in self.positions or sum(abs(a-b) for a,b in zip(old,new))!=1:raise ValueError('not one native step')
        updated=layout([(i,*(new if i==identity else (x,y))) for i,x,y in self.positions])
        self.pending=dict(revision=self.revision+1,source=owner,identity=identity,old=tuple(old),new=tuple(new),updated=updated,ready=set(),applied=set(),phase='prepare',until=now+10)
        return self.message('prepare')

    def message(self,phase):
        p=self.pending
        return dict(phase=phase,tag=self.tag,visits=dict(self.visits),revision=p['revision'],identity=p['identity'],old=p['old'],new=p['new'])

    def ready(self,owner,tag,visit,revision,positions,now):
        self._owner(owner,tag,visit);p=self.pending
        if not p or p['phase']!='prepare' or revision!=p['revision'] or now>p['until'] or layout(positions)!=self.positions:raise ValueError('invalid prepare acknowledgment')
        p['ready'].add(owner)
        if p['ready']==set(self.owners):
            p['phase']='commit';p['until']=now+10
            return self.message('commit')
        return None

    def applied(self,owner,tag,visit,revision,positions,now):
        self._owner(owner,tag,visit);p=self.pending
        if not p or p['phase']!='commit' or revision!=p['revision'] or now>p['until'] or layout(positions)!=p['updated']:raise ValueError('invalid native completion')
        p['applied'].add(owner)
        if p['applied']!=set(self.owners):return None
        result=self.message('completed');self.positions=p['updated'];self.revision=p['revision'];self.pending=None
        # Reports from both native clients, not server-attested Strength or story credit.
        self.history.append(result)
        del self.history[:-32]
        return result

    def close(self,reason):
        # A partly applied displacement is not undone by speculative server coordinates.
        # Both clients must stop sharing and re-enter/re-register matching native layouts.
        self.closed=True
        result=dict(phase='closed',tag=self.tag,visits=dict(self.visits),reason=reason,partial=bool(self.pending and self.pending['phase']=='commit'))
        self.pending=None
        return result

    def tick(self,now):
        if self.pending and now>self.pending['until']:return self.close('timeout')
        return None
