"""Fail-closed shared ownership for future original-NPC movement adapters.

No live endpoint or author action enables this yet. A native runner must reserve,
acknowledge, restore, and synchronize every participant before it can be wired in.
Positions here are native attestations, not proof of geometry or anti-cheat.
"""
from dataclasses import dataclass, field
import secrets
import time


@dataclass
class Lease:
    token: str
    actor: str
    map: tuple
    path: tuple
    owner: object
    cohort: tuple
    deadline: float
    phase: str = 'prepare'
    ready: set = field(default_factory=set)
    restored: set = field(default_factory=set)
    reason: str = ''


class SceneLeases:
    """Single-world scene serialization with exact connection-instance fencing.

Never expire an active reservation. Abort enters restoration; disconnected
participants remain outstanding until their original instance is certified home
by the integration's recovery path. This deliberately prefers no movement over
an unprovable release. A new session cannot acknowledge an old one's objects.
"""
    def __init__(self, clock=time.monotonic, token=lambda: secrets.token_hex(16)):
        self.clock=clock;self.token=token;self.current=None

    @staticmethod
    def _same(cohort, peer):
        return next((i for i,p in enumerate(cohort) if p is peer),None)

    def _lease(self, token):
        lease=self.current
        if lease is None or token!=lease.token:raise ValueError('Stale canonical scene lease')
        return lease

    def prepare(self, actor, map_id, path, owner, cohort, *, validate_tile):
        """Called only after reviewed actor binding and all-client capability checks.

validate_tile must check exact native geometry, warp/stair exclusions and actor
footprint. The client must separately recheck collision before each actual step.
Path is a bounded closed cardinal walk, so the actor has an explicit home tile.
"""
        if self.current is not None:raise ValueError('A canonical scene still owns the world reservation')
        if actor not in ('canon_rydel','canon_wally','canon_briney','canon_steven'):raise ValueError('Unknown actor')
        if type(map_id) not in (tuple,list) or len(map_id)!=2 or any(type(n) is not int or not 0<=n<=255 for n in map_id):raise ValueError('Invalid map')
        if type(path) not in (tuple,list) or not 3<=len(path)<=9:raise ValueError('Bounded closed path required')
        points=[]
        for p in path:
            if type(p) not in (tuple,list) or len(p)!=2 or any(type(n) is not int or not 0<=n<=255 for n in p):raise ValueError('Invalid scene point')
            points.append(tuple(p))
        if points[0]!=points[-1] or any(abs(a[0]-b[0])+abs(a[1]-b[1])!=1 for a,b in zip(points,points[1:])):raise ValueError('Path must return home through cardinal steps')
        if not 1<=len(cohort)<=4 or len({id(p) for p in cohort})!=len(cohort) or self._same(cohort,owner) is None:raise ValueError('Exact complete connected cohort required')
        for p in points:
            if validate_tile(tuple(map_id),p) is not True:raise ValueError('Unverified native scene geometry')
        lease=Lease(self.token(),actor,tuple(map_id),tuple(points),owner,tuple(cohort),self.clock()+3)
        self.current=lease
        return self.snapshot()

    def snapshot(self):
        l=self.current
        if l is None:return None
        return dict(token=l.token,actor=l.actor,map=list(l.map),path=[list(p) for p in l.path],phase=l.phase,
                    ready=len(l.ready),participants=len(l.cohort),restored=len(l.restored),reason=l.reason)

    def acknowledge(self, peer, token, *, home, clear, installed):
        """ACK means collision reservation installed and original NPC at home.

Every member, not only the initiating trainer, must locally verify original
actor identity, no script/battle ownership, same geometry, and clear occupancy.
Do not derive these booleans from model output or generic STATE packets.
"""
        l=self._lease(token);i=self._same(l.cohort,peer)
        if i is None:raise ValueError('Connection does not own this acknowledgement')
        if l.phase!='prepare':raise ValueError('Scene no longer preparing')
        if self.clock()>=l.deadline:
            self.abort(token,'Preparation expired');return False
        if home is not True or clear is not True or installed is not True:
            self.abort(token,'Participant could not reserve the original actor safely');return False
        l.ready.add(i)
        return len(l.ready)==len(l.cohort)

    def start(self, peer, token):
        l=self._lease(token)
        if peer is not l.owner:raise ValueError('Only exact initiating connection can start')
        if l.phase!='prepare' or len(l.ready)!=len(l.cohort):raise ValueError('Every participant must acknowledge before movement')
        if self.clock()>=l.deadline:
            self.abort(token,'Preparation expired');raise ValueError('Expired scene preparation')
        l.phase='active';l.deadline=self.clock()+10
        return self.snapshot()

    def abort(self, token, reason):
        l=self._lease(token)
        l.phase='restoring';l.reason=reason
        # No implicit success, timeout release, or inferred return-home receipt.
        return self.snapshot()

    def finish(self, peer, token):
        l=self._lease(token)
        if peer is not l.owner or l.phase!='active':raise ValueError('No active owned scene')
        return self.abort(token,'Owner finished; awaiting every original actor restoration')

    def restored(self, peer, token, *, home, idle):
        l=self._lease(token);i=self._same(l.cohort,peer)
        if i is None or l.phase!='restoring':raise ValueError('No restoration owned by this connection')
        if home is not True or idle is not True:raise ValueError('Original actor has not safely returned')
        l.restored.add(i)
        if len(l.restored)!=len(l.cohort):return False
        self.current=None
        return True

    def tick(self):
        l=self.current
        if l and l.phase in ('prepare','active') and self.clock()>=l.deadline:
            return self.abort(l.token,'Scene deadline reached; restoration required')
        return self.snapshot()

    def disconnected(self, peer):
        l=self.current
        if l and self._same(l.cohort,peer) is not None:
            return self.abort(l.token,'Participant disconnected; restoration unresolved')
        return self.snapshot()

    def admits_connection(self):
        # A joining client cannot safely enter a scene before its barrier ACK.
        # The future live adapter must explicitly defer admission, not silently
        # enroll legacy clients or pretend its first snapshot was acknowledged.
        return self.current is None

    def blocks(self, map_id, x, y):
        l=self.current
        return bool(l and tuple(map_id)==l.map and (x,y) in l.path)
