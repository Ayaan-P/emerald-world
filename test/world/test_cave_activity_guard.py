"""Incoming native invitations cannot enter activity while in a generated cave."""
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
struct LinkTransportInvitation{unsigned long long id;};
static struct LinkTransportInvitation tag={10},invite={20};static int inside,tagRejected,inviteRejected;
int GeneratedMap_IsInside(void){return inside;}
const struct LinkTransportInvitation *LinkTransport_PendingTag(void){return &tag;}
const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void){return &invite;}
void LinkTransport_TagReject(unsigned long long x){assert(x==10);tagRejected++;}
void LinkTransport_Reject(unsigned long long x){assert(x==20);inviteRejected++;}
'''+function(src,'RejectGeneratedCaveInvitations')+r'''
int main(void){assert(!RejectGeneratedCaveInvitations()&&!tagRejected&&!inviteRejected);inside=1;assert(RejectGeneratedCaveInvitations()&&tagRejected==1&&inviteRejected==1);return 0;}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.c').write_text(code)
   q=subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',str(p/'test.c'),'-o',str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
   q=subprocess.run([str(p/'test')],capture_output=True,text=True);self.assertEqual(q.returncode,0,q.stderr)
if __name__=='__main__':unittest.main()
