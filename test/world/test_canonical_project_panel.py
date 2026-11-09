"""Autonomous cast work becomes playable through original-NPC field packets."""
import copy,time,unittest
import test_canonical_cast as fixture
from test_canonical_world_actions import pack
from world import canonical_cast as cast,canonical_world_actions as actions

class ProjectPanelTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CanonicalCastTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.p=pack()
  for scene in self.p['scenes'].values():scene['place']='MauvilleCity_BikeShop'
  self.p['scenes']['contribute']['actors']=['canon_rydel']
  self.a=self.f.action();self.a['changes'].update(places=['native:LittlerootTown','native:MauvilleCity_BikeShop'],initiative=self.p,
   world_action=dict(pack='workshop',scene='organize',choice='open',place='MauvilleCity_BikeShop',revision=0),
   intentions=[dict(id='open_project',kind='world_action',target='workshop',reason='Open an actual local conversation project.')])
  self.f.apply(self.a);self.c=self.f.peer();cast.response(self.s,self.c,'a'*32,'rydel')
 def send(self,guard,peer=None,run='a'*32):
  peer=peer or self.c;peer['out'].clear()
  self.s._line(peer,('CORE '+run+' PROJECT rydel '+guard+' 77').encode())
  return peer['out'].decode()
 def pick(self,peer=None):
  peer=peer or self.c;p=peer['cast_project_panel'];return self.send('pick:'+p['token']+':1:1',peer)
 def test_real_autonomous_action_to_field_choice_to_shared_consequence_restart(self):
  self.assertIn(' 5 1 ',self.send('view'))
  self.assertEqual(actions.step(self.s,now=10)['status'],'completed')
  self.c['state'][6]=0 # Actual original script owns input; field context is the narrow exception.
  wire=self.send('view');self.assertIn(' PROJECT rydel ',wire);self.assertIn(' 4 1 ',wire)
  before=copy.deepcopy(self.s.memory.history());result=self.pick();self.assertIn(' 5 1 ',result)
  self.assertEqual(self.s.opportunities.offers('Bob','MauvilleCity_BikeShop')[0]['scenes'][0]['id'],'shared')
  self.assertEqual(self.s.memory.history(),before) # No automatic disclosure of personal participation.
  self.assertEqual(self.c['state'][6],0)
  self.s.close();self.f.f.case.server=self.f.f.case.open();self.s=self.f.f.case.server;self.f.s=self.s
  self.c=self.f.peer();cast.response(self.s,self.c,'a'*32,'rydel')
  self.assertIn(' 4 1 ',self.send('view'))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_receipts').fetchone()[0],1)
 def test_other_player_race_and_save_switch_refuse_stale_choice(self):
  actions.step(self.s,now=10);other=self.f.peer('Bob');cast.response(self.s,other,'a'*32,'rydel')
  self.send('view');self.send('view',other);self.pick(other)
  self.assertIn('CORE REFUSED 77',self.pick())
  self.send('view');token=self.c['cast_project_panel']['token']
  cast.response(self.s,self.c,'b'*32,'rydel')
  self.assertIn('CORE REFUSED 77',self.send('pick:'+token+':1:1',run='b'*32))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM story_receipts').fetchone()[0],1)
 def test_no_remote_project_or_actor_turn_and_no_replay(self):
  actions.step(self.s,now=10);self.send('view');token=self.c['cast_project_panel']['token']
  self.assertEqual(self.c['cast_project_panel']['scene'],'solo')
  self.assertNotIn('organize',str(self.c['cast_project_panel']['choices']))
  self.pick();self.assertIn('CORE REFUSED 77',self.send('pick:'+token+':1:1'))
  self.c['canonical_location']['expires']=0
  self.assertIn('CORE REFUSED 77',self.send('view'))
