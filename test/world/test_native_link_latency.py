"""Production cable scheduling under deterministic 150ms (nine tick) latency."""
import unittest
import test_native_link


class NativeLinkLatencyTests(unittest.TestCase):
    run_c = test_native_link.NativeLinkTests.run_c

    def test_wan_burst_streams_without_one_rtt_per_command(self):
        self.run_c(r'''
static struct NativeLinkEvent wire[128];
static unsigned issued, tick, due[128];
static int emit(void *c,const struct NativeLinkEvent *e) {
 (void)c;
 if(e->kind==NATIVE_LINK_COMMAND) {
  assert(issued<128);wire[issued]=*e;due[issued++]=tick+9;
 }
 return 1;
}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 unsigned delivered=0, consumed=0;
 NativeLink_Init(emit,0);assert(NativeLink_Admit(99,NATIVE_LINK_SINGLE,1));
 NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,99,1,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,99,1,0,m)==1);
 for(tick=0;tick<45;tick++) {
  while(delivered<issued && due[delivered]<=tick) {
   memcpy(m[1],wire[delivered].command,sizeof(m[1]));
   assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,wire[delivered].round,m)==1);
   delivered++;
  }
  assert(NativeLink_BeforeFrame(send));
  NativeLink_Main1(&a,send,r);
  if(r[1][0]) { assert(r[1][1]==++consumed); }
  memset(send,0,sizeof(send));
  if(tick<14) {send[0]=0x8888;send[1]=tick+1;}
  NativeLink_AfterFrame();
  assert(NativeLink_IsActive());
 }
 assert(consumed==14);
 assert(NativeLink_SendQueueCount()==0);
 return 0;
}''')

    def test_capacity_overflow_close_reopen_and_ring_wrap(self):
        self.run_c(r'''
static struct NativeLinkEvent wire[512];
static unsigned issued, delivered;
static int emit(void *c,const struct NativeLinkEvent *e) {
 (void)c;if(e->kind==NATIVE_LINK_COMMAND) {assert(issued<512);wire[issued++]=*e;}return 1;
}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 NativeLink_Init(emit,0);assert(NativeLink_Admit(80,NATIVE_LINK_TRADE,1));
 NativeLink_Open(0x1111);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,80,1,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,80,1,0,m)==1);
 /* Consume bootstrap/idle then two full 50-command bursts, wrapping ring. */
 for(unsigned batch=0;batch<2;batch++) {
  for(unsigned i=1;i<=50;i++) {
   send[0]=0xbbbb;send[1]=batch*50+i;
   assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);
   NativeLink_AfterFrame();assert(NativeLink_SendQueueCount()==i);
  }
  memset(send,0,sizeof(send));
  unsigned received=0;
  for(unsigned steps=0;received<50 && steps<150;steps++) {
   assert(delivered<issued);
   memcpy(m[1],wire[delivered].command,sizeof(m[1]));
   assert(NativeLink_Feed(NATIVE_LINK_ROUND,80,1,wire[delivered++].round,m)==1);
   assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);
   if(r[1][0]) {
    assert(r[1][0]==0xbbbb && r[1][1]==batch*50+(++received));
   }
   assert(NativeLink_RecvQueueCount()==0);NativeLink_AfterFrame();
   assert(NativeLink_FrameReady());
  }
  assert(received==50);
 }
 assert(NativeLink_SendQueueCount()==0);
 send[0]=0xdddd;assert(NativeLink_BeforeFrame(send));
 NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 assert(NativeLink_SendQueueCount()==1);
 NativeLink_Close();assert(NativeLink_SendQueueCount()==0);
 NativeLink_Open(0x1111);assert(NativeLink_Generation()==2);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,80,1,wire[delivered-1].round,m)==0);
 memset(m,0,sizeof(m));
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,80,2,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,80,2,0,m)==1);
 assert(NativeLink_FrameReady());assert(wire[issued-1].generation==2 && wire[issued-1].round==0);
 for(unsigned i=0;i<8;i++)assert(wire[issued-1].command[i]==0);
 for(unsigned i=0;i<50;i++) {
  send[0]=0xcccc;send[1]=i;
  assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 }
 assert(NativeLink_SendQueueCount()==50);
 assert(NativeLink_BeforeFrame(send)); /* 51st must abort, not overwrite */
 assert(!NativeLink_IsActive());
 assert(NativeLink_SendQueueCount()==0 && NativeLink_RecvQueueCount()==0);
 assert(NativeLink_Admit(81,NATIVE_LINK_TRADE,1));NativeLink_Open(0x1111);
 memset(m,0,sizeof(m));assert(NativeLink_Feed(NATIVE_LINK_PAIR,81,1,0,m)==1);
 assert(NativeLink_FrameReady());assert(wire[issued-1].command[0]==0);
 return 0;
}''')


    def test_window_bounds_and_ordered_receive(self):
        self.run_c(r'''
static struct NativeLinkEvent wire[32];
static unsigned issued;
static int emit(void *c,const struct NativeLinkEvent *e) {
 (void)c;if(e->kind==NATIVE_LINK_COMMAND) {assert(issued<32);wire[issued++]=*e;}return 1;
}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 NativeLink_Init(emit,0);assert(NativeLink_Admit(99,NATIVE_LINK_SINGLE,1));
 NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,99,1,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,99,1,0,m)==1);
 for(unsigned tick=0;tick<40;tick++) {
  assert(NativeLink_BeforeFrame(send));
  NativeLink_FrameReady();NativeLink_FrameReady();
  assert(NativeLink_Main1(&a,send,r)&0x100);
  NativeLink_AfterFrame();
 }
 assert(issued==16); /* Bounded even when the peer stops producing data. */
 m[0][0]=0x8888;m[0][1]=2;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,1,m)==1);
 assert(NativeLink_RecvQueueCount()==1);
 assert(NativeLink_BeforeFrame(send));
 assert(NativeLink_Main1(&a,send,r)&0x100); /* Never expose a future round early. */
 NativeLink_AfterFrame();
 m[0][1]=1;
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,0,m)==1);
 assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);
 assert(r[0][1]==1);assert(NativeLink_RecvQueueCount()==1);
 assert(NativeLink_Main1(&a,send,r)&0x100); /* No duplicate delivery this tick. */
 NativeLink_AfterFrame();
 assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);
 assert(r[0][1]==2);NativeLink_AfterFrame();
 assert(NativeLink_RecvQueueCount()==0);
 m[1][0]=1; /* Forged self echo in an actually issued future slot must abort. */
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,4,m)==-1);
 assert(!NativeLink_IsActive());
 return 0;
}''')

    def test_close_validates_late_window_without_delivering_it(self):
        self.run_c(r'''
static int emit(void *c,const struct NativeLinkEvent *e) {(void)c;(void)e;return 1;}
int main(void) {
 uint16_t send[8]={0},m[2][8]={{0}},r[5][8];uint8_t a=0;
 NativeLink_Init(emit,0);assert(NativeLink_Admit(99,NATIVE_LINK_SINGLE,1));
 NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_PAIR,99,1,0,m)==1);
 assert(NativeLink_Feed(NATIVE_LINK_HANDSHAKE,99,1,0,m)==1);
 for(unsigned tick=0;tick<16;tick++) {
  assert(NativeLink_BeforeFrame(send));NativeLink_Main1(&a,send,r);NativeLink_AfterFrame();
 }
 NativeLink_Close();
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,15,m)==0);
 assert(NativeLink_RecvQueueCount()==0 && NativeLink_SendQueueCount()==0);
 NativeLink_Open(0x2233);
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,1,15,m)==0);
 assert(NativeLink_Generation()==2 && NativeLink_IsActive());
 assert(NativeLink_Feed(NATIVE_LINK_ROUND,99,2,15,m)==-1); /* Not issued here. */
 return 0;
}''')
