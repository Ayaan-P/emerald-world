"""Current production handler/protocol; object staging is an explicit fixture."""
import copy,importlib, pathlib,sys,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
pkg=types.ModuleType('current');pkg.__path__=[str(ROOT/'world')];sys.modules['current']=pkg
class GuildError(ValueError):pass
sys.modules['current.guilds']=types.SimpleNamespace(GuildError=GuildError)
sys.modules['current.move_selectors']=types.SimpleNamespace(resolve=lambda v:v,describe=lambda v:None)
from current.link_protocol import LinkProtocol,_Tag
from current import field_move_ui as ui,overworld_moves as moves
moves.move_names=lambda:{'70':'Strength'}
class TaggedActions(unittest.TestCase):
 def setUp(self):
  self.protocol=LinkProtocol();tag=_Tag(1,'alice','bob',time.monotonic()+60,active=True);self.protocol._tags[1]=tag;self.protocol._tag_actor={'alice':1,'bob':1}
  self.c={'id':'alice','state':[0,16,1,1,4,0,1],'world_props_capable':True,'state_time':time.monotonic()};self.channel={'id':'alice','presence':self.c};self.obj={'id':'stone','text':'Heavy stone','kind':'prop','group':0,'num':16,'x':2,'y':1,'region_revision':'fixture'};self.requests=[]
  self.s=types.SimpleNamespace(link_protocol=self.protocol,link_channels={'alice':self.channel},peers={'alice':self.c},module_state={'world_object_moves':{'stone':{'roll':[70]}},'world_object_player_choices':{'stone':['roll']}},objects=[self.obj],object_use_pending=None,job=None,deployment=None)
  self.revision='one';self.offer=lambda s,o:{'actions':{'roll':'Roll stone'},'previews':{'roll':'Moves one tile east'},'object_revision':self.revision}
  def stage(server,request,position):
   moves.authorize(server,request);self.requests.append(copy.deepcopy(request));return types.SimpleNamespace(data={'request':'fixture'},dispatch=lambda:setattr(server,'deployment','pending'))
  sys.modules['current.actor_objects']=types.SimpleNamespace(offers=self.offer,stage=stage)
  sys.modules['current.region_characters']=types.SimpleNamespace(scoped=lambda *args:True)
  importlib.import_module('current.object_choices')
 def send(self,s):return ui.handle(self.s,self.channel,s.encode())
 def select(self):
  looked=self.send('FM LOOK 1');self.assertTrue(looked.startswith('FM LOOKED 1 '),looked)
  offered=self.send('FM GET 2 70');self.assertTrue(offered.startswith('FM OFFER 2 '),offered)
  token=self.channel['field_move_ui']['token'];self.assertTrue(self.send(f'FM VIEW 2 {token} roll').startswith('FM DETAIL'));return token
 def test_tagged_player_can_select_and_submit_without_leaving_tag(self):
  token=self.select();self.assertEqual(self.send(f'FM USE 2 {token} roll'),'FM WAIT 2\n');self.assertEqual(len(self.requests),1);self.assertEqual(self.requests[0]['move_effect']['move'],70);self.assertEqual(self.requests[0]['move_effect']['basis'],'client_reported_learned_move');self.assertEqual(self.protocol._tag_actor,{'alice':1,'bob':1});self.assertTrue(self.protocol.busy('alice'));self.assertFalse(self.protocol.field_action_busy('alice'))
 def test_encounter_start_between_preview_and_use_cancels_submission(self):
  token=self.select();self.protocol._encounters['alice']=(1,7);self.assertEqual(self.send(f'FM USE 2 {token} roll'),'FM FAIL 2\n');self.assertEqual(self.requests,[])
 def test_other_players_pending_encounter_does_not_take_my_agency(self):
  self.protocol._encounters['bob']=(1,7);self.select()
 def test_session_and_coop_wire_still_block(self):
  self.protocol.sessions._locks['alice']='session';self.assertEqual(self.send('FM LOOK 1'),'FM FAIL 1\n');self.protocol.sessions._locks.clear();self.protocol._tags[1].coop_wire=4;self.assertEqual(self.send('FM LOOK 1'),'FM FAIL 1\n')
 def test_stale_channel_and_changed_revision_still_rejected(self):
  token=self.select();self.revision='two';self.assertEqual(self.send(f'FM USE 2 {token} roll'),'FM FAIL 2\n');self.assertEqual(self.requests,[]);self.s.link_channels['alice']=dict(self.channel);self.assertEqual(self.send('FM LOOK 3'),'FM FAIL 0\n')
 def test_inconsistent_tag_is_not_admitted(self):
  del self.protocol._tags[1];self.assertTrue(self.protocol.field_action_busy('alice'));self.assertEqual(self.send('FM LOOK 1'),'FM FAIL 1\n')
 def test_old_guard_reproduces_the_actual_regression(self):
  self.protocol.field_action_busy=self.protocol.busy;self.assertEqual(self.send('FM LOOK 1'),'FM FAIL 1\n')
 def test_unpaired_field_actions_remain_available(self):
  self.protocol._tag_actor.clear();self.protocol._tags.clear();self.select()
 def test_facing_revalidation_survives_tag_admission(self):
  token=self.select();self.c['state'][2]=8;self.assertEqual(self.send(f'FM USE 2 {token} roll'),'FM FAIL 2\n');self.assertEqual(self.requests,[])
if __name__=='__main__':unittest.main()
