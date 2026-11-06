"""Generated caves allow co-op invitations but reject other native activities."""
from pathlib import Path
from test_save_isolation import function
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
class CaveActivityGuard(unittest.TestCase):
 def test_rejects_pending_only_inside(self):
  src=(ROOT/'src/platform/world_activity.c').read_text()
  code=r'''
#include <assert.h>
typedef int bool8;
#define TRUE 1
#define FALSE 0
enum NativeLinkMode {NATIVE_LINK_SINGLE=1,NATIVE_LINK_DOUBLE,NATIVE_LINK_TRADE,NATIVE_LINK_COOP};
struct LinkTransportInvitation{unsigned long long id;int mode;};
static struct LinkTransportInvitation tag={10,NATIVE_LINK_COOP},invite={20,NATIVE_LINK_SINGLE};static int inside,tagRejected,inviteRejected;
int GeneratedMap_IsInside(void){return inside;}
const struct LinkTransportInvitation *LinkTransport_PendingTag(void){return &tag;}
const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void){return &invite;}
void LinkTransport_TagReject(unsigned long long x){assert(x==10);tagRejected++;}
void LinkTransport_Reject(unsigned long long x){assert(x==20);inviteRejected++;}
'''+function(src,'RejectGeneratedCaveInvitations')+r'''
int main(void){
 assert(!RejectGeneratedCaveInvitations()&&!tagRejected&&!inviteRejected);
 inside=1;
 for(int mode=NATIVE_LINK_SINGLE;mode<=NATIVE_LINK_TRADE;mode++){
  invite.mode=mode;
  assert(!RejectGeneratedCaveInvitations()&&!tagRejected&&inviteRejected==mode);
 }
 invite.mode=NATIVE_LINK_COOP;
 assert(!RejectGeneratedCaveInvitations()&&!tagRejected&&inviteRejected==3);
 return 0;
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
