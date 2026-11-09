import hashlib,json,unittest
from copy import deepcopy
from world import actor_runtime as runtime
from world.character_companions import roster,descriptor
from world.mechanics import Candidate
import test_actor_cave_travel

class ExchangeTests(unittest.TestCase):
 def setUp(self):
  self.f=test_actor_cave_travel.ActorTravelTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.s=self.f.s;self.fx=self.f.fx
  state=deepcopy(self.s.module_state);sender=state['world_characters']['harbor_guide'];sender['version']+=1
  sender['team']=[dict(individual='companion',species=278,level=18),dict(individual='reserve',species=277,level=16)]
  receiver=deepcopy(sender);receiver.update(version=1,name='Visitor',object_id='visitor',team=[dict(individual='own',species=278,level=15)])
  state['world_characters']['visitor']=receiver
  obj=next(o for o in self.s.objects if o['id']=='harbor_guide');self.objects=self.s.objects+[dict(obj,id='visitor',x=3,y=4)]
  self.commit(state)
  state=deepcopy(self.s.module_state);state['world_characters']['harbor_guide']['version']+=1;state['world_characters']['harbor_guide']['team']=state['world_characters']['harbor_guide']['team'][:1];self.commit(state)
 def commit(self,state):
  source="def update(context,state):\n return dict(state=state,tiles=[],objects="+repr(self.objects)+")\n"
  self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest());self.fx.commit(dict(state=state,tiles=[],objects=self.objects));self.assertIsNone(self.s.module_error)
 def plan(self,actor,tool,args):
  state=deepcopy(self.s.module_state);c=state['world_characters'][actor];c['version']+=1;c['plan']=dict(id='decision_'+str(c['version']),purpose='Make my own companion decision.',steps=[dict(id='act',tool=tool,args=args,after=[])])
  self.commit(state)
 def offer(self):
  self.plan('harbor_guide','world.offer_companion',dict(target='visitor',individual='reserve',recipient_individual='received'))
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  return self.s.db.execute('SELECT id FROM companion_offers').fetchone()[0]
 def test_independent_accept_restart_identity_and_real_battle_descriptor(self):
  old=next(m for m in roster(self.s,'harbor_guide') if m['individual']=='reserve')
  key=self.offer();self.assertEqual(len(roster(self.s,'visitor')),1)
  self.s.close();self.fx.f.server=self.fx.f.open();self.s=self.fx.f.server;self.fx.server=self.s
  self.plan('visitor','world.respond_companion',dict(offer=key,decision='accept'));self.assertEqual(runtime.tick(self.s,now=20)['status'],'succeeded')
  self.assertNotIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])
  received=next(m for m in roster(self.s,'visitor') if m['individual']=='received')
  self.assertEqual([received[k] for k in ('species','personality','owner','level')],[old[k] for k in ('species','personality','owner','level')])
  self.assertFalse(received['on_team'])
  self.plan('visitor','world.prepare_challenge',dict(lineup='["received"]',text='A friendly challenge?'))
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'pending')
  _,path,_=self.s.deployment;self.s.deployment=None;source=path.read_text();ns={};exec(source,ns);self.fx.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.fx.commit(ns['update'](self.s._context(),deepcopy(self.s.module_state)));self.assertIsNone(self.s.module_error)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  values=descriptor(self.s,'visitor',self.s.module_state['world_characters']['visitor']['team'])
  self.assertEqual(values,[old['species'],old['level'],old['personality'],old['owner']])
  # Actual authenticated challenge transport resolves the transferred identity.
  token=self.s.create_identity('Player')['token'];peer=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.fx.send(peer,f'HELLO 1 Player {token} SOCIALCAVE10REGION1CHAR1CHARQUEST1CHARREG1CHARPK1WORLDOBJ1'))
  self.fx.state(peer,0,9,8,8);self.fx.send(peer,'REGION SELECT '+self.f.f.f.f.ra['place_id']);self.fx.send(peer,'CAVE GET');self.fx.send(peer,'CAVE ACK '+self.objects[0]['region_revision'])
  self.fx.state(peer,*self.s.cave_map,2,4)
  version=self.s.module_state['world_characters']['visitor']['version']
  wire=self.fx.send(peer,f"CHARACTER_CHALLENGE_REGION {peer['seq']+1} visitor {version} {self.objects[0]['region_revision']}")
  self.assertIn('CHARACTER_BATTLE_V2',wire);self.assertIn(' '.join(map(str,values)),wire)
  # The prior owner cannot resurrect an old local alias via authored team edits.
  from world.character_companions import validate
  with self.assertRaisesRegex(ValueError,'another character'):validate(self.s.db,'harbor_guide',dict(team=[dict(individual='reserve',species=277,level=16)]))
 def test_decline_keeps_custody_and_invented_catch_refused(self):
  key=self.offer();self.plan('visitor','world.respond_companion',dict(offer=key,decision='decline'))
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'succeeded');self.assertIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])
  self.plan('harbor_guide','world.offer_companion',dict(target='visitor',individual='imaginary_catch',recipient_individual='new'))
  self.assertEqual(runtime.tick(self.s,now=30)['status'],'blocked')
 def test_accept_requires_current_adjacent_idle_characters(self):
  key=self.offer();self.objects=[dict(o,x=8,y=8) if o['id']=='visitor' else o for o in self.objects]
  self.plan('visitor','world.respond_companion',dict(offer=key,decision='accept'))
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'blocked')
  self.assertIn('reserve',[m['individual'] for m in roster(self.s,'harbor_guide')])

 def test_full_native_state_bytes_remain_exact_without_new_practice(self):
  old=next(m for m in roster(self.s,'harbor_guide') if m['individual']=='reserve')
  # Opaque fixture payload, not a claim of a native-produced catch or battle.
  full=dict(size=100,species=old['species'],level=17,personality=old['personality'],owner=old['owner'],exp=4913,blob='ab'*100)
  with self.s.db:self.s.db.execute('INSERT INTO character_training VALUES(?,?,?,?,?)',('harbor_guide','reserve','c'*64,16,json.dumps(full,sort_keys=True)))
  key=self.offer();self.plan('visitor','world.respond_companion',dict(offer=key,decision='accept'))
  self.assertEqual(runtime.tick(self.s,now=20)['status'],'succeeded')
  from world.character_training import saved
  self.assertEqual(saved(self.s.db,'visitor','received'),dict(engine='c'*64,authored_level=16,state=full))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM character_training_receipts').fetchone()[0],0)
