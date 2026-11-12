import json,time,unittest
from unittest.mock import patch
import test_cooperative_moves as fixture
from world import move_assistance as help,object_choices,character_reactions
from world.guilds import GuildError
class Assistance(unittest.TestCase):
 def setUp(self):
  self.f=fixture.Cooperative();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.p=self.f.peer('Requester')
 def ask(self,action="charge"):
  lines=object_choices.command(self.s,self.p,['ask-help','harbor_guide',action]);self.assertIn('OPTIONAL',lines[0]);token=self.p['move_help_offer']['token']
  object_choices.command(self.s,self.p,['ask-help','harbor_guide',action,token,'yes'])
  return help.catalog(self.s)[0]['request']
 def test_consent_decline_disconnect_and_stale_offer(self):
  k=self.ask();self.assertNotIn('UserOne',json.dumps(help.catalog(self.s)))
  with self.assertRaises(ValueError):help.respond(self.s,'second',{},dict(request=k,decision='decline',individual='',move=0))
  with self.s.db:r=help.respond(self.s,'harbor_guide',{},dict(request=k,decision='decline',individual='',move=0))
  self.assertEqual(r['outcome'],'move_help_declined');self.assertEqual(help.catalog(self.s),[])
  k=self.ask();self.p['npc_speech_session']='new';self.assertEqual(help.catalog(self.s),[])
  with self.assertRaises(ValueError):help.respond(self.s,'harbor_guide',{},dict(request=k,decision='help',individual='partner',move=85))
 def test_expiry_withdrawal_and_unlearned_move(self):
  k=self.ask()
  with self.assertRaises(ValueError):help.respond(self.s,'harbor_guide',{},dict(request=k,decision='help',individual='missing',move=85))
  self.assertEqual(len(help.catalog(self.s)),1)
  with patch.object(help.time,'time',return_value=time.time()+301):self.assertEqual(help.catalog(self.s),[])
  help.command(self.s,self.p,['help-stop',str(k)])
  with self.assertRaises(ValueError):help.respond(self.s,'harbor_guide',{},dict(request=k,decision='help',individual='partner',move=85))
 def test_real_npc_contribution_and_inflight_withdrawal(self):
  # Existing fixture creates real authority native-state records with a synthetic
  # MOVES1 result, not a live native inspection. It then commits one real action.
  self.f.test_npc_native_inspection_contributes_without_fabricating_a_player()
  self.p['state_time']=time.monotonic();k=self.ask('release')
  from copy import deepcopy
  from world import actor_runtime
  state=deepcopy(self.s.module_state);c=state['world_characters']['harbor_guide'];c['version']+=1;c['evidence']=[k]
  c['plan']=dict(id='assistance',purpose='Independently choose to offer this learned move.',steps=[dict(id='move',tool='world.respond_move_help',args=dict(request=k,decision='help',individual='partner',move=85),after=[])])
  self.f.f.f.f.f.f.commit(dict(state=state,tiles=[],objects=self.s.objects))
  from world.character_training import source
  token=source(self.s,'harbor_guide','partner')['token']
  self.s.db.execute("UPDATE actor_move_requests SET token=? WHERE actor='harbor_guide'",(token,)) # synthetic refreshed MOVES1 inspection for the new version
  self.assertEqual(actor_runtime.tick(self.s,now=time.monotonic()+10)['status'],'pending',list(self.s.db.execute('SELECT * FROM actor_tool_receipts')))
  self.p['state_time']=time.monotonic()
  help.command(self.s,self.p,['help-accept',str(k)]);token=self.p['move_help_confirm']['token']
  self.p['move_help_confirm']['revision']='stale'
  with self.assertRaises(GuildError):help.command(self.s,self.p,['help-accept',str(k),token,'yes'])
  help.command(self.s,self.p,['help-accept',str(k)]);token=self.p['move_help_confirm']['token']
  help.command(self.s,self.p,['help-accept',str(k),token,'yes'])
  help.command(self.s,self.p,['help-stop',str(k)])
  self.f.f.f.f.f.advance(5,True)
  self.assertEqual(actor_runtime.tick(self.s,now=time.monotonic()+20)['status'],'succeeded')
  r=json.loads(self.s.db.execute("SELECT result FROM actor_tool_receipts WHERE actor='harbor_guide' AND plan='assistance'").fetchone()[0])
  self.assertEqual(r['outcome'],'validated_object_state_committed');self.assertEqual(r['request_status'],'completed_after_withdrawal')
  event=json.loads(self.s.db.execute('SELECT data FROM events WHERE seq=?',(r['move_receipt'],)).fetchone()[0])
  self.assertEqual(event['basis'],'matching_native_move_inspection');self.assertEqual(event['character_id'],'harbor_guide')
  self.assertEqual(help.catalog(self.s),[])
  self.assertEqual(next(o for o in self.s.objects if o['id']=='panel')['y'],72)
 def test_request_routes_to_independent_author_and_recovery(self):
  k=self.ask();e=json.loads(self.s.db.execute('SELECT data FROM events WHERE seq=?',(k,)).fetchone()[0]);self.assertTrue(character_reactions.dynamic_result(e,'harbor_guide',{}));self.assertFalse(character_reactions.dynamic_result(e,'second',{}))
  raw=json.loads(self.s.db.execute('SELECT terms FROM move_assistance WHERE id=?',(k,)).fetchone()[0]);raw['execution']=['old','help']
  self.s.db.execute("UPDATE move_assistance SET status='executing',terms=? WHERE id=?",(json.dumps(raw),k))
  self.s.db.execute('INSERT INTO actor_tool_receipts VALUES(?,?,?,?,?,NULL)',('harbor_guide','old','help','blocked','{}'))
  help.recover(self.s);self.assertEqual(self.s.db.execute('SELECT status FROM move_assistance WHERE id=?',(k,)).fetchone()[0],'unconfirmed')

 def test_chat_disclosure_and_offer_restart_expiry(self):
  self.s.guild_chat.handle(self.p,'/guild object ask-help harbor_guide charge')
  lines=[bytes.fromhex(r[3]).decode() for r in self.p['chat_history']]
  self.assertTrue(any('OPTIONAL public' in x for x in lines));self.assertTrue(all(len(x)<=120 for x in lines))
  k=self.ask();self.s.close();base=self.f.f.f.f.f.f.f;base.server=base.open();self.s=base.server
  self.assertEqual(help.catalog(self.s),[])
  self.assertEqual(self.s.db.execute('SELECT actor FROM move_assistance WHERE id=?',(k,)).fetchone()[0],'harbor_guide')
 def test_no_effect_if_confirmation_never_happens(self):
  k=self.ask();raw=json.loads(self.s.db.execute('SELECT terms FROM move_assistance WHERE id=?',(k,)).fetchone()[0])
  with self.s.db:self.s.db.execute("UPDATE move_assistance SET status='awaiting_confirmation' WHERE id=?",(k,))
  self.assertIsNone(help.poll(self.s,'harbor_guide',{},dict(assistance=k)))
  help.command(self.s,self.p,['help-stop',str(k)])
  self.assertEqual(help.poll(self.s,'harbor_guide',{},dict(assistance=k))['outcome'],'move_help_ended_without_action')
  self.assertIsNone(self.s.deployment)
