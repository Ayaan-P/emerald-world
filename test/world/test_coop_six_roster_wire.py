"""Exercise actual six-roster request, owner reply and private mirror boundaries."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class SixRosterWireTests(unittest.TestCase):
 def test_both_owners_exchange_only_selected_mon_and_preserve_private_side(self):
  code=r'''
#define main CoreFixtureMain
#include "test/world/coop_engine_core.c"
#undef main
int main(void){
 for(u8 owner=0;owner<2;owner++){
  u8 request[20]={0},reply[WORLD_COOP_ROSTER_REPLY_SIZE],wire[116]={0};
  struct CoopRosterReply parsed;struct CoopRosterMirror mirror={0};struct Pokemon own[3];
  Reset(owner,owner==0);Exchange();WorldCoop_InitControllers();gActiveBattler=owner*2;
  assert(WorldCoop_BeginFullPartyMenu());assert(WorldCoop_ChooseFullPartyMenu(5));WorldCoop_EndFullPartyMenu();
  request[0]=CONTROLLER_EXPUPDATE;request[1]=WORLD_COOP_ROSTER_REQUEST_TAG;request[2]=owner+1;request[3]=5;
  u32 gen=NativeLink_Generation();memcpy(request+4,&gen,4);request[8]=owner*3+1;request[9]=2;request[15]=2;
  assert(WorldCoop_RosterRequestValid(request,20));
  request[18]=1;assert(!WorldCoop_RosterRequestValid(request,20));request[18]=0;
  request[2]=(owner^1)+1;assert(!WorldCoop_ApplyRosterRequest(request,reply));request[2]=owner+1;
  assert(WorldCoop_ApplyRosterRequest(request,reply));assert(!WorldCoop_ApplyRosterRequest(request,reply));
  assert(WorldCoop_RosterReplyValid(owner*2,reply,sizeof(reply)));memcpy(&parsed,reply,sizeof(parsed));
  struct CoopRosterReply bad=parsed;bad.owner=(owner^1)+1;
  assert(!WorldCoop_RosterReplyValid(owner*2,(u8 *)&bad,sizeof(bad)));
  bad=parsed;bad.stage=owner*3;assert(!WorldCoop_RosterReplyValid(owner*2,(u8 *)&bad,sizeof(bad)));
  bad=parsed;bad.hidden=4;assert(!WorldCoop_RosterReplyValid(owner*2,(u8 *)&bad,sizeof(bad)));
  bad=parsed;bad.mon.box.checksum++;assert(!WorldCoop_RosterReplyValid(owner*2,(u8 *)&bad,sizeof(bad)));
  assert(parsed.stage==owner*3+1 && parsed.mon.box.personality==sCoop.original[5].box.personality);
  assert((sCoop.roster.knockedOff & (1<<3)) && !(parsed.hidden & 2));
  assert(CoopRoster_RewardMask(&sCoop.roster,0,2)==((1<<3)|(1<<5)));
  mirror.command=CONTROLLER_EXPUPDATE;mirror.tag=WORLD_COOP_ROSTER_MIRROR_TAG;
  mirror.owner=parsed.owner;mirror.stage=parsed.stage;mirror.generation=gen;mirror.hidden=parsed.hidden;mirror.mon=parsed.mon;
  memcpy(wire,&mirror,sizeof(mirror));assert(WorldCoop_RosterMirrorValid(wire,sizeof(wire)));
  assert(WorldCoop_ApplyRosterMirror(wire));
  /* Even a structurally valid conflicting echo cannot overwrite the owner. */
  mirror.mon.hp--;memcpy(wire,&mirror,sizeof(mirror));assert(WorldCoop_RosterMirrorValid(wire,sizeof(wire)));
  assert(!WorldCoop_ApplyRosterMirror(wire));assert(gPlayerParty[parsed.stage].hp==parsed.mon.hp);
  mirror.mon=parsed.mon;memcpy(wire,&mirror,sizeof(mirror));
  /* On the other view, only the partner's staged slot changes. */
  sCoop.local=owner^1;memcpy(own,&gPlayerParty[sCoop.local*3],sizeof(own));
  memset(&gPlayerParty[parsed.stage],0,sizeof(struct Pokemon));
  assert(WorldCoop_ApplyRosterMirror(wire));assert(!memcmp(own,&gPlayerParty[sCoop.local*3],sizeof(own)));
  assert(!memcmp(&gPlayerParty[parsed.stage],&parsed.mon,sizeof(parsed.mon)));
 }
 return 0;
}'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   cmd=['cc','-std=gnu99','-DPORTABLE','-DCOOP_FULL_SIX_READY=1','-DUBFIX','-DVER_64BIT','-DNONMATCHING','-DMODERN=1','-iquote',str(ROOT/'include'),'-iquote',str(ROOT),str(p/'test.c'),'-o',str(p/'test')]
   q=subprocess.run(cmd,capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
