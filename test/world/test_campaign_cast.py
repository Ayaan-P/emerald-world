import json,time,unittest
from copy import deepcopy
import test_actor_navigation as fixture
from world import actor_runtime as runtime,campaign_cast as cast
from world.battle_campaigns import publish,command,active
from world.shared_campaigns import load
from world.campaign_board import rows,handle
from world.guilds import GuildError

class CampaignCastTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.NavigationTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer
  self.p.update(campaign_run='a'*32,private_commands=True)
  self.point=[*self.s.wilds_map,70,70];self.p.update(state=[*self.point,1,0,1],state_time=time.monotonic())
  self.visit=dict(label='Survey point',point=[*self.s.wilds_map,76,70],revision=self.f.revision)
  self.doc=dict(id='mixed',title='Mixed exploration',entry='split',nodes={'split':dict(roles={
   'human':dict(visit=dict(label='Meeting point',point=self.point,revision=self.f.revision)),
   'scout':dict(visit=self.visit)},win=[],loss=[])})
  with self.s.db:publish(self.s,'harbor_guide',{},dict(campaign=json.dumps(self.doc)))
  command(self.s,self.p,['share','mixed']);self.key=active(self.s,self.p)[1]['shared'];command(self.s,self.p,['begin'])
 def invite(self,actor='harbor_guide'):
  command(self.s,self.p,['invite-npc',actor,'scout'])
  return next(x['id'] for x in cast.catalog(self.s) if x['actor']==actor)
 def plan(self,steps,identity='participate',actor='harbor_guide'):
  state=deepcopy(self.s.module_state);r=state['world_characters'][actor];r['version']+=1
  r['plan']=dict(id=identity,purpose='Decide independently and use actual arrival results.',steps=steps)
  self.f.f.commit(dict(state=state,objects=self.s.objects,tiles=[]));self.assertIsNone(self.s.module_error)
 def step(self,id,tool,args,after=[]):return dict(id=id,tool=tool,args=args,after=after)
 def test_actual_navigation_restart_and_private_party_completion(self):
  invitation=self.invite();command(self.s,self.p,['role','human'])
  self.plan([self.step('accept','world.decide_campaign_role',dict(invitation=invitation,decision='accept')),
   self.step('go','world.navigate',dict(revision=self.f.revision,x=76,y=70),['accept']),
   self.step('arrive','world.complete_campaign_role',dict(invitation=invitation,arrival_receipt=dict(result='go',key='arrival_receipt')),['go'])])
  self.assertEqual(runtime.tick(self.s,now=10)['status'],'succeeded')
  self.assertEqual(load(self.s,self.key)['status'],'ready')
  self.p['state_time']=time.monotonic();command(self.s,self.p,['check-in'])
  self.assertEqual(active(self.s,self.p)[1]['status'],'waiting')
  self.p['campaign_run']='b'*32;self.assertIsNone(active(self.s,self.p))
  self.assertEqual(runtime.tick(self.s,now=16)['status'],'pending');self.f.advance(0,True);self.f.advance(1)
  self.assertEqual(load(self.s,self.key)['status'],'ready')
  self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server;self.f.s=self.s;self.f.f.server=self.s;self.f.f.candidate=self.s.candidate
  for tick in range(2,24):self.f.advance(tick)
  self.assertEqual(runtime.tick(self.s,now=40)['status'],'succeeded')
  self.assertEqual(runtime.tick(self.s,now=46)['status'],'pending')
  self.assertEqual(runtime.tick(self.s,now=52)['status'],'succeeded')
  group=load(self.s,self.key);self.assertEqual(group['status'],'complete');self.assertEqual(group['npc_status']['harbor_guide'],'arrived')
  self.assertIsNone(active(self.s,self.p));self.p['campaign_run']='a'*32
  self.assertEqual(len(active(self.s,self.p)[1]['history']),1) # no invented NPC battle in human history
  for row, in self.s.db.execute("SELECT data FROM events WHERE kind='world_memory'"):
   if json.loads(row).get('event','').startswith('character_campaign_'):
    self.assertNotIn(self.key,row);self.assertNotIn('a'*32,row)
  self.assertEqual(cast.catalog(self.s),[])
 def test_decline_and_withdraw_do_not_move_or_complete(self):
  invitation=self.invite();before=deepcopy(self.s.objects)
  with self.s.db:cast.decide(self.s,'harbor_guide',{},dict(invitation=invitation,decision='decline'))
  self.assertEqual(self.s.objects,before);self.assertEqual(load(self.s,self.key)['status'],'deploying')
  invitation=self.invite('second');command(self.s,self.p,['role','human'])
  with self.s.db:cast.decide(self.s,'second',{},dict(invitation=invitation,decision='accept'))
  with self.s.db:cast.decide(self.s,'second',{},dict(invitation=invitation,decision='withdraw'))
  self.p['state_time']=time.monotonic();command(self.s,self.p,['check-in'])
  self.assertEqual(load(self.s,self.key)['status'],'ready');self.assertEqual(load(self.s,self.key)['npc_status']['second'],'withdrawn')
  command(self.s,self.p,['leave']);self.assertEqual(cast.catalog(self.s),[])
 def test_native_board_offer_stale_role_and_wrong_receipt(self):
  i=next(i for i,(_,act) in enumerate(rows(self.s,self.p)) if act==['invite-npc','harbor_guide','scout'])
  token=handle(self.s,self.p,self.p['campaign_run'],'view',str(i))['token']
  command(self.s,self.p,['role','human'])
  with self.assertRaises(ValueError):handle(self.s,self.p,self.p['campaign_run'],'pick',token)
  invitation=self.invite()
  with self.s.db:cast.decide(self.s,'harbor_guide',{},dict(invitation=invitation,decision='accept'))
  with self.assertRaises(ValueError):cast.poll(self.s,'second',{},dict(invitation=invitation,arrival_receipt=999))
  with self.assertRaises(ValueError):cast.poll(self.s,'harbor_guide',{},dict(invitation=invitation,arrival_receipt=999))
  self.assertEqual(load(self.s,self.key).get('npc_results',{}),{})
 def test_generated_geometry_and_client_revision_are_enforced(self):
  from world.campaign_visits import validate
  for change in (dict(revision='f'*64),dict(point=[*self.s.wilds_map,0,0])):
   with self.assertRaises(ValueError):validate(self.s,dict(visit=dict(self.visit,**change),next=[]))
  invitation=self.invite();command(self.s,self.p,['role','human'])
  with self.s.db:cast.decide(self.s,'harbor_guide',{},dict(invitation=invitation,decision='accept'))
  self.p['cave_ack']='f'*64
  with self.assertRaises(GuildError):command(self.s,self.p,['check-in'])
  self.assertEqual(load(self.s,self.key)['results'],{})
 def test_cancel_removes_outstanding_offer_and_cannot_force_actor(self):
  invitation=self.invite();self.assertEqual(load(self.s,self.key).get('npc_roles',{}),{})
  from world.character_reactions import dynamic_result
  event=self.s.memory.history()['events'][-1]
  self.assertTrue(dynamic_result(event,'harbor_guide',{}));self.assertFalse(dynamic_result(event,'second',{}))
  command(self.s,self.p,['leave']);self.assertEqual(cast.catalog(self.s),[])
  with self.assertRaises(ValueError):cast.decide(self.s,'harbor_guide',{},dict(invitation=invitation,decision='accept'))

if __name__=='__main__':unittest.main()
