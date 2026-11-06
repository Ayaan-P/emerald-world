#include "stub.h"
#include "platform/link_transport.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
struct Pokemon gParties[4][6]={{{1,10,0}}}; u8 gPartiesCount[4]={1};
struct Save1 save; struct Save1 *gSaveBlock1Ptr=&save; int save2; void *gSaveBlock2Ptr=&save2;
struct Main gMain; struct PaletteFade gPaletteFade;
u8 gWirelessCommType,gFieldLinkPlayerCount,gLocalLinkPlayerId,gReceivedRemoteLinkPlayers; u16 gLinkType;
void (*gFieldCallback)(void); bool8 (*gFieldCallback2)(void);
static int locked, active, offered, offered_mode, accepted, rejected, offer_pending, started, choice, exchange, link_ready=1;
static u16 real_new,real_held; static void (*task_fn)(u8); static struct LinkTransportInvitation incoming;
void CB1_Overworld(void){} void CB2_Overworld(void){} void CB2_ReturnToField(void){} void CB2_ReturnToFieldFromMultiplayer(void){} void FieldCB_WarpExitFadeFromBlack(void){}
int ScriptContext_IsEnabled(void){return 0;} int ArePlayerFieldControlsLocked(void){return locked;} void LockPlayerFieldControls(void){locked=1;} void UnlockPlayerFieldControls(void){locked=0;} void ScriptContext_Init(void){}
void FreezeObjectEvents(void){} void UnfreezeObjectEvents(void){} void StopPlayerAvatar(void){}
int GetMonData(struct Pokemon *p,int f){return f==MON_DATA_SPECIES?p->species:f==MON_DATA_HP?p->hp:p->egg;}
u8 AddWindow(const struct WindowTemplate *w){(void)w;return 1;} void SetStandardWindowBorderStyle(u8 w,int c){(void)w;(void)c;}
void AddTextPrinterParameterized(u8 w,int f,const u8 *s,int x,int y,int v,void *cb){(void)w;(void)f;(void)s;(void)x;(void)y;(void)v;(void)cb;}
void InitMenuNormal(u8 w,int f,int x,int y,int h,int n,int c){(void)w;(void)f;(void)x;(void)y;(void)h;(void)n;(void)c;} void CopyWindowToVram(u8 w,int f){(void)w;(void)f;}
void ClearStdWindowAndFrame(u8 w,int c){(void)w;(void)c;} void RemoveWindow(u8 w){(void)w;} u8 CreateTask(void (*f)(u8),int priority){(void)priority;task_fn=f;return 2;} void DestroyTask(u8 t){(void)t;} s8 Menu_ProcessInputNoWrap(void){return choice;}
int NativeLink_IsActive(void){return active;} void NativeLink_Abort(void){active=0;} int LinkTransport_Ready(void){return link_ready;} int LinkTransport_Reject(u64 id){assert(id==22);rejected++;return 1;} int LinkTransport_Accept(u64 id){assert(id==22);accepted++;return 1;} int LinkTransport_Offer(const char *p,unsigned m){assert(!strcmp(p,"Bob")&&(m==1||m==2));offered++;offered_mode=m;offer_pending=1;return 1;} int LinkTransport_OfferPending(void){return offer_pending;} const struct LinkTransportInvitation *LinkTransport_PendingInvitation(void){return incoming.id?&incoming:0;}
void CloseLink(void){} void OpenLink(void){} void ResetLinkPlayers(void){} int HasLinkErrorOccurred(void){return 0;} int GetLinkPlayerCount_2(void){return 2;} int IsLinkMaster(void){return 1;} void CheckShouldAdvanceLinkState(void){} int IsLinkPlayerDataExchangeComplete(void){return exchange;} u8 GetMultiplayerId(void){return 0;} void SaveLinkPlayers(int n){assert(n==2);} void SetDynamicWarp(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;} void ClearLinkCallback_2(void){} void SetMainCallback1(MainCallback f){gMain.callback1=f;} void SetMainCallback2(MainCallback f){gMain.callback2=f;}
const char *ExpansionPeers_Facing(void){return "Bob";} int ExpansionActivity_StartBattle(unsigned m){assert(m==1);started++;return 1;}
void __real_FieldGetPlayerInput(struct FieldInput *i,u16 n,u16 h){(void)i;real_new=n;real_held=h;}
void __wrap_FieldGetPlayerInput(struct FieldInput *,u16,u16); void ExpansionActivity_Update(void); int ExpansionActivity_PresenceReady(void);
int main(void) {
 struct FieldInput input; assert(!setenv("EW_EXPERIMENTAL_EXPANSION_ACTIVITIES","1",1));
 gMain.callback1=CB1_Overworld;gMain.callback2=CB2_Overworld;
 assert(ExpansionActivity_PresenceReady());
 __wrap_FieldGetPlayerInput(&input,A_BUTTON,A_BUTTON); assert(locked && !real_new && !real_held && task_fn);
 assert(!offered && !accepted); choice=0; task_fn(2); task_fn(2); assert(offered==1 && offered_mode==1 && !accepted);
 assert(ExpansionActivity_PresenceReady()); active=1; offer_pending=0; ExpansionActivity_Update();
 assert(gLinkType==LINKTYPE_SINGLE_BATTLE && !started); gReceivedRemoteLinkPlayers=1; exchange=1;
 ExpansionActivity_Update(); assert(started==1 && gFieldLinkPlayerCount==2);
 gMain.callback2=CB2_ReturnToFieldFromMultiplayer; ExpansionActivity_Update(); assert(!locked && !active);
 gMain.callback2=CB2_Overworld; ExpansionActivity_Update(); incoming.id=22; incoming.mode=1; strcpy(incoming.name,"May");
 ExpansionActivity_Update(); assert(locked && !accepted && !rejected); choice=1; task_fn(2); task_fn(2);
 assert(rejected==1 && !accepted && !locked);
 incoming.id=0; ExpansionActivity_Update(); incoming.id=22; ExpansionActivity_Update();
 assert(locked && !accepted); choice=0; task_fn(2); task_fn(2); assert(accepted==1);
 link_ready=0; ExpansionActivity_Update(); assert(!locked); link_ready=1; incoming.id=0;
 gPartiesCount[0]=2; gParties[0][1].species=2; gParties[0][1].hp=10;
 __wrap_FieldGetPlayerInput(&input,A_BUTTON,A_BUTTON); assert(locked); choice=1; task_fn(2); task_fn(2);
 assert(offered==2 && offered_mode==2); return 0;
}
