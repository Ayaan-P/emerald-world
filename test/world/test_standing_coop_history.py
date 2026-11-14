import time,types,unittest,ast
import test_coop_cast_history as baseline
ROOT=baseline.ROOT
class Standing(baseline.Authority):
 def opt(self,key):return self.m.participation(self.s,self.conn,'a'*32,key,'private' if key=='get' else 'confirm',cooperative=True)
 def test_separate_consent_revocation_and_relevance(self):
  self.m.participation(self.s,self.conn,'a'*32,'on','confirm')
  with self.assertRaises(ValueError):self.share(cooperative=True,automatic=True)
  self.assertEqual(self.opt('on')['battle_mode'],'ON');self.share(cooperative=True,automatic=True)
  e=self.events[0];self.assertEqual(e['source'],'future_coop_participation_opt_in');self.assertTrue(self.m.relevant(e,['native:RusturfTunnel']))
  self.assertNotIn(self.conn['id'],str(e));self.assertNotIn('a'*32,str(e));self.assertNotIn('participants',e)
  self.assertEqual(self.share(cooperative=True,automatic=True)['evidence'],1)
  self.opt('off')
  with self.assertRaises(ValueError):self.share(cooperative=True,automatic=True)
  self.assertEqual(len(self.events),1);self.assertEqual(self.m.participation(self.s,self.conn,'a'*32,'get','private')['battle_mode'],'ON')
 def test_settings_scoped_to_local_player_save_and_survive_connection(self):
  self.opt('on');self.conn=dict(self.conn);self.assertEqual(self.opt('get')['battle_mode'],'ON')
  self.conn['id']='another-player';self.assertEqual(self.opt('get')['battle_mode'],'OFF')
  self.conn['id']='private-player';self.conn['core_active_run']='b'*32
  self.assertEqual(self.m.participation(self.s,self.conn,'b'*32,'get','private',cooperative=True)['battle_mode'],'OFF')
  with self.assertRaises(ValueError):self.opt('on')
 def test_production_dispatch_for_standing_and_automatic(self):
  tree=ast.parse((ROOT/'world/core_story.py').read_text());method=next(n for c in tree.body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='handle')
  ns={'__package__':'cast_fixture','re':__import__('re')};exec(compile(ast.Module(body=[method],type_ignores=[]),'<exact dispatch>','exec'),ns)
  self.s.peers={self.conn['id']:self.conn};self.conn['core_story_capable']=True;obj=types.SimpleNamespace(s=self.s)
  handle=lambda fields:ns['handle'](obj,self.conn,['CORE','a'*32,*fields])
  self.assertEqual(handle(['CMODE','on','confirm'])['battle_mode'],'ON');self.assertEqual(handle(['CAUTO',self.key,'2:1:2:1'])['evidence'],1)
  handle(['CMODE','off','confirm'])
  with self.assertRaises(ValueError):handle(['CAUTO',self.key,'2:1:2:2'])
  self.assertEqual(len(self.events),1)
if __name__=='__main__':unittest.main()
