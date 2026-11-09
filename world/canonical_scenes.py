"""Optional synchronized original-actor scenes with durable restoration debt.

The first reviewed scene is Rydel taking one normal step and returning. Native
clients validate actual tiles/objects; these attestations are not anti-cheat.
"""
import json,secrets,time
from .canonical_scene_leases import SceneLeases


class CanonicalScenes:
    def __init__(self,server):
        self.s=server;self.leases=SceneLeases();self.offer=None;self.live=None
        server.db.execute('CREATE TABLE IF NOT EXISTS canonical_scene_recovery(singleton INTEGER PRIMARY KEY,document TEXT)')
        record=server.db.execute('SELECT document FROM canonical_scene_recovery WHERE singleton=1').fetchone()
        self.debt=json.loads(record[0]) if record else None

    def send(self,peer,command):self.s._queue(peer,'CORE SCENE '+command+'\n')
    def save(self):
        with self.s.db:
            if self.debt:self.s.db.execute('INSERT OR REPLACE INTO canonical_scene_recovery VALUES(1,?)',(json.dumps(self.debt,sort_keys=True),))
            else:self.s.db.execute('DELETE FROM canonical_scene_recovery WHERE singleton=1')
    def fresh(self,peer):
        return (self.s.peers.get(peer.get('id')) is peer and not peer.get('closing')
                and peer.get('state') and peer['state'][6] and 0<=time.monotonic()-peer.get('state_time',0)<=3)
    def recovery(self,peer):
        d=self.debt
        if d and peer['id'] in d['remaining'] and peer.get('core_active_run')==d['runs'].get(peer['id']):
            self.send(peer,'RECOVER '+d['token']+' '+' '.join(map(str,d['map']+[1,2,5])))
            self.s.guild_chat.message(peer,'World','Pending scene restoration. Return to the Bike Shop on this save; normal play is available.')

    def handle(self,peer,args):
        if self.s.peers.get(peer.get('id')) is not peer or peer.get('closing') or not peer.get('core_story_capable') or not peer.get('cast_scene_supported'):raise ValueError('Canonical scene capability required')
        if len(args)==2 and args[0]=='HELLO':
            if args[1]!=peer.get('core_active_run'):raise ValueError('Current save synchronization required')
            peer['cast_scene_run']=args[1];self.send(peer,'READY');self.recovery(peer);return
        if peer.get('cast_scene_run')!=peer.get('core_active_run') or not peer.get('cast_scene_run'):raise ValueError('Scene session not negotiated')
        if len(args)==3 and args[0]=='ASK':
            from .canonical_cast import records,BINDINGS,check_actor_location
            if args[1]!=peer['core_active_run'] or args[2]!='rydel':raise ValueError('Unsupported scene')
            row=records(self.s.module_state).get('canon_rydel',{})
            reached=peer.get('canonical_location') or {}
            if (row.get('scene')!='rydel_step' or reached.get('actor')!='canon_rydel'
                    or reached.get('version')!=row.get('version') or reached.get('expires',0)<time.monotonic()):raise ValueError('Talk to current Rydel invitation first')
            check_actor_location(self.s,peer,'canon_rydel')
            if self.debt or self.offer:raise ValueError('Another scene or restoration is pending')
            cohort=list(self.s.peers.values());map_id=list(peer['state'][:2])
            if not 1<=len(cohort)<=4 or any(not self.fresh(p) or p['state'][:2]!=map_id or not p.get('cast_scene_run') for p in cohort):raise ValueError('Every connected trainer must be ready in the Bike Shop with scene support')
            if time.monotonic()<peer.get('cast_scene_next',0):raise ValueError('Scene request cooldown')
            peer['cast_scene_next']=time.monotonic()+60
            self.offer=dict(token=secrets.token_hex(16),owner=peer,cohort=cohort,map=map_id,joined=set(),expires=time.monotonic()+15,version=row['version'])
            for p in cohort:
                self.send(p,'INVITE '+self.offer['token'])
                self.s.guild_chat.message(p,'Rydel','Group demonstration offered. /history scene join or cancel. Everyone must opt in; B cancels the scene.')
            return
        if len(args)==2 and args[0] in ('JOIN','DECLINE'):
            o=self.offer
            if not o or o['token']!=args[1] or not any(p is peer for p in o['cohort']):raise ValueError('Stale scene invitation')
            if args[0]=='DECLINE':self.cancel_offer();return
            if time.monotonic()>o['expires']:self.cancel_offer();raise ValueError('Scene invitation expired')
            o['joined'].add(peer['id'])
            if len(o['joined'])!=len(o['cohort']):return
            from .canonical_cast import records
            row=records(self.s.module_state).get('canon_rydel',{})
            if (row.get('scene')!='rydel_step' or row.get('version')!=o['version']
                    or len(self.s.peers)!=len(o['cohort']) or any(not self.fresh(p) or p['state'][:2]!=o['map'] for p in o['cohort'])):
                self.cancel_offer();raise ValueError('Scene or participants changed')
            # A closed route, not an arbitrary model-selected location. Every
            # client must verify real native geometry before barrier ACK.
            path=[(2,5),(3,5),(2,5)]
            if any(tuple(p['state'][2:4]) in path for p in o['cohort']):
                self.cancel_offer();raise ValueError('Stand away from the demonstration tiles')
            self.leases.token=lambda:o['token']
            lease=self.leases.prepare('canon_rydel',o['map'],path,o['owner'],o['cohort'],validate_tile=lambda m,p: self.bounds(m,p))
            self.debt=dict(token=lease['token'],map=o['map'],remaining=[p['id'] for p in o['cohort']],runs={p['id']:p['core_active_run'] for p in o['cohort']},version=o['version'])
            self.save() # Durable BEFORE any client can install a movement lock.
            self.live=dict(o,step=0,at=set());self.offer=None
            for p in self.live['cohort']:self.send(p,'PREPARE '+self.debt['token']+' '+' '.join(map(str,self.debt['map']+[1,2,5,3,5])))
            return
        if len(args)==2 and args[0]=='HOME':
            if not self.debt or self.debt['token']!=args[1] or peer['id'] not in self.debt['remaining'] or peer.get('core_active_run')!=self.debt['runs'].get(peer['id']):raise ValueError('Stale restoration receipt')
            # Only dedicated native scene handling emits HOME after verifying
            # the original actor idle at its exact home. No STATE inference.
            if self.live and self.leases.current.phase!='restoring':raise ValueError('Restoration was not requested')
            self.debt['remaining'].remove(peer['id'])
            if not self.live:self.send(peer,'RELEASE '+args[1])
            self.release_connected()
            if not self.debt['remaining']:
                self.debt=None;self.live=None;self.leases.current=None
            self.save();return
        if len(args)>=2 and self.live and self.live['token']==args[1] and any(p is peer for p in self.live['cohort']):
            if args[0]=='ACK' and len(args)==2:
                if self.leases.acknowledge(peer,args[1],home=True,clear=True,installed=True):
                    self.leases.start(self.live['owner'],args[1]);self.step(1)
                elif self.leases.current.phase=='restoring':self.abort()
                return
            if args[0]=='AT' and self.leases.current.phase=='active' and len(args)==3 and args[2] in ('1','2') and int(args[2])==self.live['step']:
                self.live['at'].add(peer['id'])
                if len(self.live['at'])==len(self.live['cohort']):
                    if self.live['step']==1:self.step(2)
                    else:self.abort()
                return
            if args[0]=='CANCEL' and len(args)==2:self.abort();return
        raise ValueError('Unknown or stale scene request')

    def release_connected(self):
        if self.live and not any(p['id'] in self.debt['remaining'] and not p.get('closing') for p in self.live['cohort']):
            for p in self.live['cohort']:
                if not p.get('closing'):
                    self.send(p,'RELEASE '+self.live['token'])
                    self.s.guild_chat.message(p,'World','Original actor restored. The scene ended; normal services and story progression are unchanged.')
            self.live=None;self.leases.current=None

    def bounds(self,m,p):
        from .build_catalog import validate_coords
        validate_coords(*m,*p);return True
    def step(self,index):
        self.live['step']=index;self.live['at']=set()
        for p in self.live['cohort']:self.send(p,'STEP '+self.live['token']+' '+str(index))
    def cancel_offer(self):
        if self.offer:
            for p in self.offer['cohort']:self.send(p,'RELEASE '+self.offer['token'])
        self.offer=None
    def abort(self):
        if self.live:
            self.leases.abort(self.live['token'],'Native restoration required')
            for p in self.live['cohort']:
                if not p.get('closing'):self.send(p,'RETURN '+self.live['token'])
    def disconnected(self,peer):
        if self.offer and any(p is peer for p in self.offer['cohort']):self.cancel_offer()
        if self.live and any(p is peer for p in self.live['cohort']):
            self.abort();self.release_connected()
    def tick(self):
        if self.offer and time.monotonic()>self.offer['expires']:self.cancel_offer()
        if self.live:
            previous=self.leases.current.phase
            self.leases.tick()
            if previous!='restoring' and self.leases.current.phase=='restoring':self.abort()
