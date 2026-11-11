"""Native-result agreement before either client's stock link-contest save tail.

Does not compute standings, assign winners, copy saves or roll back another
player. Both reports are client claims tied to admitted native sessions.
"""
from dataclasses import dataclass,field

@dataclass
class ContestCompletion:
    session:int
    connections:dict
    category:int
    deadline:float
    reports:dict=field(default_factory=dict)
    saved:set=field(default_factory=set)
    state:str='running'

    def __post_init__(self):
        if len(self.connections)!=2 or len(set(self.connections.values()))!=2 or not 0<=self.category<5 or self.session<=0:
            raise ValueError('invalid contest session')
        self.connections=dict(self.connections)

    def report(self,*,owner,connection,session,category,standings,contestants_digest,now):
        if self.state not in ('running','agreed') or now>self.deadline or session!=self.session or self.connections.get(owner)!=connection:
            raise ValueError('stale native contest')
        if category!=self.category or type(standings) not in (list,tuple) or len(standings)!=4 or any(type(v) is not int for v in standings) or sorted(standings)!=[0,1,2,3]:
            raise ValueError('invalid native standings')
        if type(contestants_digest) is not str or len(contestants_digest)!=80 or any(c not in '0123456789abcdef' for c in contestants_digest):
            raise ValueError('invalid frozen contestant digest')
        value=(category,tuple(standings),contestants_digest)
        old=self.reports.get(owner)
        if old and old!=value:self.state='aborted';raise ValueError('native result changed')
        self.reports[owner]=value
        if len(self.reports)<2:return {'state':'waiting'}
        if len(set(self.reports.values()))!=1:self.state='aborted';return {'state':'aborted','reason':'results disagree'}
        self.state='agreed'
        return {'state':'agreed','session':self.session,'category':category,'standings':tuple(standings),'digest':contestants_digest}

    def save_ack(self,*,owner,connection,session,success):
        if self.state not in ('agreed','saved') or session!=self.session or self.connections.get(owner)!=connection or type(success) is not bool:
            raise ValueError('no agreed native result')
        if not success:return {'state':'local_save_failed','owner':owner}
        self.saved.add(owner)
        if len(self.saved)==2:self.state='saved'
        return {'state':self.state,'saved':tuple(sorted(self.saved))}

    def disconnect(self,owner,connection):
        if self.connections.get(owner)!=connection:return None
        # Once both native results agree, a local successful save stays true.
        # No fictitious rollback, refund, victory or partner save completion.
        prior=self.state
        if prior=='running':self.state='aborted'
        return {'state':self.state,'disconnected':owner,'saved':tuple(sorted(self.saved))}
