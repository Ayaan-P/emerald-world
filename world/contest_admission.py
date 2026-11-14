"""Bilateral stock-counter enrollment, never contest scoring/save authority.

Each authenticated connection must have reached its own native Emerald-mode
counter after private party/category selection. Tag membership alone is not
consent to enter. This coordinator doesn't start the native contest or emulate
its command stream; integration must consume the one-shot admission ticket.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Entry:
    owner: str
    connection: str
    visit: int
    category: int
    selection_revision: int
    until: float

class ContestAdmission:
    def __init__(self, *, clock, ticket_id):
        self.clock=clock;self.ticket_id=ticket_id
        self.pending={};self.active={}

    def enroll(self, *, owner, connection, visit, category, selection_revision,
               tag, members, counter, local_ready):
        if len(members)!=2 or len(set(members))!=2 or owner not in members:
            raise ValueError('exact current two-member tag required')
        if not connection or type(tag) is not int or tag<=0 or not counter or not local_ready:
            raise ValueError('native counter admission required')
        if any(type(v) is not int for v in (visit,category,selection_revision)) or not 0<visit<2**32 or not 0<=category<5 or not 0<selection_revision<2**32:
            raise ValueError('invalid native selection')
        if tag in self.active:raise ValueError('already admitted')
        now=self.clock()
        for key,value in tuple(self.pending.items()):
            if value.until<now:self.pending.pop(key)
        key=(tag,owner);old=self.pending.get(key)
        if old and old.connection==connection:
            if visit<old.visit or (visit==old.visit and selection_revision<old.selection_revision):raise ValueError('stale selection')
            if visit==old.visit and selection_revision==old.selection_revision and category!=old.category:raise ValueError('revision reused')
        entry=Entry(owner,connection,visit,category,selection_revision,now+30)
        self.pending[key]=entry
        other_owner=next(w for w in members if w!=owner)
        other=self.pending.get((tag,other_owner))
        if not other:return {'state':'waiting','owner':owner}
        if other.category!=category:
            # No coercion into the other trainer's category. Both choose again.
            self.pending.pop(key);self.pending.pop((tag,other_owner))
            return {'state':'different_categories','owners':tuple(members)}
        entries={owner:entry,other_owner:other}
        ticket=self.ticket_id()
        if type(ticket) is not int or not 0<ticket<2**64:raise ValueError('ticket allocation failed')
        result={'state':'prepared','ticket':ticket,'tag':tag,'category':category,
                'entries':entries,'acked':set(),'until':now+15,'members':tuple(members)}
        self.active[tag]=result
        for who in members:self.pending.pop((tag,who),None)
        return self._view(result)

    def _view(self,p):
        # No Pokémon payload or claimed outcome is retained by admission.
        return {'state':p['state'],'ticket':p['ticket'],'tag':p['tag'],
                'category':p['category'],'members':p['members'],
                'selections':{w:(e.visit,e.selection_revision) for w,e in p['entries'].items()}}

    def ready(self, *, tag, ticket, owner, connection, visit, selection_revision):
        p=self.active.get(tag)
        if not p or p['ticket']!=ticket or p['state']!='prepared' or self.clock()>p['until']:
            raise ValueError('expired or stale admission')
        e=p['entries'].get(owner)
        if not e or (e.connection,e.visit,e.selection_revision)!=(connection,visit,selection_revision):
            raise ValueError('changed connection or selection')
        p['acked'].add(owner)
        if p['acked']==set(p['members']):p['state']='admitted'
        return self._view(p)

    def consume(self, *, tag, ticket):
        p=self.active.get(tag)
        if not p or p['ticket']!=ticket or p['state']!='admitted' or self.clock()>p['until']:
            raise ValueError('bilateral native acknowledgment required')
        self.active.pop(tag)
        return self._view(p)

    def cancel(self, *, tag, owner, connection):
        p=self.active.get(tag)
        if p and owner in p['entries'] and p['entries'][owner].connection==connection:
            self.active.pop(tag)
            return {'state':'cancelled','members':p['members'],'ticket':p['ticket']}
        e=self.pending.get((tag,owner))
        if e and e.connection==connection:self.pending.pop((tag,owner))
        return None

    def expire(self):
        now=self.clock();cancelled=[]
        for tag,p in tuple(self.active.items()):
            if now>p['until']:
                self.active.pop(tag);cancelled.append({'state':'cancelled','members':p['members'],'ticket':p['ticket']})
        for key,e in tuple(self.pending.items()):
            if now>e.until:self.pending.pop(key)
        return cancelled
