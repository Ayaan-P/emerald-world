"""Exercise actual six-roster controller sequencing with explicit fake transport."""
from pathlib import Path
import subprocess,tempfile,unittest
from test_save_isolation import function
ROOT=Path(__file__).resolve().parents[2]
class SixActionSequence(unittest.TestCase):
 def test_both_owners_acknowledge_before_switch_and_preserve_exp(self):
  fixture=(ROOT/'test/world/coop_engine_core.c').read_text()
  fixture=fixture.replace('../../src/platform/world_coop.c',str(ROOT/'src/platform/world_coop.c'))
  fixture=fixture.replace(function(fixture,'PrepareBufferDataTransferLink'),r'''
static u8 testWire[128];static u16 testWireSize;
void PrepareBufferDataTransferLink(u8 id,u16 size,u8 *data){
 assert(id==B_COMM_TO_CONTROLLER && size<=112);testWireSize=size;memset(testWire,0,sizeof(testWire));memcpy(testWire,data,size);
}''')
  fixture=fixture.replace('void MarkBattlerForControllerExec(u8 battler) {}',
                          'void MarkBattlerForControllerExec(u8 battler) { (void)battler; gBattleControllerExecFlags=1; }')
  code='#define main CoreFixtureMain\n'+fixture+'\n#undef main\n'+r'''
int main(void){
 for(u8 owner=0;owner<2;owner++){
  u8 reply[WORLD_COOP_ROSTER_REPLY_SIZE],order[3]={0x10,0x32,0x54};
  struct Pokemon original[6];u8 battler=owner*2,stage=owner*3+1;
  Reset(owner,owner==0);Exchange();WorldCoop_InitControllers();memcpy(original,sCoop.original,sizeof(original));
  gActiveBattler=battler;assert(WorldCoop_BeginFullPartyMenu());assert(WorldCoop_ChooseFullPartyMenu(5));
  u8 choice=WorldCoop_FullPartyChoiceReply();WorldCoop_EndFullPartyMenu();
  gBattlersCount=4;gAbsentBattlerFlags=0;gBattlerPartyIndexes[1]=0;gBattlerPartyIndexes[3]=4;
  gSentPokesToOpponent[0]=(1u<<stage)|(1u<<(owner*3));
  gSentPokesToOpponent[1]=(1u<<stage);
  assert(WorldCoop_BeginRosterAction(battler,choice,order)==0 && testWireSize==16 && gBattleControllerExecFlags);
  assert(WorldCoop_RosterRequestValid(testWire,20));assert(WorldCoop_AdvanceRosterAction(battler)==0);
  assert(WorldCoop_ApplyRosterRequest(testWire,reply));
  gBattleBufferB[battler][0]=CONTROLLER_DATATRANSFER;gBattleBufferB[battler][2]=sizeof(reply);gBattleBufferB[battler][3]=0;
  memcpy(&gBattleBufferB[battler][4],reply,sizeof(reply));gBattleControllerExecFlags=0;
  assert(WorldCoop_AdvanceRosterAction(battler)==0 && testWireSize==112 && gBattleControllerExecFlags);
  assert(WorldCoop_ApplyRosterMirror(testWire));assert(WorldCoop_AdvanceRosterAction(battler)==0);
  gBattleControllerExecFlags=0;assert(WorldCoop_AdvanceRosterAction(battler)==1);
  assert(gBattleBufferB[battler][0]==CONTROLLER_CHOSENMONRETURNVALUE && gBattleBufferB[battler][1]==stage);
  assert(!memcmp(&gBattleBufferB[battler][2],order,3));
  assert(!(gSentPokesToOpponent[0] & (1u<<stage)));
  assert(CoopRoster_RewardMask(&sCoop.roster,0,2)==((1u<<1)|(1u<<3)|(1u<<5)));
  assert(CoopRoster_RewardMask(&sCoop.roster,4,0)==(1u<<3));
  assert(!(gSentPokesToOpponent[1] & (1u<<stage)));
  assert(!WorldCoop_RosterRequestValid(NULL,20));
  sCoop.rosterAction=1;WorldCoop_Abort();assert(!sCoop.rosterAction);assert(!memcmp(gPlayerParty,original,sizeof(original)));
 }
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DCOOP_FULL_SIX_READY=1','-DUBFIX','-DVER_64BIT','-DNONMATCHING','-DMODERN=1','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
