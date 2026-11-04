#ifdef PORTABLE
#include "global.h"
#include "main.h"
#include "link.h"
#include "menu.h"
#include "overworld.h"
#include "palette.h"
#include "pokemon.h"
#include "battle.h"
#include "battle_setup.h"
#include "event_data.h"
#include "constants/cable_club.h"
#include "script.h"
#include "task.h"
#include "trade.h"
#include "window.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "field_screen_effect.h"
#include "constants/characters.h"
#include "constants/maps.h"
#include "platform/native_link.h"
#include "platform/link_transport.h"
#include "platform/world_activity.h"
#include "platform/world_coop.h"
#include <string.h>

enum { IDLE, MENU, INVITATION, WAIT_ADMIT, CONNECTING, NATIVE, RETURNING, WAIT_TAG };
static struct {
    unsigned state, mode, timer;
    u8 window, task;
    bool8 locked;
    bool8 tagInvitation, encounterPending, wildCaptured, trainerCaptured;
    bool8 encounterOfferDeferred;
    MainCallback trainerCallback;
    char peer[25], talkPeer[25];
    uint64_t invitation;
    const char *status;
} sActivity = { .window = WINDOW_NONE, .task = TASK_NONE, .status = "idle" };

static int CopyPeer(char dest[25], const char *source)
{
    unsigned i;
    if (!source) return 0;
    for (i = 0; i < 25; i++)
    {
        unsigned char c = source[i];
        if (!c) { if (!i) return 0; memcpy(dest, source, i + 1); return 1; }
        if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
           || (c >= '0' && c <= '9') || c == '_' || c == '-')) return 0;
    }
    return 0;
}

static bool8 FieldReady(void)
{
    return gMain.callback1 == CB1_Overworld && gMain.callback2 == CB2_Overworld
        && !gMain.inBattle && !gPaletteFade.active && !ScriptContext_IsEnabled()
        && !ArePlayerFieldControlsLocked() && !gWirelessCommType;
}

static bool8 ActivityPartyReady(unsigned mode)
{
    unsigned i, usable = 0;
    if (mode == NATIVE_LINK_TRADE) return gPlayerPartyCount > 0;
    for (i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP)) usable++;
    return usable >= (mode == NATIVE_LINK_DOUBLE ? 2 : 1);
}

/* Storage preparation is local and precedes consent. Never send box contents
 * through the party-only trade exchange or open storage during that exchange. */
static bool8 TradeStorageLocation(u8 mapGroup, u8 mapNum)
{
    switch ((mapGroup << 8) | mapNum)
    {
    case MAP_OLDALE_TOWN_POKEMON_CENTER_1F:
    case MAP_DEWFORD_TOWN_POKEMON_CENTER_1F:
    case MAP_LAVARIDGE_TOWN_POKEMON_CENTER_1F:
    case MAP_FALLARBOR_TOWN_POKEMON_CENTER_1F:
    case MAP_VERDANTURF_TOWN_POKEMON_CENTER_1F:
    case MAP_PACIFIDLOG_TOWN_POKEMON_CENTER_1F:
    case MAP_PETALBURG_CITY_POKEMON_CENTER_1F:
    case MAP_SLATEPORT_CITY_POKEMON_CENTER_1F:
    case MAP_MAUVILLE_CITY_POKEMON_CENTER_1F:
    case MAP_RUSTBORO_CITY_POKEMON_CENTER_1F:
    case MAP_FORTREE_CITY_POKEMON_CENTER_1F:
    case MAP_LILYCOVE_CITY_POKEMON_CENTER_1F:
    case MAP_MOSSDEEP_CITY_POKEMON_CENTER_1F:
    case MAP_SOOTOPOLIS_CITY_POKEMON_CENTER_1F:
    case MAP_EVER_GRANDE_CITY_POKEMON_CENTER_1F:
    case MAP_BATTLE_FRONTIER_POKEMON_CENTER_1F:
        return TRUE;
    default:
        return FALSE;
    }
}

static bool8 TradeStorageFieldReady(void)
{
    return sActivity.state == MENU && FieldReady() && !NativeLink_IsActive();
}

extern const u8 WorldActivity_EventScript_StoragePC[];

/* Native charmap, never feed wire bytes to the text control-code parser. */
static void Encode(u8 *dest, const char *src)
{
    while (*src)
    {
        unsigned char c = *src++;
        if (c >= 'A' && c <= 'Z') *dest++ = CHAR_A + c - 'A';
        else if (c >= 'a' && c <= 'z') *dest++ = CHAR_a + c - 'a';
        else if (c >= '0' && c <= '9') *dest++ = CHAR_0 + c - '0';
        else if (c == '-') *dest++ = CHAR_HYPHEN;
        else *dest++ = CHAR_SPACE;
    }
    *dest = EOS;
}

static void CloseMenu(void)
{
    if (sActivity.task != TASK_NONE)
    {
        DestroyTask(sActivity.task);
        sActivity.task = TASK_NONE;
    }
    if (sActivity.window != WINDOW_NONE)
    {
        ClearStdWindowAndFrame(sActivity.window, TRUE);
        RemoveWindow(sActivity.window);
        sActivity.window = WINDOW_NONE;
    }
}

static void ShowWaiting(const char *message)
{
    struct WindowTemplate window = { 0, 1, 1, 28, 6, 15, 0x125 };
    u8 text[64];
    CloseMenu();
    sActivity.window = AddWindow(&window);
    if (sActivity.window == WINDOW_NONE) return;
    SetStandardWindowBorderStyle(sActivity.window, FALSE);
    Encode(text, sActivity.peer);
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 0, TEXT_SKIP_DRAW, NULL);
    Encode(text, message);
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 24, TEXT_SKIP_DRAW, NULL);
    CopyWindowToVram(sActivity.window, COPYWIN_FULL);
}

static void Stop(const char *status)
{
    bool8 resumeWild = sActivity.wildCaptured;
    bool8 resumeTrainer = sActivity.trainerCaptured;
    CloseMenu();
    if (NativeLink_IsActive()) NativeLink_Abort();
    if (sActivity.locked)
    {
        CloseLink();
        if (!resumeTrainer)
        {
            UnlockPlayerFieldControls();
            if (sActivity.encounterPending) UnfreezeObjectEvents();
        }
        sActivity.locked = FALSE;
    }
    sActivity.state = IDLE;
    sActivity.status = status;
    sActivity.encounterPending = sActivity.wildCaptured = sActivity.tagInvitation = FALSE;
    sActivity.trainerCaptured = FALSE;
    sActivity.encounterOfferDeferred = FALSE;
    if (resumeTrainer)
    {
        gMain.savedCallback = sActivity.trainerCallback;
        BattleSetup_ResumeWorldTrainerBattle();
        sActivity.trainerCallback = NULL;
    }
    else if (resumeWild) BattleSetup_ResumeWorldWildBattle();
}

static void Task_Menu(u8 taskId)
{
    s8 choice;
    (void)taskId;
    if (!sActivity.timer++) return; /* opening A is not a selection */
    choice = Menu_ProcessInputNoWrap();
    if (choice == MENU_NOTHING_CHOSEN) return;
    if (sActivity.state == INVITATION)
    {
        uint64_t id = sActivity.invitation;
        CloseMenu();
        if (sActivity.tagInvitation)
        {
            if (choice != 0) { LinkTransport_TagReject(id); Stop("tag declined"); return; }
            if (!FieldReady() || !ActivityPartyReady(NATIVE_LINK_COOP) || !LinkTransport_TagAccept(id))
            { LinkTransport_TagReject(id); Stop("tag unavailable"); return; }
            Stop("tag accepted");
            return;
        }
        if (choice != 0) { LinkTransport_Reject(id); Stop("invitation declined"); return; }
        if (!FieldReady() || !ActivityPartyReady(sActivity.mode) || !LinkTransport_Accept(id)) { Stop("invitation unavailable"); return; }
    }
    else
    {
        CloseMenu();
        if (choice < 0 || choice == 5) { Stop("cancelled"); return; }
        if (choice == 6)
        {
            if (!TradeStorageFieldReady()
                || !TradeStorageLocation(gSaveBlock1Ptr->location.mapGroup, gSaveBlock1Ptr->location.mapNum))
            { Stop("use the PC at a Pokemon Center"); return; }
            Stop("preparing trade party at Center PC");
            ScriptContext_SetupScript(WorldActivity_EventScript_StoragePC);
            return;
        }
        if (choice == 4)
        {
            if (LinkTransport_TagPeer())
            {
                LinkTransport_TagEnd();
                Stop("tag ended");
                return;
            }
            if (!FieldReady() || !ActivityPartyReady(NATIVE_LINK_COOP) || !LinkTransport_TagOffer(sActivity.peer))
            { Stop("tag unavailable"); return; }
            sActivity.mode = NATIVE_LINK_COOP;
            sActivity.state = WAIT_TAG;
            sActivity.timer = 0;
            sActivity.status = "waiting for tag reply";
            ShowWaiting("Waiting for tag reply");
            return;
        }
        if (choice == 0)
        {
            Stop("world chat handoff");
            strcpy(sActivity.talkPeer, sActivity.peer);
            return;
        }
        sActivity.mode = choice; /* menu order matches NativeLinkMode */
        if (!FieldReady() || !ActivityPartyReady(sActivity.mode) || !LinkTransport_Offer(sActivity.peer, sActivity.mode))
        { Stop("peer unavailable"); return; }
    }
    sActivity.state = WAIT_ADMIT;
    sActivity.timer = 0;
    sActivity.status = "waiting for bilateral consent";
}

static bool8 ShowMenu(bool8 incoming)
{
    struct WindowTemplate window = { 0, 1, 0, 28, 20, 15, 0x125 };
    const char *labels[] = { "Talk", "Battle single", "Battle double", "Trade party", "Tag up (first 3 mons)", "Cancel", "Prepare party at Center PC" };
    const char *modes[] = { "", "Single battle invitation", "Double battle invitation", "Trade invitation", "Tag up invitation" };
    u8 text[64];
    unsigned i, count = incoming ? 2 : 6;
    if (!incoming && TradeStorageLocation(gSaveBlock1Ptr->location.mapGroup, gSaveBlock1Ptr->location.mapNum))
        count = 7;
    if (LinkTransport_TagPeer()) labels[4] = "End tag";
    sActivity.window = AddWindow(&window);
    if (sActivity.window == WINDOW_NONE) return FALSE;
    SetStandardWindowBorderStyle(sActivity.window, FALSE);
    Encode(text, sActivity.peer);
    AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 0, TEXT_SKIP_DRAW, NULL);
    if (incoming)
    {
        Encode(text, modes[sActivity.mode]);
        AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 16, TEXT_SKIP_DRAW, NULL);
    }
    for (i = 0; i < count; i++)
    {
        Encode(text, incoming ? (i ? "No" : "Yes") : labels[i]);
        AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 32 + 16 * i, TEXT_SKIP_DRAW, NULL);
    }
    InitMenuNormal(sActivity.window, FONT_NORMAL, 0, 32, 16, count, incoming ? 1 : 0);
    if (incoming && sActivity.tagInvitation)
    {
        Encode(text, "First 3 usable mons fight");
        AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 80, TEXT_SKIP_DRAW, NULL);
        Encode(text, "No bag or catches in a tag");
        AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 96, TEXT_SKIP_DRAW, NULL);
    }
    if (!incoming)
    {
        Encode(text, LinkTransport_TagPeer()
            ? (LinkTransport_TagInRange() ? "Tag: nearby; no bag or catches" : "Tag: get closer")
            : "Tag: no bag or catches");
        AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, count == 7 ? 144 : 128, TEXT_SKIP_DRAW, NULL);
        if (count == 6)
        {
            Encode(text, "PC mons at a Pokemon Center");
            AddTextPrinterParameterized(sActivity.window, FONT_NORMAL, text, 8, 144, TEXT_SKIP_DRAW, NULL);
        }
    }
    CopyWindowToVram(sActivity.window, COPYWIN_FULL);
    sActivity.task = CreateTask(Task_Menu, 80);
    if (sActivity.task == TASK_NONE) { CloseMenu(); return FALSE; }
    sActivity.timer = 0;
    return TRUE;
}

int WorldActivity_Interact(const char *peerName)
{
    if (sActivity.state != IDLE || !FieldReady() || !LinkTransport_Ready()
        || NativeLink_IsActive() || !CopyPeer(sActivity.peer, peerName)) return 0;
    sActivity.mode = 0;
    sActivity.tagInvitation = FALSE;
    sActivity.state = MENU;
    if (!ShowMenu(FALSE)) { Stop("native menu unavailable"); return 0; }
    sActivity.status = "peer menu";
    return 1;
}

int WorldActivity_OwnsFieldInput(void)
{
    return sActivity.state != IDLE;
}
unsigned short WorldActivity_FilterFieldKeys(unsigned short keys)
{
    return WorldActivity_OwnsFieldInput() ? 0 : keys;
}
const char *WorldActivity_Status(void) { return sActivity.status; }
const char *WorldActivity_Phase(void)
{
    static const char *const phases[] = { "idle", "menu", "invitation", "waiting", "connecting", "native", "returning", "tag_waiting" };
    return phases[sActivity.state];
}
unsigned WorldActivity_Mode(void) { return sActivity.state == IDLE ? 0 : sActivity.mode; }
int WorldActivity_TakeTalkRequest(char peer[25])
{
    if (!sActivity.talkPeer[0]) return 0;
    strcpy(peer, sActivity.talkPeer);
    sActivity.talkPeer[0] = 0;
    return 1;
}


void WorldActivity_ReturnToField(void)
{
    /* An incomplete exchange is neither a victory nor a defeat. Discard the
     * suspended trainer script, rather than invoking its ordinary result
     * callback (which would white out or award local trainer progression). */
    sActivity.trainerCallback = NULL;
    sActivity.trainerCaptured = sActivity.encounterPending = FALSE;
    sActivity.wildCaptured = sActivity.encounterOfferDeferred = FALSE;
    CloseLink();
    NativeLink_Abort();
    gFieldLinkPlayerCount = 0;
    SetMainCallback1(CB1_Overworld);
    ScriptContext_Init();
    UnlockPlayerFieldControls();
    UnfreezeObjectEvents();
    sActivity.locked = FALSE;
    gFieldCallback = FieldCB_WarpExitFadeFromBlack;
    gFieldCallback2 = NULL;
    sActivity.state = RETURNING;
    sActivity.status = "returning to field";
    SetMainCallback2(CB2_ReturnToField);
}

int WorldActivity_IsEncounterPending(void)
{
    return sActivity.encounterPending
        && (sActivity.state == WAIT_ADMIT || sActivity.state == CONNECTING)
        && gMain.callback1 == CB1_Overworld && gMain.callback2 == CB2_Overworld
        && !gMain.inBattle && !gPaletteFade.active;
}

static int TryCoopBattle(bool8 trainer)
{
    const char *peer = LinkTransport_TagPeer();
    if (sActivity.state != IDLE || NativeLink_IsActive() || !peer
        || (!trainer && !LinkTransport_TagInRange()) || !LinkTransport_Ready()
        || !ActivityPartyReady(NATIVE_LINK_COOP)
        || gMain.callback1 != CB1_Overworld || gMain.callback2 != CB2_Overworld
        || gMain.inBattle || gPaletteFade.active || !CopyPeer(sActivity.peer, peer)) return 0;
    if (trainer)
    {
        if (!WorldCoop_CaptureTrainer()) return 0;
    }
    else
        WorldCoop_CaptureWild();
    /* Trainer dialogue legitimately revokes field readiness before this hook.
     * First suspend that recognized encounter so presence can refresh from the
     * real field object. Only then may the existing broker range/consent gate
     * authorize an offer; never treat a dialogue's cached RANGE 0 as solo play. */
    if (!trainer && !LinkTransport_Offer(sActivity.peer, NATIVE_LINK_COOP)) return 0;
    sActivity.encounterOfferDeferred = trainer;
    sActivity.mode = NATIVE_LINK_COOP;
    sActivity.encounterPending = TRUE;
    sActivity.wildCaptured = !trainer;
    sActivity.trainerCaptured = trainer;
    sActivity.trainerCallback = trainer ? gMain.savedCallback : NULL;
    sActivity.tagInvitation = FALSE;
    sActivity.state = WAIT_ADMIT;
    sActivity.timer = 0;
    sActivity.status = "joining tagged encounter";
    LockPlayerFieldControls();
    FreezeObjectEvents();
    StopPlayerAvatar();
    sActivity.locked = TRUE;
    ShowWaiting("Joining tagged encounter");
    return 1;
}

int WorldActivity_TryCoopWildBattle(void) { return TryCoopBattle(FALSE); }
int WorldActivity_TryCoopTrainerBattle(void) { return TryCoopBattle(TRUE); }

void WorldActivity_ReturnFromCoopWildBattle(void)
{
    MainCallback trainerCallback = sActivity.trainerCallback;
    bool8 trainer = WorldCoop_IsTrainer();
    u16 trainerId = WorldCoop_TrainerId();
    bool8 localScript;
    sActivity.trainerCallback = NULL;
    WorldCoop_Abort();
    CloseMenu();
    CloseLink();
    NativeLink_Abort();
    gFieldLinkPlayerCount = 0;
    SetMainCallback1(CB1_Overworld);
    localScript = trainerCallback == NULL && trainer && gBattleOutcome == B_OUTCOME_WON
        && BattleSetup_ResumeWorldTrainerScript(trainerId);
    if (trainerCallback == NULL && !localScript)
        ScriptContext_Init();
    /* The owner's suspended script still owns its field lock and NPCs. */
    if (trainerCallback == NULL && !localScript)
    {
        UnlockPlayerFieldControls();
        UnfreezeObjectEvents();
    }
    sActivity.locked = FALSE;
    sActivity.encounterPending = sActivity.wildCaptured = FALSE;
    sActivity.state = RETURNING;
    sActivity.status = "returning after tagged encounter";
    sActivity.trainerCaptured = FALSE;
    if (trainerCallback != NULL)
        trainerCallback();
    else if (!localScript)
    {
        if (trainer && gBattleOutcome == B_OUTCOME_WON)
        {
            BattleSetup_RegisterWorldTrainerInMatchCall(trainerId);
            SetTrainerFlag(trainerId);
        }
        BattleSetup_EndWorldWildBattle();
    }
}

void WorldActivity_Update(void)
{
    const struct LinkTransportInvitation *pending;
    if (sActivity.state == IDLE && NativeLink_IsActive() && LinkTransport_Mode() == NATIVE_LINK_COOP)
    {
        const char *peer = LinkTransport_TagPeer();
        if (!peer || !FieldReady() || !ActivityPartyReady(NATIVE_LINK_COOP) || !CopyPeer(sActivity.peer, peer))
        { Stop("tagged encounter unavailable"); return; }
        sActivity.mode = NATIVE_LINK_COOP;
        sActivity.encounterPending = TRUE;
        sActivity.wildCaptured = sActivity.tagInvitation = FALSE;
        sActivity.state = WAIT_ADMIT;
        sActivity.timer = 0;
        sActivity.status = "joining tagged encounter";
        ShowWaiting("Joining tagged encounter");
    }
    if (sActivity.state == IDLE)
    {
        pending = LinkTransport_PendingTag();
        if (pending)
        {
            if (!FieldReady() || !ActivityPartyReady(NATIVE_LINK_COOP) || !CopyPeer(sActivity.peer, pending->name))
            { LinkTransport_TagReject(pending->id); return; }
            sActivity.invitation = pending->id;
            sActivity.mode = NATIVE_LINK_COOP;
            sActivity.tagInvitation = TRUE;
            sActivity.state = INVITATION;
            sActivity.status = "incoming tag invitation";
            if (!ShowMenu(TRUE)) { LinkTransport_TagReject(sActivity.invitation); Stop("native menu unavailable"); }
            return;
        }
        pending = LinkTransport_PendingInvitation();
        if (!pending) return;
        /* Tag consent already authorizes co-op. Its OFFER and ADMIT can be in
         * different socket reads; do not turn the brief gap into a second UI. */
        if (pending->mode == NATIVE_LINK_COOP) return;
        if (!FieldReady() || pending->mode < NATIVE_LINK_SINGLE || pending->mode > NATIVE_LINK_TRADE
            || !CopyPeer(sActivity.peer, pending->name))
        { LinkTransport_Reject(pending->id); return; }
        sActivity.invitation = pending->id;
        sActivity.mode = pending->mode;
        sActivity.tagInvitation = FALSE;
        sActivity.state = INVITATION;
        sActivity.status = "incoming invitation";
        if (!ShowMenu(TRUE)) { LinkTransport_Reject(sActivity.invitation); Stop("native menu unavailable"); }
        return;
    }
    if (sActivity.state == MENU || sActivity.state == INVITATION)
    {
        if (!FieldReady()) { Stop("field became unavailable"); return; }
        if (sActivity.state == INVITATION)
        {
            pending = sActivity.tagInvitation ? LinkTransport_PendingTag() : LinkTransport_PendingInvitation();
            if (!pending || pending->id != sActivity.invitation) Stop("invitation expired");
        }
        return;
    }
    if (sActivity.state == WAIT_TAG)
    {
        const char *peer = LinkTransport_TagPeer();
        if (peer && !strcmp(peer, sActivity.peer)) { Stop("tag ready; stay nearby"); return; }
        if (!LinkTransport_Ready() || !LinkTransport_TagOfferPending() || ++sActivity.timer > 900)
            Stop("tag declined or expired");
        return;
    }
    if (sActivity.state == WAIT_ADMIT)
    {
        bool8 coop = sActivity.mode == NATIVE_LINK_COOP;
        if ((!FieldReady() && !(coop && WorldActivity_IsEncounterPending()))
            || !ActivityPartyReady(sActivity.mode) || !LinkTransport_Ready() || ++sActivity.timer > 1800)
        { Stop("consent unavailable"); return; }
        if (sActivity.encounterOfferDeferred)
        {
            const char *peer = LinkTransport_TagPeer();
            if (!peer || strcmp(peer, sActivity.peer))
            { Stop("tag unavailable; continuing trainer encounter"); return; }
            if (!NativeLink_IsActive())
            {
                if (!LinkTransport_TagInRange()) return;
                if (!LinkTransport_Offer(sActivity.peer, NATIVE_LINK_COOP))
                { Stop("partner unavailable; continuing trainer encounter"); return; }
            }
            sActivity.encounterOfferDeferred = FALSE;
        }
        if (coop && !NativeLink_IsActive() && !LinkTransport_OfferPending())
        { Stop("partner unavailable; continuing wild encounter"); return; }
        if (!NativeLink_IsActive()) return;
        /* Active means server ADMIT after BOTH decisions, not OFFER/ACCEPT. */
        LockPlayerFieldControls();
        if (coop) { FreezeObjectEvents(); StopPlayerAvatar(); }
        sActivity.locked = TRUE;
        gWirelessCommType = 0;
        gLinkType = coop ? 0x2255 : sActivity.mode == NATIVE_LINK_TRADE ? LINKTYPE_TRADE_SETUP
            : sActivity.mode == NATIVE_LINK_DOUBLE ? LINKTYPE_DOUBLE_BATTLE : LINKTYPE_SINGLE_BATTLE;
        OpenLink();
        ResetLinkPlayers();
        sActivity.state = CONNECTING;
        sActivity.timer = 0;
        sActivity.status = "exchanging native link players";
        return;
    }
    if (sActivity.state == CONNECTING)
    {
        if (!NativeLink_IsActive() || HasLinkErrorOccurred() || ++sActivity.timer > 1200)
        { Stop("native connection aborted before activity"); return; }
        if (GetLinkPlayerCount_2() == 2 && IsLinkMaster() && !gReceivedRemoteLinkPlayers)
            CheckShouldAdvanceLinkState();
        if (!gReceivedRemoteLinkPlayers || !IsLinkPlayerDataExchangeComplete()) return;
        gFieldLinkPlayerCount = 2;
        gLocalLinkPlayerId = GetMultiplayerId();
        SaveLinkPlayers(2);
        /* Native trade/battle saves use dynamicWarp for restart recovery. It
         * must name THIS field, never an old Pokemon Center cable entrance. */
        SetDynamicWarp(0, gSaveBlock1Ptr->location.mapGroup,
            gSaveBlock1Ptr->location.mapNum, -1);
        ClearLinkCallback_2();
        CloseMenu();
        sActivity.state = NATIVE;
        sActivity.status = "native activity running";
        if (sActivity.mode == NATIVE_LINK_COOP)
        {
            if (!WorldCoop_StartBattle(LinkTransport_CoopOwner()))
            { Stop("tagged battle unavailable"); return; }
            sActivity.wildCaptured = sActivity.encounterPending = FALSE;
            sActivity.trainerCaptured = FALSE;
            /* The kind is authenticated by the exchange, not by overworld presence. */
        }
        else if (sActivity.mode == NATIVE_LINK_TRADE)
        {
            gBattleTypeFlags = 0;
            gSpecialVar_0x8004 = USING_TRADE_CENTER;
            gSelectedTradeMonPositions[TRADE_PLAYER] = 0;
            gSelectedTradeMonPositions[TRADE_PARTNER] = 0;
            CleanupOverworldWindowsAndTilemaps();
            SetMainCallback2(CB2_StartCreateTradeMenu);
        }
        else if (!WorldActivity_StartNativeBattle(sActivity.mode))
            Stop("native battle task unavailable");
        return;
    }
    if (sActivity.state == NATIVE)
    {
        /* Trade's stock exit selects cable-map callback. Replace BEFORE it runs.
         * Battle helper routes its native post-battle save to our local return. */
        if (gMain.callback2 == CB2_ReturnToFieldFromMultiplayer)
            WorldActivity_ReturnToField();
        else if (!NativeLink_IsActive())
            sActivity.status = "native connection lost; reset required (no automatic save or rollback)";
        return;
    }
    if (sActivity.state == RETURNING && FieldReady())
    {
        sActivity.state = IDLE;
        sActivity.status = "native activity returned";
    }
}
#endif
