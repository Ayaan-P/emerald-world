import importlib.util,pathlib,subprocess,tempfile,time,unittest,sys
import test_region_characters
class BaseShare(unittest.TestCase):
 def setUp(self):
  self.f=test_region_characters.RegionCharacterTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.a=self.peer('Alice',8);self.b=self.peer('Bob',9);self.c=self.peer('Carol',10)
 def peer(self,name,x):
  token=self.s.create_identity(name)['token'];p=dict(id=None,out=bytearray(),closing=False,state=None,seq=0,sock=object())
  self.assertIn('WELCOME',self.f.send(p,f'HELLO 1 {name} {token} SOCIALCHAT'))
  self.f.state(p,0,9,x,8);return p
 def offer(self):
  reply=self.f.send(self.a,'BASE_OFFER 1 Bob '+'00'*154)
  self.assertIn('OFFERED',reply)
  return next(iter(self.s.base_offers))
 def test_bilateral_actual_dispatch_private_and_one_use(self):
  token=self.offer()
  self.assertNotIn(token,self.s._snapshot(self.c))
  self.assertNotIn('BASE_DATA',self.f.send(self.c,f'BASE_ACCEPT 2 {token}'))
  reply=self.f.send(self.b,f'BASE_ACCEPT 2 {token}')
  self.assertIn('BASE_DATA 2 '+'00'*154,reply)
  self.assertNotIn('BASE_DATA',self.f.send(self.b,f'BASE_ACCEPT 3 {token}'))
  self.assertNotIn('BASE_DATA',self.s._snapshot(self.a))
 def test_cancel_expire_changed_connection_and_range(self):
  token=self.offer();self.assertIn('DECLINED',self.f.send(self.b,f'BASE_DECLINE 2 {token}'))
  self.assertEqual(self.s.base_offers,{})
  self.a['base_seq']=0;token=self.offer();self.s.base_offers[token]['expires']=0
  self.assertIn('UNAVAILABLE',self.f.send(self.b,f'BASE_ACCEPT 3 {token}'))
  self.a['base_seq']=0;token=self.offer();self.f.state(self.b,0,9,10,8)
  self.assertIn('UNAVAILABLE',self.f.send(self.b,f'BASE_ACCEPT 4 {token}'))
  self.f.state(self.b,0,9,9,8);self.s.peers['Alice']=dict(self.a)
  self.assertIn('UNAVAILABLE',self.f.send(self.b,f'BASE_ACCEPT 5 {token}'))
 def test_bounded_payload_and_no_history(self):
  before=self.s.db.execute('SELECT count(*) FROM events').fetchone()[0]
  self.assertIn('UNAVAILABLE',self.f.send(self.a,'BASE_OFFER 1 Bob 00'))
  self.assertEqual(before,self.s.db.execute('SELECT count(*) FROM events').fetchone()[0])
 def test_native_import_component(self):
  path=pathlib.Path('../native-shared-secret-bases/tests/test_base_share.py').resolve()
  if not path.exists():self.skipTest('paired native source unavailable')
  spec=importlib.util.spec_from_file_location('native_base',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with tempfile.TemporaryDirectory() as d:
   executable=str(module.build(d));payload=subprocess.run([executable],check=True,capture_output=True,text=True).stdout.strip()
   self.assertIn('OFFERED',self.f.send(self.a,'BASE_OFFER 1 Bob '+payload))
   token=next(iter(self.s.base_offers));reply=self.f.send(self.b,f'BASE_ACCEPT 2 {token}')
   received=next(line.split()[2] for line in reply.splitlines() if line.startswith('BASE_DATA '))
   self.assertEqual(payload,received)
   subprocess.run([executable,received],check=True,capture_output=True)
   for enabled in (0,1):subprocess.run([str(module.build_commands(d,enabled))],check=True,capture_output=True)

 def test_build_gate_is_explicit(self):
  p=subprocess.run([sys.executable,'scripts/build_expansion.py','--experimental-secret-bases'],capture_output=True,text=True)
  self.assertNotEqual(p.returncode,0);self.assertIn('requires --development',p.stderr)
 def test_legacy_chat_prefix_does_not_broadcast(self):
  before=list(self.c['chat_history'])
  reply=self.f.send(self.a,'CHAT 999 * '+b'/base accept 1234567812345678'.hex())
  self.assertIn('CHATMSG',reply)
  self.assertEqual(before,self.c['chat_history'])
