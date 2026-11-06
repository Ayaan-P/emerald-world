#ifndef ACTIVITY_STUB_H
#define ACTIVITY_STUB_H
#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32; typedef uint64_t u64; typedef int8_t s8; typedef uint8_t bool8; typedef void (*MainCallback)(void);
#define TRUE 1
#define FALSE 0
#define WINDOW_NONE 255
#define TASK_NONE 255
#define PARTY_SIZE 6
#define B_TRAINER_PLAYER 0
#define MON_DATA_SPECIES 1
#define MON_DATA_IS_EGG 2
#define MON_DATA_HP 3
#define CHAR_A 1
#define CHAR_a 30
#define CHAR_0 60
#define CHAR_HYPHEN 80
#define CHAR_SPACE 81
#define EOS 255
#define MENU_NOTHING_CHOSEN -2
#define FONT_NORMAL 1
#define TEXT_SKIP_DRAW 1
#define COPYWIN_FULL 1
#define A_BUTTON 1
#define LINKTYPE_SINGLE_BATTLE 0x2233
#define LINKTYPE_DOUBLE_BATTLE 0x2244
#define LINKTYPE_TRADE_SETUP 0x1111
#define USING_TRADE_CENTER 3
struct Pokemon { int species,hp,egg; };
extern struct Pokemon gParties[4][6]; extern u8 gPartiesCount[4];
struct Save1 { struct { int mapGroup,mapNum; } location; }; extern struct Save1 *gSaveBlock1Ptr; extern void *gSaveBlock2Ptr;
struct Main { MainCallback callback1,callback2; int inBattle; }; extern struct Main gMain;
struct PaletteFade { int active; }; extern struct PaletteFade gPaletteFade;
struct FieldInput { int unused; }; struct WindowTemplate { int bg,x,y,w,h,pal,base; };
extern u8 gWirelessCommType, gFieldLinkPlayerCount, gLocalLinkPlayerId, gReceivedRemoteLinkPlayers;
extern u16 gLinkType, gSpecialVar_0x8004; extern u32 gBattleTypeFlags; extern u8 gSelectedTradeMonPositions[2]; extern void (*gFieldCallback)(void); extern bool8 (*gFieldCallback2)(void);
void CB2_StartCreateTradeMenu(void); void CleanupOverworldWindowsAndTilemaps(void);
void CB1_Overworld(void); void CB2_Overworld(void); void CB2_ReturnToField(void); void CB2_ReturnToFieldFromMultiplayer(void); void FieldCB_WarpExitFadeFromBlack(void);
int ScriptContext_IsEnabled(void); int ArePlayerFieldControlsLocked(void); void LockPlayerFieldControls(void); void UnlockPlayerFieldControls(void); void ScriptContext_Init(void);
void FreezeObjectEvents(void); void UnfreezeObjectEvents(void); void StopPlayerAvatar(void);
int GetMonData(struct Pokemon *, int); u8 AddWindow(const struct WindowTemplate *); void SetStandardWindowBorderStyle(u8,int);
void AddTextPrinterParameterized(u8,int,const u8 *,int,int,int,void *); void InitMenuNormal(u8,int,int,int,int,int,int); void CopyWindowToVram(u8,int);
void ClearStdWindowAndFrame(u8,int); void RemoveWindow(u8); u8 CreateTask(void (*)(u8), int); void DestroyTask(u8); s8 Menu_ProcessInputNoWrap(void);
void CloseLink(void); void OpenLink(void); void ResetLinkPlayers(void); int HasLinkErrorOccurred(void); int GetLinkPlayerCount_2(void); int IsLinkMaster(void); void CheckShouldAdvanceLinkState(void); int IsLinkPlayerDataExchangeComplete(void); u8 GetMultiplayerId(void); void SaveLinkPlayers(int); void SetDynamicWarp(int,int,int,int); void ClearLinkCallback_2(void); void SetMainCallback1(MainCallback); void SetMainCallback2(MainCallback);
#endif
