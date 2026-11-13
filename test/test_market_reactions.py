import ast,json,os,pathlib,sqlite3,subprocess,sys,tempfile,time,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
# The app also contains vanilla shop.c; prefer the actual expansion checkout.
NATIVE=pathlib.Path(os.environ['EW_NATIVE_SOURCE']).resolve() if 'EW_NATIVE_SOURCE' in os.environ else (ROOT/'engines/expansion-native' if (ROOT/'engines/expansion-native/src/world/world_market.c').exists() else ROOT)
pkg=types.ModuleType('reaction_fixture');pkg.__path__=[str(ROOT/'world')];sys.modules[pkg.__name__]=pkg
# Use actual inherited retail item catalog; only reviewed map identity lookup is isolated.
sys.modules['reaction_fixture.build_catalog']=types.SimpleNamespace(catalog_maps=lambda:{})
from reaction_fixture import hoenn_markets as m,history_world_rules as rules
m.catalog_maps=lambda:{p:{'name':n} for n,p in m.SITES.items()}
class Markets(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.db=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.addCleanup(self.db.close);self.db.execute('CREATE TABLE history(seq INTEGER PRIMARY KEY,event TEXT,data TEXT)')
  self.peer={'id':'alice','state':[9,13,1,1,2,0,1],'state_time':time.monotonic()};self.conn={'id':'alice','presence':self.peer,'sock':1};self.s=types.SimpleNamespace(db=self.db,peers={'alice':self.peer},link_channels={'alice':self.conn},connections={1:True},link_protocol=types.SimpleNamespace(sessions=types.SimpleNamespace(_locks={}),_encounters={}),revision=0,job=None,deployment=None)
  def append(event,data):return self.db.execute('INSERT INTO history(event,data) VALUES(?,?)',(event,json.dumps(data))).lastrowid
  def history(after=0,limit=64):
   rows=self.db.execute('SELECT seq,event,data FROM history WHERE seq>? ORDER BY seq LIMIT ?',(after,limit)).fetchall();head=self.db.execute('SELECT coalesce(max(seq),0) FROM history').fetchone()[0];return {'events':[dict(seq=q,event=e,**json.loads(d)) for q,e,d in rows],'cursor':rows[-1][0] if rows else after,'through':head}
  self.s.memory=types.SimpleNamespace(append=append,history=history)
  with self.db:self.first=m.configure(self.s,'merchant',{},dict(site='SlateportCity_Mart',items='[43,114]',minutes=10))['revision']
 def send(self,s):return m.wire(self.s,self.conn,s.encode())
 def test_purchase_changes_real_later_shelf_through_existing_executor(self):
  cap=types.SimpleNamespace(kinds=('canonical','world'),poll=None,arguments={'site':'str','items':'str','minutes':'int'},execute=m.configure)
  sys.modules['reaction_fixture.actor_runtime']=types.SimpleNamespace(CAPABILITIES={'world.arrange_market_shelf':cap},actor_records=lambda server:{'merchant':{'canonical':False,'status':'active'}})
  d=dict(event='hoenn_market_purchase_reported',where={'site':'SlateportCity_Mart','item':43},tool='world.arrange_market_shelf',args=dict(site='SlateportCity_Mart',items='[48,120]',minutes=60),cooldown=60,per_hour=1)
  with self.db:rules.publish(self.s,'merchant',{},dict(id='response',rule=json.dumps(d)))
  self.assertIn(f' 2 {self.first} 43 114',self.send('MK GET 2'));self.assertEqual(self.send(f'MK BUY 1 {self.first} 43 3'),'MK RECORDED 1\n');self.assertEqual(rules.tick(self.s,now=time.time())['status'],'succeeded');self.assertTrue(self.send('MK GET 2').endswith('48 120\n'))
  # A buyer with an already frozen shelf can finish its original checkout.
  self.assertEqual(self.send(f'MK BUY 2 {self.first} 43 1'),'MK RECORDED 2\n');self.assertEqual(m.catalog(self.s)['active'][0]['items'],[48,120])
  other=sqlite3.connect(pathlib.Path(self.temp.name)/'world.db');self.assertEqual(json.loads(other.execute('SELECT items FROM hoenn_market_shelves').fetchone()[0]),[48,120]);self.assertEqual(other.execute('SELECT count(*) FROM hoenn_market_reports').fetchone()[0],2);other.close()
 def test_no_unissued_revision_item_or_replay_credit(self):
  self.assertEqual(self.send(f'MK BUY 1 {self.first} 43 3'),'MK UNCONFIRMED 1\n');self.send('MK GET 2');self.assertEqual(self.send(f'MK BUY 2 {self.first} 43 3'),'MK RECORDED 2\n');self.assertEqual(self.send(f'MK BUY 2 {self.first} 43 3'),'MK UNCONFIRMED 2\n');self.assertEqual(self.send(f'MK BUY 3 {self.first} 28 1'),'MK UNCONFIRMED 3\n');self.assertEqual(self.db.execute('SELECT count(*) FROM hoenn_market_reports').fetchone()[0],1)
 def test_auth_context_lifetime_quantity(self):
  self.send('MK GET 2');self.assertEqual(self.send(f'MK BUY 1 {self.first} 43 10000'),'MK UNCONFIRMED 1\n');self.conn['market_report_shelves'][self.first]['at']-=7201;self.assertEqual(self.send(f'MK BUY 2 {self.first} 43 1'),'MK UNCONFIRMED 2\n');self.send('MK GET 2');self.s.link_protocol.sessions._locks['alice']=1;self.assertTrue(self.send(f'MK BUY 3 {self.first} 43 1').startswith('MK UNCONFIRMED'));self.s.link_protocol.sessions._locks.clear();self.peer['state'][1]=12;self.assertEqual(self.send('MK GET 2'),'MK NONE\n');self.peer['state'][1]=13;self.s.link_channels['alice']=dict(self.conn);self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
 def test_clerk_absence_keeps_explicit_mart_visit_listing_and_checkout(self):
  # Real bridge revokes ordinary field presence for the clerk script.
  self.peer['state'][6]=1
  self.send('MK ENTER 9 13');self.send('MK GET 2')
  self.peer['state']=[0,0,0,0,1,7,0]
  self.assertTrue(self.send('MK GET 2').startswith('MK SHELF2 9 13'), 'clerk dialogue cleared Community stock')
  self.assertEqual(self.send(f'MK BUY 1 {self.first} 43 1'),'MK RECORDED 1\n')
  self.assertEqual(self.db.execute('SELECT item,quantity FROM hoenn_market_reports').fetchall(),[(43,1)])
  self.assertEqual(self.peer['state'],[0,0,0,0,1,7,0])
 def test_visit_cannot_start_from_absence_or_unready_field(self):
  for state in ([0,0,0,0,1,7,0],[9,13,1,1,2,0,0],[9,12,1,1,2,0,1]):
   self.peer['state']=state;self.send('MK ENTER 9 13')
   self.assertNotIn('market_visit',self.conn)
   self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
  self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
 def test_visit_security_revocation_and_replay(self):
  for scenario in ('expiry','scope','leave','identity','channel','stale','lock','encounter'):
   with self.subTest(scenario=scenario):
    m.end_visit(self.conn);self.peer['state']=[9,13,1,1,2,0,1];self.peer['state_time']=time.monotonic()
    self.s.peers['alice']=self.peer;self.s.link_channels['alice']=self.conn
    self.s.link_protocol.sessions._locks.clear();self.s.link_protocol._encounters.clear()
    self.send('MK ENTER 9 13');self.send('MK GET 2');self.peer['state']=m.ABSENT.copy()
    if scenario=='expiry':self.conn['market_visit']['at']-=7201
    if scenario=='scope':
     self.peer['state']=[9,12,1,1,2,0,1];m.observe(self.conn);self.peer['state']=m.ABSENT.copy()
    if scenario=='leave':self.send('MK LEAVE')
    if scenario=='identity':self.s.peers['alice']=dict(self.peer)
    if scenario=='channel':self.s.link_channels['alice']=dict(self.conn)
    if scenario=='stale':self.peer['state_time']-=6
    if scenario=='lock':self.s.link_protocol.sessions._locks['alice']=1
    if scenario=='encounter':self.s.link_protocol._encounters['alice']=1
    self.assertTrue(self.send(f'MK BUY 100 {self.first} 43 1').startswith('MK UNCONFIRMED'))
  self.assertEqual(self.db.execute('SELECT count(*) FROM hoenn_market_reports').fetchone()[0],0)
 def test_no_request_during_stale_gap_cannot_revive_on_heartbeat(self):
  self.send('MK ENTER 9 13');self.send('MK GET 2');self.peer['state']=m.ABSENT.copy()
  self.peer['state_time']-=6
  # Execute the actual heartbeat boundary, including timestamp replacement.
  source=(ROOT/'world/server.py').read_text();start=source.index('                from .hoenn_markets import observe as market_observe')
  end=source.index('                self._deliver_links(',start)
  import textwrap
  exec(compile(textwrap.dedent(source[start:end]),'actual_heartbeat','exec'),{'__package__':'reaction_fixture','self':self.s,'conn':self.peer,'now':time.monotonic()})
  self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
  self.assertTrue(self.send(f'MK BUY 1 {self.first} 43 1').startswith('MK UNCONFIRMED'))
 def test_no_request_during_stale_observation_cannot_revive(self):
  self.send('MK ENTER 9 13');self.send('MK GET 2');self.peer['state']=m.ABSENT.copy();self.peer['state_time']-=6
  m.observe(self.conn);self.peer['state_time']=time.monotonic()
  self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
 def busy_lifecycle(self,encounter):
  from reaction_fixture.link_protocol import LinkProtocol
  self.s.link_protocol=LinkProtocol(id_factory=lambda:7)
  source=(ROOT/'world/server.py').read_text()
  node=next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name=='_deliver_links')
  ns={'__package__':'reaction_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_delivery','exec'),ns)
  self.s._queue=lambda *a:None
  presence={'alice':[9,13,1,1,2,0,1],'bob':[9,13,2,1,2,0,1]}
  def process(who,line):
   out=self.s.link_protocol.process(who,line.encode(),presence)
   self.assertFalse(any('ERROR' in text for _,text in out),out)
   ns['_deliver_links'](self.s,out)
  self.send('MK ENTER 9 13');self.send('MK GET 2')
  if encounter:
   process('alice','T OFFER bob');process('bob','T ACCEPT 7')
   self.assertIn('market_visit',self.conn,'social consent alone is not busy')
   process('alice','L CHOICE HOLD 7 42')
   self.assertIn('alice',self.s.link_protocol._encounters)
  else:
   process('alice','L OFFER 1 bob')
   self.assertIn('alice',self.s.link_protocol.sessions._locks)
  self.peer['state']=m.ABSENT.copy()
  # No market traffic occurs until after the authoritative hold is released.
  if encounter:process('alice','L CHOICE RELEASE 7 42')
  else:process('bob','L REJECT 7')
  self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
  self.assertTrue(self.send(f'MK BUY 1 {self.first} 43 1').startswith('MK UNCONFIRMED'))
  self.assertEqual(self.db.execute('SELECT count(*) FROM hoenn_market_reports').fetchone()[0],0)
 def test_no_market_request_during_real_session_lock(self):self.busy_lifecycle(False)
 def test_no_market_request_during_real_encounter_hold(self):self.busy_lifecycle(True)
 def test_visit_deadline_is_not_renewed_by_absent_heartbeat(self):
  self.peer['state'][6]=1;self.send('MK ENTER 9 13');at=self.conn['market_visit']['at']
  self.peer['state']=m.ABSENT.copy();self.send('MK ENTER 9 13')
  self.assertEqual(self.conn['market_visit']['at'],at)
 def test_actual_presence_transition_revokes_market_scope(self):
  source=(ROOT/'world/server.py').read_text()
  marker='from .hoenn_markets import observe as market_observe'
  self.assertIn(marker,source,'production presence update must revoke wrong-scope visits')
  start=source.index(marker);boundary='                '+source[start:source.index('self._deliver_links(',start)]
  self.peer['state'][6]=1;self.send('MK ENTER 9 13')
  self.peer['state']=[9,12,1,1,2,0,1]
  import textwrap
  exec(compile(textwrap.dedent(boundary),'actual_presence_market_boundary','exec'),{'__package__':'reaction_fixture','self':self.s,'conn':self.peer,'now':time.monotonic()})
  self.assertNotIn('market_visit',self.conn)
 def test_visit_shelf_remains_frozen_after_publication_expiry(self):
  self.send('MK ENTER 9 13');first=self.send('MK GET 2')
  self.db.execute('UPDATE hoenn_market_shelves SET expires=0')
  self.peer['state']=m.ABSENT.copy()
  self.assertEqual(self.send('MK GET 2'),first)
 def test_stale_or_busy_visit_cannot_revive_in_absence(self):
  for scenario in ('stale','lock','encounter'):
   with self.subTest(scenario=scenario):
    m.end_visit(self.conn);self.peer['state']=[9,13,1,1,2,0,1];self.peer['state_time']=time.monotonic()
    self.send('MK ENTER 9 13');self.send('MK GET 2');self.peer['state']=m.ABSENT.copy()
    if scenario=='stale':self.peer['state_time']-=6
    if scenario=='lock':self.s.link_protocol.sessions._locks['alice']=1
    if scenario=='encounter':self.s.link_protocol._encounters['alice']=1
    self.send('MK GET 2');self.peer['state_time']=time.monotonic()
    self.s.link_protocol.sessions._locks.clear();self.s.link_protocol._encounters.clear()
    self.assertEqual(self.send('MK GET 2'),'MK NONE\n')
 def test_native_poll_dialogue_snapshot_buy_to_actual_authority_dispatch(self):
  # Complete market C module <-> actual authority dispatch, with real SQLite.
  sys.modules['reaction_fixture.combined_regions']=types.SimpleNamespace(pending=lambda *a:False)
  node=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line')
  ns={'__package__':'reaction_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_dispatch','exec'),ns)
  replies=[];self.s._queue=lambda c,s:replies.append(s)
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'platform').mkdir()
   for name in ['global.h','platform/world_bridge.h','platform/native_link.h']:(d/name).write_text('')
   (d/'platform/world_market.h').write_text((NATIVE/'include/platform/world_market.h').read_text())
   (d/'test.c').write_text((ROOT/'test/native_market_lifecycle.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_market.c')))
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-DEW_HOENN_MARKETS=1','-DEW_MARKET_REACTIONS=1','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True)
   p=subprocess.Popen([str(d/'test')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
   try:
    def command(line):
     p.stdin.write(line+'\n');p.stdin.flush();out=[]
     while True:
      result=p.stdout.readline()
      self.assertTrue(result,'native fixture exited before DONE')
      if result=='DONE\n':return out
      out.append(result.strip())
    def exchange(lines):
     for line in lines:
      replies.clear();ns['_link_line'](self.s,self.conn,line.encode())
      for reply in replies:
       if reply:command('L '+reply.strip())
    entry=command('P');self.assertEqual(entry,['MK ENTER 9 13','MK GET 2']);exchange(entry)
    self.peer['state']=m.ABSENT.copy();m.observe(self.conn);command('D')
    exchange(command('T'));self.assertTrue(replies[-1].startswith('MK SHELF2'))
    command('S');buy=command('B');self.assertEqual(buy,[f'MK BUY 1 {self.first} 43 1'])
    exchange(buy);self.assertEqual(replies,['MK RECORDED 1\n']);command('A')
    self.assertEqual(self.db.execute('SELECT item,quantity FROM hoenn_market_reports').fetchall(),[(43,1)])
    replies.clear();ns['_link_line'](self.s,self.conn,buy[0].encode());self.assertEqual(replies,['MK UNCONFIRMED 1\n'])
   finally:
    p.stdin.close();p.wait(timeout=5);p.stdout.close()
   self.assertEqual(p.returncode,0)
 def test_ordinary_legacy_catalog_unchanged(self):self.assertEqual(self.send('MK GET 1'),'MK SHELF 9 13 15 2 43 114\n')
 def test_actual_transport_dispatch(self):
  sys.modules['reaction_fixture.combined_regions']=types.SimpleNamespace(pending=lambda *a:False);node=next(n for n in ast.walk(ast.parse((ROOT/'world/server.py').read_text())) if isinstance(n,ast.FunctionDef) and n.name=='_link_line');ns={'__package__':'reaction_fixture'};exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_dispatch','exec'),ns);out=[];self.s._queue=lambda c,s:out.append(s);ns['_link_line'](self.s,self.conn,b'MK GET 2');self.assertTrue(out[0].startswith('MK SHELF2'))
 def test_native_enabled_disabled_revision_and_owner(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'platform').mkdir()
   for p in ['global.h','platform/world_bridge.h','platform/native_link.h']:(d/p).write_text('')
   (d/'platform/world_market.h').write_text((NATIVE/'include/platform/world_market.h').read_text());(d/'test.c').write_text((ROOT/'test/native_market_reactions.c').read_text().replace('ACTUAL_SOURCE',str(NATIVE/'src/world/world_market.c')))
   for on in [0,1]:
    subprocess.run(['cc','-std=c99','-DPORTABLE','-DEW_HOENN_MARKETS=1',f'-DEW_MARKET_REACTIONS={on}','-fsanitize=undefined','-iquote',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_actual_checkout_reports_only_after_credit_and_debit(self):
  source=(NATIVE/'src/shop.c').read_text();parts=[]
  for sig in ['static void BuyMenuTryMakePurchase(u8 taskId)','static void BuyMenuSubtractMoney(u8 taskId)']:
   start=source.index(sig+'\n{');parts.append(source[start:source.index('\n}',start)+2].replace('static void ','void ',1))
  with tempfile.TemporaryDirectory() as tmp:
   d=pathlib.Path(tmp);(d/'test.c').write_text((ROOT/'test/native_market_checkout.c').read_text().replace('ACTUAL_FUNCTIONS','\n'.join(parts)));subprocess.run(['cc','-std=c99','-DPORTABLE','-DEW_HOENN_MARKETS=1','-DEW_MARKET_REACTIONS=1','-fsanitize=undefined',str(d/'test.c'),'-o',str(d/'test')],check=True);subprocess.run([str(d/'test')],check=True)
 def test_no_extra_approval_or_private_sell_reporting(self):
  s=(NATIVE/'src/shop.c').read_text();self.assertIn('Share an anonymous item/count',s);self.assertIn('sCommunityPurchase ? sText_PublicPurchase',s);self.assertIn('sCommunityPurchase ? sText_PublicSinglePurchase',s);self.assertEqual(s.count('WorldMarket_Purchased('),1);self.assertIn('sCommunityPurchase = FALSE;\n    if (sVisitingShelf)',s);self.assertIn('WorldMarket_EndVisit();',s[s.index('void CreateWorldRetailMenu'):]);self.assertIn("'world.arrange_market_shelf'",(ROOT/'world/history_world_rules.py').read_text())
 def test_receipt_failure_is_not_a_committed_purchase(self):
  self.send('MK GET 2');before=self.s.revision
  self.db.execute("CREATE TRIGGER fail_report BEFORE INSERT ON hoenn_market_reports BEGIN SELECT RAISE(ABORT,'synthetic fault'); END")
  self.assertEqual(self.send(f'MK BUY 1 {self.first} 43 1'),'MK UNCONFIRMED 1\n');self.assertEqual(self.s.revision,before);self.assertEqual(self.db.execute("SELECT count(*) FROM history WHERE event='hoenn_market_purchase_reported'").fetchone()[0],0)
 def test_rule_cannot_take_another_actors_shelf(self):
  cap=types.SimpleNamespace(kinds=('canonical','world'),poll=None,arguments={'site':'str','items':'str','minutes':'int'},execute=m.configure)
  sys.modules['reaction_fixture.actor_runtime']=types.SimpleNamespace(CAPABILITIES={'world.arrange_market_shelf':cap},actor_records=lambda server:{'other':{'canonical':False,'status':'active'}})
  d=dict(event='hoenn_market_purchase_reported',where={'item':43},tool='world.arrange_market_shelf',args=dict(site='SlateportCity_Mart',items='[48]',minutes=60),cooldown=60,per_hour=1)
  with self.db:rules.publish(self.s,'other',{},dict(id='response',rule=json.dumps(d)))
  self.send('MK GET 2');self.send(f'MK BUY 1 {self.first} 43 1');self.assertEqual(rules.tick(self.s,now=time.time())['status'],'blocked');self.assertEqual(m.catalog(self.s)['active'][0]['items'],[43,114])
if __name__=='__main__':unittest.main()
