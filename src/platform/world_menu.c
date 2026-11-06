#ifdef PORTABLE
#include "platform/world_chat.h"
#include "global.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "menu.h"
#include "window.h"
#include "text.h"
#include "fieldmap.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "event_data.h"
#include "battle_setup.h"
#include "pokemon.h"
#include "link.h"
#include "dexnav.h"
#include "platform/dexnav_native.h"
#include "platform/native_link.h"
#include "platform/world_activity.h"
#include "platform/world_bridge.h"
#include "platform/world_menu.h"
#include "platform/generated_map.h"
#include "platform/world_rally.h"
#include "platform/world_travel.h"
#include "constants/characters.h"
#include "constants/flags.h"
#include "constants/map_groups.h"
#include "constants/opponents.h"
#include <stdio.h>
#include <string.h>

/* One field window, not another Start-menu row or another input consumer.
 * Lists are rebuilt from live state, but focus is an action identity. */
enum MenuState { CLOSED, OPEN_REQUEST, FEATURES, RALLY, DISPATCH };
#define GEN_EXPLORE_LABEL "Explore generated area"
#define GEN_LEAVE_LABEL "Leave generated area"
enum Action { FRIENDS, STORY, DEXNAV, GUILDS, BACK, MODE, SCOPE, REQUEST, READY,
    LATER, CANCEL, GO, FINISH, RETURN, STAY,
#if GENERATED_MAP_READY
    GEN_CAVE,
#endif
    ACTION_COUNT };
enum Page { CONTROLS, ROSTER, STATUS, PAGE_COUNT };
enum { WORLD_MENU_WIDTH = 28, WORLD_MENU_HEIGHT = 18, LINE_HEIGHT = 12,
    SCREEN_LINES = WORLD_MENU_HEIGHT * 8 / LINE_HEIGHT, TEXT_BYTES = 96 };
struct Row { enum Action action; const char *label, *reason; };
struct Screen { char lines[SCREEN_LINES][TEXT_BYTES]; };
static const struct WindowTemplate sWindow = {0, 1, 1, WORLD_MENU_WIDTH, WORLD_MENU_HEIGHT, 15, 0x125};
static struct {
    enum MenuState state;
    enum Page page;
    enum Action focus, pending;
    unsigned scope, pendingScope, pendingId, freeFrames, group, num;
    bool8 locked, delay, dirty, offerPending;
    u8 window;
    const char *notice;
    struct Screen drawn;
} sMenu = {.window = WINDOW_NONE};

static bool8 FieldContext(void)
{
    return gSaveBlock1Ptr && gSaveBlock2Ptr && gMain.callback1 == CB1_Overworld
        && gMain.callback2 == CB2_Overworld && !gMain.inBattle && !gPaletteFade.active
        && !ScriptContext_IsEnabled() && !gPlayerAvatar.tileTransitionState
        && !gWirelessCommType && !IsOverworldLinkActive() && !NativeLink_IsActive()
        && !WorldActivity_OwnsFieldInput() && !WorldTravel_OwnsFieldInput()
        && !WorldTravel_NativeFlyRunning();
}

static bool8 FreeField(void)
{
    return FieldContext() && !ArePlayerFieldControlsLocked();
}

static void Forget(void)
{
    /* A scene replacement can reuse both window IDs and the global field lock.
     * Neither belongs to us any more. Never tear down the replacement UI. */
    sMenu.window = WINDOW_NONE;
    sMenu.locked = FALSE;
    sMenu.state = CLOSED;
}

static void Close(void)
{
    if (sMenu.window != WINDOW_NONE)
    {
        ClearStdWindowAndFrame(sMenu.window, TRUE);
        RemoveWindow(sMenu.window);
        sMenu.window = WINDOW_NONE;
    }
    if (sMenu.locked)
    {
        UnlockPlayerFieldControls();
        UnfreezeObjectEvents();
        sMenu.locked = FALSE;
    }
    sMenu.state = CLOSED;
}

/* Explain only locally observable prerequisites. The backend still owns final
 * ledger, geometry, presence freshness and server acceptance checks. */
static const char *PersonalReason(void)
{
    unsigned i;
    if (FlagGet(FLAG_BADGE01_GET) || FlagGet(FLAG_DEFEATED_RUSTBORO_GYM)
        || HasTrainerBeenFought(TRAINER_ROXANNE_1))
        return "Your save already cleared Roxanne. This first scene is unavailable.";
    if (VarGet(VAR_RUSTBORO_CITY_STATE) != 0)
        return "Finish your Rustboro story event first.";
    if (!FlagGet(FLAG_VISITED_RUSTBORO_CITY)) return "Visit Rustboro on your own save first.";
    if (!HasTrainerBeenFought(TRAINER_JOSH) || !HasTrainerBeenFought(TRAINER_TOMMY)
        || !HasTrainerBeenFought(TRAINER_MARC))
        return "Defeat all three Rustboro Gym trainers on your own save first.";
    for (i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP)) return NULL;
    return "You need a conscious Pokemon that is not an Egg.";
}

static const char *ApproachReason(void)
{
    const struct ObjectEvent *player;
    if (gSaveBlock1Ptr->location.mapGroup != MAP_GROUP(MAP_RUSTBORO_CITY_GYM)
        || gSaveBlock1Ptr->location.mapNum != MAP_NUM(MAP_RUSTBORO_CITY_GYM))
        return "Stand at Roxanne's approach in Rustboro Gym.";
    if (gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return "Your field position is unavailable.";
    player = &gObjectEvents[gPlayerAvatar.objectEventId];
    if (!player->active || !player->isPlayer || player->currentCoords.x != 5 + MAP_OFFSET
        || player->currentCoords.y != 3 + MAP_OFFSET || player->currentElevation != ELEVATION_DEFAULT)
        return "Stand directly below Roxanne at Gym tile 5,3.";
    return NULL;
}

static unsigned MemberState(const struct WorldRallySnapshot *r)
{
    unsigned i;
    for (i = 0; i < r->count && i < WORLD_RALLY_ROSTER; i++)
        if (!strcmp(r->members[i].name, WorldBridge_TrainerName())) return r->members[i].state;
    return 0;
}

static void AddRow(struct Row *rows, unsigned *count, enum Action action,
                   const char *label, const char *reason)
{
    rows[(*count)++] = (struct Row){action, label, reason};
}

#if GENERATED_MAP_READY
static const char *GeneratedAreaReason(void)
{
    struct WorldRallySnapshot rally = {0};
    if (GeneratedMap_IsInside() || GeneratedMap_CanEnter()) return NULL;
    if (!GeneratedMap_HasUsableParty()) return "You need a conscious Pokemon that is not an Egg.";
    if (!IsMapTypeOutdoors(gMapHeader.mapType)) return "Go outdoors before entering a generated area.";
    if (!TestPlayerAvatarFlags(PLAYER_AVATAR_FLAG_ON_FOOT)) return "Get off your Bike or stop Surfing first.";
    if (WorldRally_HasReturn() || (WorldRally_GetSnapshot(&rally) && rally.id))
        return "Finish your rally and return before exploring another area.";
    if (WorldBridge_Enabled() && !WorldBridge_GeneratedCaveReady())
        return "No shared area is ready. Select an area in the launcher and wait for it to arrive.";
    return "Finish the current activity and stand on safe ground before exploring.";
}
#endif

static unsigned Rows(struct Row *rows, struct WorldRallySnapshot *r, bool8 online)
{
    unsigned n = 0, member = MemberState(r);
    bool8 owner = online && r->id && !strcmp(r->owner, WorldBridge_TrainerName());
    bool8 anchor = WorldRally_HasReturn();
    const char *personal = PersonalReason();
    const char *network = online ? NULL : "No fresh rally snapshot. Connect to a rally-enabled world.";
    const char *eligible = network ? network : personal;
    const char *approach = eligible ? eligible : ApproachReason();
    if (sMenu.state == FEATURES)
    {
#if GENERATED_MAP_READY
        if (GeneratedMap_IsInside()) {
            AddRow(rows, &n, GEN_CAVE, GEN_LEAVE_LABEL, NULL);
            AddRow(rows, &n, BACK, "Back", NULL);
            return n;
        }
#endif
        AddRow(rows, &n, FRIENDS, "Friends", WorldBridge_Enabled() ? NULL : "Connect to a world to visit friends.");
        AddRow(rows, &n, GUILDS, "Guilds", WorldBridge_Enabled() && WORLD_CHAT_HEIGHT ? NULL : "Connect to a world with chat available.");
        AddRow(rows, &n, STORY, "Story rally", NULL);
        AddRow(rows, &n, DEXNAV, "DexNav", DexNavNative_Available() ? NULL :
            "DexNav needs a Pokedex and conscious party outside restricted or link areas.");
#if GENERATED_MAP_READY
        AddRow(rows, &n, GEN_CAVE, GEN_EXPLORE_LABEL, GeneratedAreaReason());
#endif
        AddRow(rows, &n, BACK, "Back", NULL);
        return n;
    }
    AddRow(rows, &n, MODE, WorldRally_GetAutoJoin() ? "Mode AUTO-JOIN" : "Mode ASK", NULL);
    AddRow(rows, &n, SCOPE, sMenu.scope ? "Scope World" : "Scope Nearby", r->id ?
        "Scope applies to your next request. It cannot change a running rally." : NULL);
    if (!r->id)
    {
        AddRow(rows, &n, REQUEST, "Request Roxanne", sMenu.offerPending ?
            "A local request was queued. Check backend status or cancel it before retrying." :
            anchor ? "Return or Stay before requesting another rally." : approach);
        if (sMenu.offerPending) AddRow(rows, &n, CANCEL, "Cancel pending request", NULL);
    }
    else if (r->phase == WORLD_RALLY_GATHER)
    {
        AddRow(rows, &n, READY, "Ready", anchor ? "A return is still pending." : eligible);
        AddRow(rows, &n, LATER, "Not yet", network);
        AddRow(rows, &n, CANCEL, owner ? "Cancel rally" : "Leave rally", network);
        if (owner) AddRow(rows, &n, GO, "Go on", approach);
    }
    else if (r->phase == WORLD_RALLY_TRAVEL || r->phase == WORLD_RALLY_ACTIVE)
    {
        if (owner) AddRow(rows, &n, FINISH, "Finish rally", network);
        if (!(anchor && member == WORLD_RALLY_RETURNING))
            AddRow(rows, &n, RETURN, anchor ? "Return" : "Leave rally", network);
    }
    if (anchor && (!r->id || r->phase == WORLD_RALLY_RETURN || member == WORLD_RALLY_RETURNING))
    {
        AddRow(rows, &n, RETURN, "Return", NULL);
        AddRow(rows, &n, STAY, "Stay here", r->id && member != WORLD_RALLY_RETURNING ?
            "Wait for your returning state before choosing Stay." : NULL);
    }
    AddRow(rows, &n, BACK, "Back", NULL);
    return n;
}

static u8 EncodeChar(unsigned char c)
{
    if (c >= 'A' && c <= 'Z') return CHAR_A + c - 'A';
    if (c >= 'a' && c <= 'z') return CHAR_a + c - 'a';
    if (c >= '0' && c <= '9') return CHAR_0 + c - '0';
    switch (c)
    {
    case '.': return CHAR_PERIOD;
    case ',': return CHAR_COMMA;
    case '-': return CHAR_HYPHEN;
    case '?': return CHAR_QUESTION_MARK;
    case ':': return CHAR_COLON;
    case '/': return CHAR_SLASH;
    case '\'': return CHAR_SGL_QUOTE_RIGHT;
    case '>': return CHAR_RIGHT_ARROW;
    default: return CHAR_SPACE;
    }
}

static void Encode(u8 *dest, const char *text)
{
    for (; *text; text++) *dest++ = EncodeChar(*text);
    *dest = EOS;
}

static void Line(struct Screen *screen, unsigned row, const char *text)
{
    if (row < SCREEN_LINES) snprintf(screen->lines[row], TEXT_BYTES, "%s", text);
}

static void Wrap(struct Screen *screen, unsigned row, unsigned end, const char *text)
{
    /* Measure actual native glyphs, including long unbroken trainer names.
     * Never pass arbitrary server bytes to the game's text control decoder. */
    while (*text && row < end && row < SCREEN_LINES)
    {
        char line[TEXT_BYTES] = {0};
        u8 encoded[TEXT_BYTES];
        unsigned n = 0, space = 0;
        while (text[n] && text[n] != '\n' && n + 1 < sizeof(line))
        {
            line[n] = text[n];
            line[n + 1] = 0;
            Encode(encoded, line);
            if (GetStringWidth(FONT_SMALL, encoded, 0) > WORLD_MENU_WIDTH * 8 - 16) break;
            if (text[n] == ' ') space = n;
            n++;
        }
        if (text[n] && text[n] != '\n' && space) n = space;
        if (!n) n = 1;
        line[n] = 0;
        Line(screen, row++, line);
        text += n;
        while (*text == ' ' || *text == '\n') text++;
    }
}

static void Draw(const struct Row *rows, unsigned count, unsigned selected,
                 const struct WorldRallySnapshot *r, bool8 online)
{
    static const char *const phases[] = {"No rally", "Gathering", "Travelling", "Active", "Returning"};
    static const char *const states[] = {"Unknown", "Invited", "Ready", "Not yet", "Moving",
        "Arrived", "Returning", "Staying", "Left"};
    struct Screen screen = {0};
    char text[TEXT_BYTES];
    u8 encoded[TEXT_BYTES];
    unsigned i;
    if (sMenu.state == FEATURES)
    {
        Line(&screen, 0, "WORLD");
        Line(&screen, 1, "Up/Down choose. A open. B close.");
    }
    else
    {
        snprintf(text, sizeof(text), "Roxanne   %s", online ? phases[r->phase <= WORLD_RALLY_RETURN ? r->phase : 0] : "Offline");
        Line(&screen, 0, text);
        Line(&screen, 1, "Left/Right controls roster status");
    }
    if (sMenu.state == FEATURES || sMenu.page == CONTROLS)
    {
        for (i = 0; i < count; i++)
        {
            snprintf(text, sizeof(text), "%s%s%s", i == selected ? "> " : "  ",
                rows[i].reason ? "X " : "", rows[i].label);
            Line(&screen, 2 + i, text);
        }
        Wrap(&screen, 9, SCREEN_LINES, rows[selected].reason ? rows[selected].reason :
            sMenu.notice ? sMenu.notice : sMenu.focus == GO ?
            "Go on leaves invited, not-yet and busy guests behind." :
            sMenu.focus == MODE ? "AUTO-JOIN still checks your own save and free field. ASK never auto-accepts." :
            sMenu.focus == FINISH ? "Ends the visit. Only the encounter owner earns boss credit." :
            sMenu.focus == STAY ? "Keep this position and discard your pre-rally return point." :
            sMenu.focus == STORY ? "Roxanne visit for up to four trainers. Normal two-player battles. Boss credit stays personal." :
#if GENERATED_MAP_READY
            sMenu.focus == GEN_CAVE ? (GeneratedMap_IsInside() ?
                "Return to where you entered. Save after returning. Adventure conversations restart on a new visit." :
                "Explore the active area selected in your launcher. Face a character and press A to talk.") :
#endif
            "A choose. B back. Check status for local requirements.");
    }
    else if (sMenu.page == ROSTER)
    {
        snprintf(text, sizeof(text), "Owner %s", r->id ? r->owner : "none");
        Line(&screen, 2, text);
        snprintf(text, sizeof(text), "Scope %s", r->id ? (r->scope ? "World" : "Nearby") : "not requested");
        Line(&screen, 3, text);
        for (i = 0; i < r->count && i < WORLD_RALLY_ROSTER; i++)
        {
            Line(&screen, 4 + i * 2, r->members[i].name);
            snprintf(text, sizeof(text), "  Slot %u  %s", r->members[i].slot + 1,
                states[r->members[i].state <= WORLD_RALLY_LEFT ? r->members[i].state : 0]);
            Line(&screen, 5 + i * 2, text);
        }
    }
    else
    {
        Line(&screen, 2, "Backend status");
        Wrap(&screen, 3, 7, WorldRally_Status());
        Line(&screen, 7, WorldRally_HasReturn() ? "Your return point is recorded." : "No return point is recorded.");
        Wrap(&screen, 8, SCREEN_LINES, sMenu.notice ? sMenu.notice : PersonalReason() ? PersonalReason() :
            "Local story checks pass. Backend checks private return storage, safe ground and fresh presence after closing.");
    }
    if (!sMenu.dirty && !memcmp(&screen, &sMenu.drawn, sizeof(screen))) return;
    FillWindowPixelBuffer(sMenu.window, PIXEL_FILL(1));
    for (i = 0; i < SCREEN_LINES; i++)
    {
        Encode(encoded, screen.lines[i]);
        AddTextPrinterParameterized(sMenu.window, FONT_SMALL, encoded, 8, i * LINE_HEIGHT, TEXT_SKIP_DRAW, NULL);
    }
    CopyWindowToVram(sMenu.window, COPYWIN_FULL);
    sMenu.drawn = screen;
    sMenu.dirty = FALSE;
}

static void Queue(enum Action action, unsigned id)
{
    sMenu.pending = action;
    sMenu.pendingId = id;
    sMenu.pendingScope = sMenu.scope;
    Close();
    sMenu.state = DISPATCH;
    sMenu.freeFrames = 0;
    sMenu.notice = "Waiting for the free field. No rally approval has been received.";
}

static void Dispatch(void)
{
    struct WorldRallySnapshot r = {0};
    struct Row rows[ACTION_COUNT];
    bool8 accepted = FALSE, online;
    unsigned action, i, count;
    /* Human input always wins. Do not replay a deferred click after another
     * menu, script, battle, trade or field transition has taken ownership. */
    if (JOY_NEW(A_BUTTON | B_BUTTON | START_BUTTON | SELECT_BUTTON | L_BUTTON | R_BUTTON | DPAD_ANY)
        || JOY_HELD(DPAD_ANY))
    {
        sMenu.state = CLOSED;
        sMenu.notice = "Choice cancelled by field input. Open WORLD to try again.";
        return;
    }
    if (!FreeField() || JOY_HELD(A_BUTTON | B_BUTTON | L_BUTTON | R_BUTTON))
    { sMenu.freeFrames = 0; return; }
    /* The first free frame lets the bridge restore its ordinary local field
     * presence. This is not server readiness. Request/Ready/Go still use the
     * backend's fresh report queue and normal STATE publication intervals. */
    if (++sMenu.freeFrames < 2) return;
    sMenu.state = CLOSED;
#if GENERATED_MAP_READY
    if (sMenu.pending == GEN_CAVE)
    {
        accepted = GeneratedMap_IsInside() ? GeneratedMap_Leave() : GeneratedMap_Enter();
        sMenu.notice = accepted ? NULL : "Generated area unavailable in this field state.";
        return;
    }
#endif
    if (sMenu.pending == FRIENDS) { WorldTravel_RequestMenu(); return; }
    if (sMenu.pending == GUILDS)
    {
        accepted = WorldChat_OpenGuild();
        sMenu.notice = accepted ? NULL : "Guild chat is unavailable right now.";
        return;
    }
    if (sMenu.pending == DEXNAV)
    {
        accepted = DexNav_RequestOpen();
        sMenu.notice = accepted ? NULL : "DexNav is unavailable in the current field state.";
        return;
    }
    online = WorldRally_GetSnapshot(&r);
    if (r.id != sMenu.pendingId || (!online && sMenu.pending != RETURN && sMenu.pending != STAY
        && !(sMenu.pending == CANCEL && sMenu.offerPending)))
    {
        sMenu.notice = "Rally changed or disconnected. Review it before choosing again.";
        return;
    }
    /* Identity alone is insufficient: ownership, phase, personal state and
     * available recovery choices may have changed since the button press. */
    count = Rows(rows, &r, online);
    for (i = 0; i < count && rows[i].action != sMenu.pending; i++);
    if (i == count || rows[i].reason)
    {
        sMenu.notice = i == count ? "That choice is no longer available. Review the live rally." : rows[i].reason;
        return;
    }
    switch (sMenu.pending)
    {
    case REQUEST:
        accepted = WorldRally_Request(WORLD_RALLY_ROXANNE, sMenu.pendingScope);
        if (accepted) sMenu.offerPending = TRUE;
        break;
    case READY: action = WORLD_RALLY_ACCEPT; goto choose;
    case LATER: action = WORLD_RALLY_LATER; goto choose;
    case CANCEL: action = WORLD_RALLY_CANCEL; goto choose;
    case GO: action = WORLD_RALLY_GO; goto choose;
    case FINISH: action = WORLD_RALLY_FINISH; goto choose;
    case RETURN: action = WORLD_RALLY_BACK; goto choose;
    case STAY: action = WORLD_RALLY_KEEP;
choose:
        accepted = WorldRally_Choose(action);
        break;
    default: break;
    }
    if (sMenu.pending == CANCEL) sMenu.offerPending = FALSE;
    sMenu.notice = accepted ? "Choice queued locally. Check live roster and backend status for the result." :
        "Choice not accepted. Check backend status, personal eligibility and private return storage. No approval is implied.";
}

void WorldMenu_RequestOpen(void)
{
    if (sMenu.state == CLOSED) sMenu.state = OPEN_REQUEST;
}

bool8 WorldMenu_OwnsFieldInput(void)
{
    return sMenu.state != CLOSED;
}

void WorldMenu_Update(void)
{
    struct WorldRallySnapshot r = {0};
    struct Row rows[ACTION_COUNT];
    unsigned count, selected;
    bool8 online;
    if (sMenu.state == CLOSED) return;
    if (sMenu.state == DISPATCH) { Dispatch(); return; }
    if (sMenu.state == OPEN_REQUEST)
    {
        if (!FreeField()) { Forget(); return; }
        sMenu.group = gSaveBlock1Ptr->location.mapGroup;
        sMenu.num = gSaveBlock1Ptr->location.mapNum;
        sMenu.window = AddWindow(&sWindow);
        if (sMenu.window == WINDOW_NONE) { Forget(); return; }
        LockPlayerFieldControls();
        FreezeObjectEvents();
        sMenu.locked = TRUE;
        SetStandardWindowBorderStyle(sMenu.window, FALSE);
        sMenu.state = FEATURES;
        sMenu.focus = STORY;
        sMenu.delay = sMenu.dirty = TRUE;
    }
    if (!FieldContext() || !ArePlayerFieldControlsLocked()
        || sMenu.group != (unsigned)gSaveBlock1Ptr->location.mapGroup
        || sMenu.num != (unsigned)gSaveBlock1Ptr->location.mapNum)
    {
        Forget();
        return;
    }
    online = WorldRally_GetSnapshot(&r);
    count = Rows(rows, &r, online);
    if (online && r.id) sMenu.offerPending = FALSE;
    for (selected = 0; selected < count && rows[selected].action != sMenu.focus; selected++);
    if (selected == count) { selected = count - 1; sMenu.focus = BACK; }
    if (sMenu.delay) { sMenu.delay = FALSE; Draw(rows, count, selected, &r, online); return; }
    if (JOY_NEW(B_BUTTON))
    {
        if (sMenu.state == FEATURES) { Close(); return; }
        sMenu.state = FEATURES;
        sMenu.focus = STORY;
        sMenu.dirty = TRUE;
        return;
    }
    if (sMenu.state == RALLY && JOY_NEW(DPAD_LEFT | DPAD_RIGHT))
    {
        sMenu.page = (sMenu.page + (JOY_NEW(DPAD_LEFT) ? PAGE_COUNT - 1 : 1)) % PAGE_COUNT;
        sMenu.dirty = TRUE;
    }
    if (sMenu.state == FEATURES || sMenu.page == CONTROLS)
    {
        if (JOY_REPEAT(DPAD_UP) && selected) selected--;
        if (JOY_REPEAT(DPAD_DOWN) && selected + 1 < count) selected++;
        sMenu.focus = rows[selected].action;
        if (JOY_NEW(A_BUTTON))
        {
            if (rows[selected].reason) { sMenu.notice = rows[selected].reason; }
            else if (sMenu.focus == BACK)
            {
                if (sMenu.state == FEATURES) { Close(); return; }
                sMenu.state = FEATURES;
                sMenu.focus = STORY;
                sMenu.dirty = TRUE;
                return;
            }
            else if (sMenu.focus == STORY)
            {
                sMenu.state = RALLY;
                sMenu.page = CONTROLS;
                sMenu.focus = MODE;
                sMenu.dirty = TRUE;
                return;
            }
            else if (sMenu.focus == MODE) WorldRally_SetAutoJoin(!WorldRally_GetAutoJoin());
            else if (sMenu.focus == SCOPE) sMenu.scope ^= 1;
            else { Queue(sMenu.focus, r.id); return; }
            /* Labels/reasons can change after a local mode or scope toggle. */
            count = Rows(rows, &r, online);
        }
    }
    Draw(rows, count, selected, &r, online);
}
#endif

