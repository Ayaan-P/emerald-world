/* Opt-in native battle consent flow for Expansion. No automatic acceptance.
 * This prototype supports single battles only; trade/co-op remain disabled. */
#include "global.h"
#include "global.fieldmap.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "menu.h"
#include "window.h"
#include "text.h"
#include "task.h"
#include "pokemon.h"
#include "battle.h"
#include "link.h"
#include "event_data.h"
#include "field_control_avatar.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "field_screen_effect.h"
#include "constants/characters.h"
#include "constants/cable_club.h"
#define PORTABLE 1
#include "platform/native_link.h"
#include "platform/link_transport.h"
#undef PORTABLE
#include <stdlib.h>
#include <string.h>

enum ActivityPhase { ACT_IDLE, ACT_MENU, ACT_INVITE, ACT_WAIT, ACT_CONNECT, ACT_BATTLE, ACT_RETURN };
static struct {
    enum ActivityPhase phase;
    u8 window, task;
    bool8 locked, outgoing;
    unsigned timer;
    u64 invite;
    char peer[25];
} sActivity = { .window = WINDOW_NONE, .task = TASK_NONE };

const char *ExpansionPeers_Facing(void);
int ExpansionActivity_StartBattle(unsigned mode);
void __real_FieldGetPlayerInput(struct FieldInput *input, u16 newKeys, u16 heldKeys);

static bool8 enabled(void)
{
    const char *p = getenv("EW_EXPERIMENTAL_EXPANSION_ACTIVITIES");
    return p && !strcmp(p, "1");
}
static bool8 field_context(void)
{
    return gMain.callback1 == CB1_Overworld && gMain.callback2 == CB2_Overworld
        && !gMain.inBattle && !gPaletteFade.active && !ScriptContext_IsEnabled()
        && !gWirelessCommType && gSaveBlock1Ptr && gSaveBlock2Ptr;
}
int ExpansionActivity_PresenceReady(void)
{
    if (!enabled() || !LinkTransport_Ready() || !field_context()) return 0;
    if (sActivity.phase >= ACT_CONNECT) return 0;
    return sActivity.locked || !ArePlayerFieldControlsLocked();
}
static bool8 party_ready(void)
{
    unsigned i;
    for (i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP)) return TRUE;
    return FALSE;
}
static void encode(u8 *out, const char *text)
{
    while (*text) {
        unsigned char c = *text++;
        if (c >= 'A' && c <= 'Z') *out++ = CHAR_A + c - 'A';
        else if (c >= 'a' && c <= 'z') *out++ = CHAR_a + c - 'a';
        else if (c >= '0' && c <= '9') *out++ = CHAR_0 + c - '0';
        else if (c == '-') *out++ = CHAR_HYPHEN;
        else *out++ = CHAR_SPACE;
    }
    *out = EOS;
}
static void close_menu(void)
{
    if (sActivity.task != TASK_NONE) { DestroyTask(sActivity.task); sActivity.task = TASK_NONE; }
    if (sActivity.window != WINDOW_NONE) {
        ClearStdWindowAndFrame(sActivity.window, TRUE);
        RemoveWindow(sActivity.window);
        sActivity.window = WINDOW_NONE;
    }
}
static void stop_activity(void)
{
    close_menu();
    if (NativeLink_IsActive()) { CloseLink(); NativeLink_Abort(); }
    if (sActivity.locked) { UnlockPlayerFieldControls(); UnfreezeObjectEvents(); }
    sActivity.locked = FALSE;
    sActivity.phase = ACT_IDLE;
    sActivity.outgoing = FALSE;
    sActivity.peer[0] = 0;
}
static void task_menu(u8 task)
{
    s8 choice;
    (void)task;
    if (!sActivity.timer++) return;
    choice = Menu_ProcessInputNoWrap();
    if (choice == MENU_NOTHING_CHOSEN) return;
    close_menu();
    if (sActivity.phase == ACT_INVITE) {
        if (choice != 0 || !party_ready()) {
            LinkTransport_Reject(sActivity.invite); stop_activity(); return;
        }
        if (!LinkTransport_Accept(sActivity.invite)) { stop_activity(); return; }
        sActivity.outgoing = FALSE;
    } else {
        if (choice != 0 || !party_ready() || !LinkTransport_Offer(sActivity.peer, NATIVE_LINK_SINGLE)) {
            stop_activity(); return;
        }
        sActivity.outgoing = TRUE;
    }
    sActivity.phase = ACT_WAIT;
    sActivity.timer = 0;
}
static bool8 show_menu(bool8 incoming)
{
    struct WindowTemplate window = {0, 1, 1, 28, 9, 15, 0x125};
    u8 text[64];
    sActivity.window = AddWindow(&window);
    if (sActivity.window == WINDOW_NONE) return FALSE;
    SetStandardWindowBorderStyle(sActivity.window, FALSE);
    encode(text, sActivity.peer);
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 0, TEXT_SKIP_DRAW, NULL);
    encode(text, incoming ? "Battle invitation" : "Battle this trainer");
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 16, TEXT_SKIP_DRAW, NULL);
    encode(text, incoming ? "Yes" : "Battle");
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 32, TEXT_SKIP_DRAW, NULL);
    encode(text, incoming ? "No" : "Cancel");
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 48, TEXT_SKIP_DRAW, NULL);
    InitMenuNormal(sActivity.window, FONT_NORMAL, 0, 32, 16, 2, 1);
    CopyWindowToVram(sActivity.window, COPYWIN_FULL);
    sActivity.task = CreateTask(task_menu, 80);
    if (sActivity.task == TASK_NONE) { close_menu(); return FALSE; }
    sActivity.timer = 0;
    return TRUE;
}
static bool8 begin_menu(const char *peer, bool8 incoming)
{
    size_t n;
    if (!enabled() || sActivity.phase != ACT_IDLE || !field_context()
        || ArePlayerFieldControlsLocked() || !LinkTransport_Ready() || !peer) return FALSE;
    n = strlen(peer);
    if (!n || n > 24) return FALSE;
    memcpy(sActivity.peer, peer, n + 1);
    LockPlayerFieldControls(); FreezeObjectEvents(); StopPlayerAvatar();
    sActivity.locked = TRUE;
    sActivity.phase = incoming ? ACT_INVITE : ACT_MENU;
    if (!show_menu(incoming)) { stop_activity(); return FALSE; }
    return TRUE;
}
void __wrap_FieldGetPlayerInput(struct FieldInput *input, u16 newKeys, u16 heldKeys)
{
    if (enabled() && (newKeys & A_BUTTON) && sActivity.phase == ACT_IDLE) {
        const char *peer = ExpansionPeers_Facing();
        if (peer && begin_menu(peer, FALSE)) newKeys &= ~A_BUTTON;
    }
    if (sActivity.phase != ACT_IDLE) { newKeys = 0; heldKeys = 0; }
    __real_FieldGetPlayerInput(input, newKeys, heldKeys);
}
void ExpansionActivity_ReturnToField(void)
{
    CloseLink(); NativeLink_Abort(); gFieldLinkPlayerCount = 0;
    SetMainCallback1(CB1_Overworld); ScriptContext_Init();
    UnlockPlayerFieldControls(); UnfreezeObjectEvents(); sActivity.locked = FALSE;
    gFieldCallback = FieldCB_WarpExitFadeFromBlack; gFieldCallback2 = NULL;
    sActivity.phase = ACT_RETURN;
    SetMainCallback2(CB2_ReturnToField);
}
void ExpansionActivity_Update(void)
{
    const struct LinkTransportInvitation *pending;
    if (!enabled()) return;
    if (sActivity.phase == ACT_IDLE) {
        pending = LinkTransport_PendingInvitation();
        if (!pending) return;
        if (pending->mode != NATIVE_LINK_SINGLE || !party_ready()
            || !begin_menu(pending->name, TRUE)) { LinkTransport_Reject(pending->id); return; }
        sActivity.invite = pending->id;
        return;
    }
    if (sActivity.phase == ACT_MENU || sActivity.phase == ACT_INVITE) {
        if (!field_context() || !LinkTransport_Ready()) { stop_activity(); return; }
        if (sActivity.phase == ACT_INVITE) {
            pending = LinkTransport_PendingInvitation();
            if (!pending || pending->id != sActivity.invite) stop_activity();
        }
        return;
    }
    if (sActivity.phase == ACT_WAIT) {
        if (!field_context() || !party_ready() || !LinkTransport_Ready() || ++sActivity.timer > 1800
            || (sActivity.outgoing && !LinkTransport_OfferPending() && !NativeLink_IsActive())) {
            stop_activity(); return;
        }
        if (!NativeLink_IsActive()) return;
        gWirelessCommType = 0; gLinkType = LINKTYPE_SINGLE_BATTLE;
        OpenLink(); ResetLinkPlayers();
        sActivity.phase = ACT_CONNECT; sActivity.timer = 0;
        return;
    }
    if (sActivity.phase == ACT_CONNECT) {
        if (!NativeLink_IsActive() || HasLinkErrorOccurred() || ++sActivity.timer > 1200) { stop_activity(); return; }
        if (GetLinkPlayerCount_2() == 2 && IsLinkMaster() && !gReceivedRemoteLinkPlayers) CheckShouldAdvanceLinkState();
        if (!gReceivedRemoteLinkPlayers || !IsLinkPlayerDataExchangeComplete()) return;
        gFieldLinkPlayerCount = 2; gLocalLinkPlayerId = GetMultiplayerId(); SaveLinkPlayers(2);
        SetDynamicWarp(0, gSaveBlock1Ptr->location.mapGroup, gSaveBlock1Ptr->location.mapNum, -1);
        ClearLinkCallback_2(); close_menu(); sActivity.phase = ACT_BATTLE;
        if (!ExpansionActivity_StartBattle(NATIVE_LINK_SINGLE)) stop_activity();
        return;
    }
    if (sActivity.phase == ACT_BATTLE) {
        if (gMain.callback2 == CB2_ReturnToFieldFromMultiplayer) ExpansionActivity_ReturnToField();
        return;
    }
    if (sActivity.phase == ACT_RETURN && field_context()) sActivity.phase = ACT_IDLE;
}
