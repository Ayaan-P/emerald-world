import json,time,unittest,hashlib
from world.mechanics import Candidate
from unittest.mock import patch
from world import player_cargo as cargo,cave_links,player_cargo_links as transfer
import test_cave_links as fixture

class CargoLinkTests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CaveLinkTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s
  self.a=self.f.connect('Carrier');self.a.update(private_commands=True,campaign_run='save-a')
  self.crate=dict(self.f.obj,id='crate',portable=True,x=3,y=2,text='Shared crate.')
  self.authored=self.s.objects+[self.crate]
  source='def update(context,state):\n return dict(state=state,tiles=[],objects='+repr(self.authored)+')\n'
  self.f.f.candidate=Candidate(source,hashlib.sha256(source.encode()).hexdigest())
  self.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.authored))
  self.assertIsNone(self.s.module_error)
  self.a['state'][4]=2;cargo.command(self.s,self.a,['take']);self.a['state'][4]=4
 def go(self,on=True):
  if on:cargo.command(self.s,self.a,['travel','on'])
  seq=self.a['seq']+1
  self.assertIn('LINK OFFER',self.f.f.send(self.a,f'INTERACT_REGION {seq} door {self.f.f.f.a}'))
  self.assertIn('LINK DATA',self.f.f.send(self.a,f'LINK ACCEPT {seq}'))
  self.assertIn('LINK COMMIT',self.f.f.send(self.a,f'LINK ACK {seq} {self.f.f.f.b}'))
  self.f.f.state(self.a,*self.s.cave_map,1,1)
  return seq
 def scope(self):return json.loads(self.s.db.execute("SELECT object FROM world_prop_custody WHERE id='crate'").fetchone()[0])['region_revision']
 def test_real_transfer_drop_and_native_snapshot_no_duplicate(self):
  source=self.scope();seq=self.go();self.assertEqual(self.scope(),source)
  self.assertIn('LINK DONE',self.f.f.send(self.a,f'LINK ARRIVED {seq} {self.f.f.f.b}'));self.assertEqual(self.scope(),self.f.f.f.b)
  self.f.f.state(self.a,*self.s.cave_map,3,3);self.a['state'][4]=2
  cargo.command(self.s,self.a,['drop','crate'])
  props=[o for o in self.s.objects if o['id']=='crate'];self.assertEqual(len(props),1);self.assertEqual(props[0]['region_revision'],self.f.f.f.b)
  self.assertIn('REGION_PROP','\n'.join(self.s._snapshot(self.a).splitlines()))
  self.assertEqual(self.s.db.execute('SELECT count(*) FROM world_prop_custody').fetchone()[0],1)
  self.f.f.commit(dict(state=self.s.module_state,tiles=[],objects=self.authored))
  self.assertIsNone(self.s.module_error)
  self.assertEqual(next(o for o in self.s.objects if o['id']=='crate')['region_revision'],self.f.f.f.b)
 def test_default_off_and_abort_leave_original_scope(self):
  source=self.scope();seq=self.go(False);self.f.f.send(self.a,f'LINK ARRIVED {seq} {self.f.f.f.b}')
  self.assertEqual(self.scope(),source)
 def test_abort_with_optin_leaves_source(self):
  source=self.scope();seq=self.go();cave_links.abort(self.s,self.a,seq);self.assertEqual(self.scope(),source)
 def test_save_switch_and_cargo_change_refuse_commit(self):
  source=self.scope();seq=self.go();self.a['campaign_run']='other'
  with self.assertRaises(ValueError):cave_links.line(self.s,self.a,['LINK','ARRIVED',str(seq),self.f.f.f.b])
  self.assertEqual(self.scope(),source)
 def test_failed_arrival_receipt_rolls_back_cargo_and_revision(self):
  source=self.scope();seq=self.go();revision=self.s.revision
  with patch.object(self.s,'_event',side_effect=ValueError('injected')):
   with self.assertRaises(ValueError):cave_links.line(self.s,self.a,['LINK','ARRIVED',str(seq),self.f.f.f.b])
  self.assertEqual(self.scope(),source);self.assertEqual(self.s.revision,revision)
 def test_restart_retains_arrived_scope_and_save_ownership(self):
  seq=self.go();self.f.f.send(self.a,f'LINK ARRIVED {seq} {self.f.f.f.b}')
  owner=cargo.identity(self.s,self.a);self.s.close();self.f.f.f.server=self.f.f.f.open();self.s=self.f.f.f.server
  self.s.peers['Carrier']=self.a;self.assertEqual(cargo.identity(self.s,self.a),owner)
  self.assertEqual(self.scope(),self.f.f.f.b)
  self.a['campaign_run']='other';self.assertIsNone(cargo.identity(self.s,self.a))

 def test_pending_transfer_prevents_local_custody_changes(self):
  from world.guilds import GuildError
  self.go()
  for words in (['drop','crate'],['take'],['travel','off']):
   with self.assertRaises(GuildError):cargo.command(self.s,self.a,words)
 def test_public_cargo_receipt_omits_save_and_trainer(self):
  seq=self.go();self.f.f.send(self.a,f'LINK ARRIVED {seq} {self.f.f.f.b}')
  raw=self.s.db.execute("SELECT data FROM events WHERE kind='world_memory' ORDER BY seq DESC LIMIT 1").fetchone()[0]
  self.assertEqual(json.loads(raw)['event'],'player_cargo_link_arrived')
  self.assertNotIn('Carrier',raw);self.assertNotIn('save-a',raw)

if __name__=='__main__':unittest.main()
