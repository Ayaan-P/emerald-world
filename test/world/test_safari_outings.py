import json,unittest,time,subprocess,tempfile,os
from pathlib import Path
import test_character_offers as fixture
from world import safari_outings as outings
from world.build_catalog import catalog_maps

class SafariOutings(unittest.TestCase):
 def setUp(self):
  self.f=fixture.CharacterOfferTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.server
  self.a=self.f.peer('Alice','SOCIALCHATCOMMANDS1');self.a['campaign_run']='save_a'
  self.map=next(k for k,v in catalog_maps().items() if v['name'].startswith('SafariZone_'))
  self.a['state'][:2]=self.map
  self.c=dict(id='Alice',presence=self.a)
  with self.s.db:outings.publish(self.s,'field_researcher',{},dict(id='outing',title='A shared expedition',target=2,hours=1))
 def report(self,text):return outings.handle(self.s,self.c,text.encode())
 def join(self):
  answer=self.report('S JOIN 1 outing');self.assertTrue(answer.startswith('S ADMIT '),answer);return answer.split()[2]
 def test_actual_reports_and_public_aggregate_not_individuals(self):
  lease=self.join();self.assertEqual(self.report(f'S REPORT {lease} 1 1 0 0 30 500'),f'S ACK {lease} 1\n')
  self.report(f'S REPORT {lease} 2 2 1 1 29 490');before=self.s.memory.history()['through']
  self.report(f'S REPORT {lease} 2 2 1 1 29 490');self.assertEqual(self.s.memory.history()['through'],before)
  self.report(f'S REPORT {lease} 4 3 2 2 28 480')
  pending=outings.wait(self.s,'field_researcher',{},dict(id='outing'))
  self.assertEqual(outings.poll(self.s,'field_researcher',{},pending.data)['outcome'],'safari_target_reported')
  x=outings.summary(self.s,'outing');self.assertTrue(x['target_reported']);self.assertEqual(x['finished_visits'],1)
  event=self.s.memory.history();encoded=json.dumps(event)
  for private in ('Alice','save_a',lease):self.assertNotIn(private,encoded)
  self.assertIn('client_reported',encoded);self.assertIn('2/2',' '.join(outings.command(self.s,self.a,['outing'])))
 def test_no_consent_replay_forgery_lineage_or_wrong_location(self):
  self.assertIn('ERROR',self.report('S REPORT '+ 'a'*32+' 1 1 0 0 30 500'))
  lease=self.join();self.a['state'][:2]=[0,0]
  self.assertIn('WAIT',self.report(f'S REPORT {lease} 1 1 0 0 30 500'))
  self.a['state'][:2]=self.map
  self.assertIn('ERROR',self.report(f'S REPORT {lease} 2 2 3 1 29 490'))
  self.a['campaign_run']='save_b';self.assertIn('ERROR',self.report(f'S REPORT {lease} 1 1 0 0 30 500'))
  self.assertEqual(outings.summary(self.s,'outing')['reported_catches'],0)
 def test_stop_timeout_and_disconnect_never_complete(self):
  lease=self.join();self.report(f'S REPORT {lease} 2 2 1 1 29 490')
  self.report(f'S STOP {lease}')
  self.assertIn('ERROR',self.report(f'S REPORT {lease} 4 3 2 2 28 480'))
  self.assertEqual(outings.summary(self.s,'outing')['finished_visits'],0)
  self.assertIn('ERROR',self.report('S JOIN 1 outing'))
 def test_restart_durable_no_automatic_replay(self):
  lease=self.join();self.report(f'S REPORT {lease} 2 2 1 1 29 490')
  self.s.close();case=self.f.fixture.case;case.server=case.open();self.s=case.server;self.f.server=self.s
  self.c=dict(id='Alice',presence=self.a)
  self.assertIn('ERROR',self.report(f'S REPORT {lease} 4 3 2 2 28 480'))
  self.assertEqual(outings.summary(self.s,'outing')['reported_catches'],1)
  self.assertEqual(outings.summary(self.s,'outing')['finished_visits'],0)
 def test_two_independent_visits_and_actor_capability(self):
  from world.actor_runtime import CAPABILITIES
  self.assertIn('world.publish_safari_outing',CAPABILITIES)
  lease=self.join();self.report(f'S REPORT {lease} 3 3 1 1 29 490')
  b=self.f.peer('Bob','SOCIALCHATCOMMANDS1');b['campaign_run']='b';b['state'][:2]=self.map
  self.c=dict(id='Bob',presence=b);lease=self.join();self.report(f'S REPORT {lease} 4 3 1 2 28 480')
  x=outings.summary(self.s,'outing');self.assertEqual((x['participants'],x['finished_visits'],x['reported_catches']),(2,2,2))
 def test_authenticated_link_dispatch_and_private_chat_discovery(self):
  from test_link_delivery import Selector,Sock
  self.s.selector=Selector()
  channel=dict(self.c,sock=Sock(),link=True,closing=False,out=bytearray())
  self.s.connections[channel['sock']]=channel;self.s.link_channels['Alice']=channel
  self.s._link_line(channel,b'S JOIN 1 outing')
  self.assertTrue(bytes(channel['out']).startswith(b'S ADMIT '))
  lease=bytes(channel['out']).decode().split()[2];channel['out'].clear()
  self.s._link_line(channel,f'S REPORT {lease} 3 3 1 1 29 490'.encode())
  self.assertEqual(bytes(channel['out']),f'S ACK {lease} 3\n'.encode())
  self.a['chat_credit']=4
  self.s._line(self.a,f"CHAT {self.a['seq']+1} * {'/guild safari outing'.encode().hex()}".encode())
  lines=[bytes.fromhex(x[3]).decode() for x in self.a['chat_history']]
  self.assertTrue(any('Reported catches 1/2' in x for x in lines))
  self.s.connections.pop(channel['sock']);self.s.link_channels.clear()

 def test_cumulative_contradictions_rejected(self):
  lease=self.join();self.report(f'S REPORT {lease} 2 2 1 1 29 490')
  for values in ('3 2 0 2 28 480','3 2 2 2 30 480','3 2 2 2 28 499','2 2 2 2 28 480'):
   self.assertIn('ERROR',self.report('S REPORT '+lease+' '+values))
  self.assertEqual(outings.summary(self.s,'outing')['reported_catches'],1)

class NativeSafari(unittest.TestCase):
 def test_native_consent_codec_and_stock_wiring(self):
  root=Path(os.environ.get('EW_SAFARI_NATIVE_SOURCE','../native-safari-outings'))
  if not (root/'src/world/world_safari.c').exists():self.skipTest('native Safari source not present')
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'global.h').write_text('');(p/'platform').mkdir();(p/'platform/link_transport.h').write_text('int LinkTransport_Ready(void); int LinkTransport_SafariSend(const char *);')
   (p/'platform/world_safari.h').write_text((root/'include/platform/world_safari.h').read_text())
   (p/'safari_zone.h').write_text('int GetSafariZoneFlag(void);')
   (p/'main.c').write_text('''#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "platform/world_safari.h"
static int active; static char last[256];
int LinkTransport_Ready(void){return 1;}
int LinkTransport_SafariSend(const char *s){strcpy(last,s);return 1;}
int GetSafariZoneFlag(void){return active;}
int main(void){char hint[128];char *admit[]={"S","ADMIT","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"};char *ack[]={"S","ACK","aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","3"};
WorldSafari_Entered(30,500);WorldSafari_Pump();assert(!last[0]);
WorldSafari_Command("/safari outing not yes",hint,sizeof(hint));assert(!last[0]);
WorldSafari_Command("/safari outing yes",hint,sizeof(hint));assert(!strcmp(last,"S JOIN 1 outing\\n"));
assert(WorldSafari_Line(3,admit));active=1;WorldSafari_Entered(30,500);WorldSafari_Pump();puts(last);
WorldSafari_Battle(1,29,490);WorldSafari_Exited(29,490);for(int i=0;i<60;i++)WorldSafari_Pump();puts(last);
assert(strstr(last," 3 3 1 1 29 490"));assert(WorldSafari_Line(4,ack));
strcpy(last,"");WorldSafari_Entered(30,500);WorldSafari_Pump();assert(!last[0]);
WorldSafari_Reset();return 0;}
''')
   build=subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-DPORTABLE','-I'+str(p),str(root/'src/world/world_safari.c'),str(p/'main.c'),'-o',str(p/'test')],capture_output=True,text=True)
   self.assertEqual(build.returncode,0,build.stderr)
   run=subprocess.run([str(p/'test')],check=True,capture_output=True,text=True);self.assertIn('S REPORT',run.stdout)
   authority=SafariOutings();authority.setUp();self.addCleanup(authority.doCleanups);lease=authority.join()
   for line in run.stdout.splitlines():
    if line.startswith('S REPORT '):self.assertIn('S ACK',authority.report(line.replace('a'*32,lease)))
   self.assertEqual(outings.summary(authority.s,'outing')['finished_visits'],1)
  source=(root/'src/safari_zone.c').read_text()
  self.assertIn('WorldSafari_Battle(gBattleOutcome == B_OUTCOME_CAUGHT',source)
  self.assertIn('WorldSafari_Exited(gNumSafariBalls, gSafariZoneStepCounter)',source)
  wire=(root/'src/world/link_transport.c').read_text();self.assertIn('WorldSafari_Line(n,t)',wire);self.assertIn('WorldSafari_Reset();',wire)
