"""Native cleanup -> authenticated private report -> save-specific reflection."""
import json,os,re,subprocess,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from test_steven_companion import StevenCompanionTests
from world import canonical_cast as cast,canonical_partner_memory as memory
from world.canonical_reflection import snapshot

class PartnerMemoryTests(unittest.TestCase):
 def setUp(self):
  self.f=StevenCompanionTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.s=self.f.s;self.c=self.f.c
 def begin(self):
  cast.guild_command(self.s,self.c,['steven','remember','on'])
  response=cast.response(self.s,self.c,'a'*32,'steven')
  from world.canonical_memory import acknowledge
  acknowledge(self.s,self.c,'a'*32,'canon_steven',response['digest'],'MossdeepCity_StevensHouse')
  self.f.request()
 def finish(self,code='1',run='a'*32):
  return self.s.core_story.handle(self.c,['CORE',run,'ALLYEND','steven',code])
 def test_private_report_affects_only_one_time_same_save_reflection(self):
  self.begin();history=deepcopy(self.s.memory.history());state=deepcopy(self.s.module_state)
  self.assertTrue(self.finish()['ok'])
  self.assertEqual(self.s.memory.history(),history);self.assertEqual(self.s.module_state,state)
  self.assertEqual(snapshot(self.s,'Alice','canon_steven','a'*32)[2]['partner_encounters'][0]['outcome'],'won')
  self.assertNotIn('partner_encounters',snapshot(self.s,'Alice','canon_steven','a'*32,decision_only=True)[2])
  self.assertEqual(memory.context(self.s,'Alice','canon_steven','b'*32),[])
  self.assertEqual(memory.context(self.s,'Bob','canon_steven','a'*32),[])
  with self.assertRaises(ValueError):self.finish()
  self.s.close();self.f.f.f.case.server=self.f.f.f.case.open();self.s=self.f.f.f.case.server
  self.assertEqual(memory.context(self.s,'Alice','canon_steven','a'*32)[0]['outcome'],'won')
  from world.canonical_memory import forget
  with self.s.db:forget(self.s,self.c,'canon_steven')
  self.assertEqual(memory.context(self.s,'Alice','canon_steven','a'*32),[])
 def test_no_grant_wrong_save_or_withdrawal_never_store(self):
  cast.response(self.s,self.c,'a'*32,'steven');self.f.request()
  with self.assertRaises(ValueError):self.finish()
  self.begin()
  with self.assertRaises(ValueError):self.finish(run='b'*32)
  with self.assertRaises(ValueError):self.finish(code='128')
  cast.guild_command(self.s,self.c,['steven','remember','off'])
  cast.guild_command(self.s,self.c,['steven','remember','on'])
  with self.assertRaises(ValueError):self.finish()
  self.assertEqual(memory.context(self.s,'Alice','canon_steven','a'*32),[])
 @unittest.skipUnless(os.environ.get('EW_NATIVE_SOURCE'),'exact native source needed')
 def test_actual_native_cleanup_emits_single_private_report(self):
  native=Path(os.environ['EW_NATIVE_SOURCE']);test=(native/'tests/test_world_core_story.py').read_text()
  fixture=re.search(r"fixture=r'''(.*?)'''",test,re.S).group(1)
  source=re.sub(r'^#include .*\n','',(native/'src/world/world_core_story.c').read_text(),flags=re.M)
  checks=r'''
int main(void){
char *ready[]={"CORE","READY","1","12345678-1234-1234-1234-123456789abc"};
assert(WorldCoreStory_Line(4,ready));assert(Lineage());script=false;diveReceived=true;stevenState=2;
sCore.synced=0;sCore.mileSynced=0;sCore.incomingOff=TRUE;sCore.stevenUntil=100;
/* Quiesce the independent standing-battle mode read; this fixture isolates
 * duplicate private partner-result cleanup, not ordinary background sync. */
sCore.battleModeAsked=TRUE;
assert(WorldCoreStory_TakeStevenInvitation());gMain.inBattle=true;
WorldCoreStory_StevenFinished(1);sent[0]=0;WorldCoreStory_Update();assert(!sent[0]);
gMain.inBattle=false;WorldCoreStory_Update();assert(strstr(sent," ALLYEND steven 1 "));printf("%s",sent);
sCore.pending=0;sent[0]=0;WorldCoreStory_Update();assert(!sent[0]);
WorldCoreStory_StevenFinished(2);WorldCoreStory_Update();assert(!sent[0]);
sCore.stevenUntil=sCore.frame+100;assert(WorldCoreStory_TakeStevenInvitation());WorldCoreStory_Disconnected();
WorldCoreStory_StevenFinished(1);assert(!sCore.stevenReport);
return 0;}
'''
  with tempfile.TemporaryDirectory() as tmp:
   c=Path(tmp)/'paired.c';exe=Path(tmp)/'paired';c.write_text(fixture+source+checks)
   subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
   result=subprocess.run([str(exe)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr);line=result.stdout
  self.begin();self.c['out'].clear();self.s._line(self.c,line.strip().encode())
  self.assertIn('ALLYEND steven OK',self.c['out'].decode())
  self.assertNotIn('CHAT',self.c['out'].decode())
  self.assertEqual(memory.context(self.s,'Alice','canon_steven','a'*32)[0]['outcome'],'won')
