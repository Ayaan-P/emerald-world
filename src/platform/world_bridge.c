#ifdef PORTABLE
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <windows.h>
#endif
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include "platform/native_file.h"
#include "global.h"
#include "global.fieldmap.h"
#include "fieldmap.h"
#include "field_camera.h"
#include "metatile_behavior.h"
#include "event_object_movement.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "start_menu.h"
#include "task.h"
#include "field_message_box.h"
#include "pokemon.h"
#include "sprite.h"
#include "constants/event_objects.h"
#include "constants/map_groups.h"
#include "platform/world_bridge.h"
#include "platform/chat_command_gate.h"
#include "platform/generated_map.h"
#if GENERATED_MAP_READY
#include "platform/world_cave_wire.h"
#endif
#include "platform/world_activity.h"
#include "platform/world_travel.h"
#include "platform/world_rally.h"
#include "platform/world_menu.h"
#include "platform/world_catalog.h"
#ifndef _WIN32
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <poll.h>
#endif

/* A negotiated relevance window, not the server's total population.
 * The experimental native pool can request 32; older servers get 16 or eight. */
#define WB_PEERS 8
#if WORLD_EXTENDED_OBJECTS
#undef WB_PEERS
#define WB_PEERS 32
#endif
#define WB_TRAVEL_PEERS 63
#define WB_OBJECTS 8
#define WB_REMOTES (WB_PEERS + WB_OBJECTS)
#define WB_TILES 128
#define WB_BUFFER 65536
#define WB_HANDSHAKE_POLLS 300
#if WORLD_EXTENDED_OBJECTS
// 160..199 avoids the Berry Blender reserved local IDs 236..240.
#define WB_LOCALID 160
#else
#define WB_LOCALID 224
#endif
#define WB_MARKER 0x5742
#ifndef WORLD_SMOOTH_PRESENCE
#define WORLD_SMOOTH_PRESENCE 0
#endif

struct Peer { char id[26], text[58]; unsigned group, num, x, y, facing, gfx, ready; };
struct Tile { unsigned group, num, x, y, metatile, collision; };
struct Meeting { unsigned seq, group, num, x, y; char player[25], target[25]; };
struct ChatMessage { unsigned seq; char sender[25], target[25], text[121]; };
struct TravelPeer { struct Peer peer; unsigned ttl; };
struct Snapshot {
    unsigned revision, peerCount, tileCount, objectCount;
    struct Peer peers[WB_REMOTES];
    struct Tile tiles[WB_TILES];
    struct Meeting meeting;
    unsigned chatCount;
    unsigned commandMask, commandsSeen;
    char chatStatus[12];
    struct ChatMessage chat[16];
    bool8 travel;
    unsigned travelCount, travelExpected;
    struct TravelPeer friends[WB_TRAVEL_PEERS];
    bool8 rallySeen;
    unsigned rallyExpected;
    struct WorldRallySnapshot rally;
};
#if GENERATED_MAP_READY
enum CaveState { CAVE_DISABLED, CAVE_IDLE, CAVE_WAIT, CAVE_WAIT_RESET, CAVE_ACK, CAVE_WAIT_OK,
                 CAVE_READY, CAVE_MISMATCH, CAVE_RETURN_NONE };
#endif
struct Remote { char id[26]; u8 object, sprite, group, num;
#if WORLD_SMOOTH_PRESENCE
    s16 motionX, motionY;
    u8 motionDirection;
    bool8 walking;
#endif
};
struct Applied { struct Tile tile; u16 original, raw; };
static struct {
    bool8 enabled, connected, connecting, staging, chatProbe, chatLegacy, chatAvailable;
    bool8 commandsProbe, commandsLegacy;
    bool8 travelProbe, travelLegacy, travelAvailable;
    bool8 rallyProbe, rallyLegacy, rallyAvailable;
#if GENERATED_MAP_READY
    bool8 caveProbe, caveLegacy, caveAvailable, caveReturning;
#if GENERATED_WORLD_XL
    bool8 caveV10Probe, caveV10Legacy;
#endif
#if GENERATED_CAVE_PROFILES
    bool8 caveV2Probe, caveV2Legacy;
#if GENERATED_CAVE_WILDLIFE
    bool8 caveV3Probe, caveV3Legacy;
#if GENERATED_MAP_LARGE
    bool8 caveV4Probe, caveV4Legacy;
    bool8 caveV5Probe, caveV5Legacy;
#if GENERATED_MAP_WILDS
    bool8 caveV6Probe, caveV6Legacy;
#if GENERATED_WILDS_GUIDE
    bool8 caveV7Probe, caveV7Legacy;
#if GENERATED_WILDS_CAST
    bool8 caveV8Probe, caveV8Legacy;
#if GENERATED_WILDS_EVENTS
    bool8 caveV9Probe, caveV9Legacy;
#if GENERATED_WILDS_SHARED_TERRAIN
    bool8 caveV9TProbe, caveV9TLegacy, terrainPending, terrainReportPending, terrainReportedApplied;
#if GENERATED_WILDS_SHARED_GEOMETRY
    bool8 caveV9GProbe, caveV9GLegacy;
#if GENERATED_WILDS_LARGE_TERRAIN
    bool8 caveV9HProbe, caveV9HLegacy;u8 terrainRx[1539],terrainRxNext,terrainRxTotal;u16 terrainRxSize;u32 terrainRxRevision;
#endif
#endif
    u32 terrainRevision;u16 terrainSize;u8 terrainData[GENERATED_TERRAIN_MAX_BYTES];
#endif
    u8 eventHead, eventCount; unsigned eventSetSeq;
    struct {u8 kind, state, rule[61], x, y, terrain, tiles[193], tilesSize;unsigned sequence;} eventQueue[8];
#endif
#endif
#endif
#endif
#endif
#endif
#endif
    enum CaveState caveState;
    unsigned caveTimeout, caveRetry;
    char caveExpected[WORLD_CAVE_ID + 1];
    struct WorldCaveWire caveWire;
#endif
#if WORLD_EXTENDED_OBJECTS
    bool8 peer32Probe, peer32Legacy, peer16Probe, peer16Legacy;
#endif
#ifdef _WIN32
    SOCKET fd;
    bool8 winsockStarted;
    unsigned loopbackPort;
    char loopbackToken[65];
#else
    int fd;
#endif
    char socketPath[108], trainer[25], token[65], telemetry[1024];
    char input[WB_BUFFER], output[4096];
    size_t inputSize, outputSize, outputSent;
    unsigned seq, retry, handshakePolls, stagedBytes, generation, appliedGeneration, snapshotAge;
    bool8 tilesLive;
    struct Snapshot live, stage;
    struct Peer field;
    bool8 fieldKnown, menuAnchor;
    unsigned visiblePeers; /* Local render preference, never world population. */
    struct Remote remotes[WB_REMOTES];
    bool8 dialogueActive;
    u16 previousKeys, dialogueKeys;
    char pendingObject[26], dialogueObject[25], dialogueLiteral[58];
    unsigned interactionSeq;
    unsigned shownMeeting, dialogueMeeting, meetingAge, socialCooldown;
    u8 dialogueText[58];
    struct Applied applied[WB_TILES], restored[WB_TILES];
    unsigned appliedCount, restoredCount;
    const struct MapLayout *layout;
    u16 *grid;
    int group, num;
} sWorld;

static bool8 Identifier(const char *s)
{
    size_t i, n = strlen(s);
    if (!n || n > 24) return FALSE;
    for (i = 0; i < n; i++)
        if (!((s[i] >= 'a' && s[i] <= 'z') || (s[i] >= 'A' && s[i] <= 'Z')
           || (s[i] >= '0' && s[i] <= '9') || s[i] == '_' || s[i] == '-')) return FALSE;
    return TRUE;
}

static bool8 Decimal(const char *s, unsigned *value)
{
    unsigned n = 0;
    if (!*s) return FALSE;
    for (; *s; s++) {
        if (*s < '0' || *s > '9' || n > (UINT_MAX - (*s - '0')) / 10) return FALSE;
        n = n * 10 + (*s - '0');
    }
    *value = n;
    return TRUE;
}

/* Decode only literal supported glyphs, never engine text commands. */
static bool8 ObjectText(const char *hex, char text[58])
{
    size_t i, n = strlen(hex), line = 0, lines = 1;
    if (!n || n % 2 || n > 114) return FALSE;
    for (i = 0; i < n / 2; i++) {
        unsigned value = 0, j;
        char c;
        for (j = 0; j < 2; j++) {
            char h = hex[2*i+j];
            if (h >= '0' && h <= '9') value = value * 16 + h - '0';
            else if (h >= 'a' && h <= 'f') value = value * 16 + h - 'a' + 10;
            else return FALSE;
        }
        c = value;
        if (c == '\n') {
            if (!line || ++lines > 2) return FALSE;
            line = 0;
        } else {
            if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z')
               || (c >= '0' && c <= '9') || (c && strchr(" .,!?'-", c)))) return FALSE;
            if (++line > 28) return FALSE;
        }
        text[i] = c;
    }
    text[i] = 0;
    return line != 0;
}

static void EncodeText(const char *text, u8 *out)
{
    for (; *text; text++, out++) {
        char c = *text;
        if (c >= 'A' && c <= 'Z') *out = 0xBB + c - 'A';
        else if (c >= 'a' && c <= 'z') *out = 0xD5 + c - 'a';
        else if (c >= '0' && c <= '9') *out = 0xA1 + c - '0';
        else switch (c) {
        case '\n': *out = 0xFE; break;
        case '.': *out = 0xAD; break;
        case ',': *out = 0xB8; break;
        case '!': *out = 0xAB; break;
        case '?': *out = 0xAC; break;
        case '\'': *out = 0xB4; break;
        case '-': *out = 0xAE; break;
        default: *out = 0; break;
        }
    }
    *out = 0xFF;
}

/* Generated dimensions reject unknown maps before any engine lookup. */
#if GENERATED_MAP_READY
static bool8 IsGeneratedCaveMap(unsigned group, unsigned num)
{
    return (group == MAP_GROUP(MAP_GENERATED_WORLD_CAVE) && num == MAP_NUM(MAP_GENERATED_WORLD_CAVE))
#if GENERATED_MAP_WILDS
        || (group == MAP_GROUP(MAP_GENERATED_WORLD_WILDS) && num == MAP_NUM(MAP_GENERATED_WORLD_WILDS))
#endif
        ;
}
#endif
static bool8 MapCoords(unsigned group, unsigned num, unsigned x, unsigned y)
{
#if GENERATED_MAP_READY
    if (IsGeneratedCaveMap(group, num))
        return sWorld.connected && sWorld.caveAvailable && sWorld.caveState == CAVE_READY
#if GENERATED_MAP_WILDS
            && ((sWorld.caveWire.version == 6 || sWorld.caveWire.version == 7 || sWorld.caveWire.version == 8 || sWorld.caveWire.version == 9 || sWorld.caveWire.version == 10) == (group == MAP_GROUP(MAP_GENERATED_WORLD_WILDS)
                                                && num == MAP_NUM(MAP_GENERATED_WORLD_WILDS)))
#endif
            && GeneratedMap_SharedCoordValid(x, y);
#endif
    return WorldCatalog_Coords(group, num, x, y);
}

static bool8 Overworld(void)
{
    return gSaveBlock1Ptr && gMapHeader.mapLayout && gBackupMapLayout.map
        && gPlayerAvatar.objectEventId < OBJECT_EVENTS_COUNT
        && gObjectEvents[gPlayerAvatar.objectEventId].active
        && gObjectEvents[gPlayerAvatar.objectEventId].isPlayer
        && gMain.callback2 == CB2_Overworld && !gMain.inBattle;
}

static bool8 PresenceReady(void)
{
    return Overworld() && !gPaletteFade.active && !ArePlayerFieldControlsLocked()
        && !ScriptContext_IsEnabled();
}

static bool8 Ready(void)
{
    return PresenceReady() && !gPlayerAvatar.tileTransitionState;
}

/* A busy proxy is a frozen SAFE anchor, not a sample of a reused sprite pool.
 * WorldActivity owns the known battle/trade entry and return lifecycle. Unknown
 * scripts, warps and resets revoke it, and no busy path can resurrect it. */
static void UpdateFieldPresence(void)
{
    bool8 activity = WorldActivity_OwnsFieldInput();
    const char *phase = WorldActivity_Phase();
    bool8 native = activity && (!strcmp(phase, "native") || !strcmp(phase, "connecting")
        || !strcmp(phase, "returning") || WorldActivity_IsEncounterPending());
#if GENERATED_MAP_READY
    if (GeneratedMap_IsInside() && !WorldBridge_GeneratedCaveReady()) {
        sWorld.fieldKnown = sWorld.menuAnchor = FALSE;
        return;
    }
#endif
    if (!gSaveBlock1Ptr || (!native && gMain.callback1 != CB1_Overworld)
     || (sWorld.fieldKnown
      && (sWorld.field.group != (unsigned)gSaveBlock1Ptr->location.mapGroup
       || sWorld.field.num != (unsigned)gSaveBlock1Ptr->location.mapNum))) {
        sWorld.fieldKnown = sWorld.menuAnchor = FALSE;
        return;
    }
    if (PresenceReady()) {
        const struct ObjectEvent *player = &gObjectEvents[gPlayerAvatar.objectEventId];
        struct Peer *p = &sWorld.field;
        p->group = gSaveBlock1Ptr->location.mapGroup;
        p->num = gSaveBlock1Ptr->location.mapNum;
        p->x = player->currentCoords.x - MAP_OFFSET;
        p->y = player->currentCoords.y - MAP_OFFSET;
        p->facing = player->facingDirection;
        p->gfx = player->graphicsId;
        sWorld.fieldKnown = MapCoords(p->group, p->num, p->x, p->y);
        sWorld.menuAnchor = FALSE;
        return;
    }
    if (sWorld.fieldKnown && Overworld() && !ScriptContext_IsEnabled()
     && FuncIsActiveTask(Task_ShowStartMenu)) sWorld.menuAnchor = TRUE;
    /* Only sanctioned activity can retain an anchor across its native script
     * locks. A script outside that lifecycle always invalidates menu ancestry. */
    if ((ScriptContext_IsEnabled() && !native) || (!activity && !sWorld.menuAnchor))
        sWorld.fieldKnown = sWorld.menuAnchor = FALSE;
}

static bool8 Owned(unsigned slot)
{
    const struct Remote *r = &sWorld.remotes[slot];
    const struct ObjectEvent *o;
    if (!r->id[0] || r->object >= OBJECT_EVENTS_COUNT || r->sprite >= MAX_SPRITES) return FALSE;
    o = &gObjectEvents[r->object];
    return o->active && !o->isPlayer && o->localId == WB_LOCALID + slot
        && o->mapGroup == r->group && o->mapNum == r->num && o->spriteId == r->sprite
        && gSprites[r->sprite].inUse && gSprites[r->sprite].data[0] == r->object
        && gSprites[r->sprite].data[7] == WB_MARKER;
}

bool8 WorldBridge_IsRemoteObject(const struct ObjectEvent *object)
{
    unsigned i;
    if (object == NULL) return FALSE;
    for (i = 0; i < WB_REMOTES; i++)
        if (Owned(i) && &gObjectEvents[sWorld.remotes[i].object] == object)
            return TRUE;
    return FALSE;
}

static void RemoveRemote(unsigned slot)
{
    struct Remote *r = &sWorld.remotes[slot];
    if (Owned(slot)) {
#ifdef UBFIX
        /* UBFIX makes the missing map template's flag ID zero, not a NULL dereference. */
        RemoveObjectEventByLocalIdAndMap(WB_LOCALID + slot, r->num, r->group);
#else
        /* Same sprite teardown as RemoveObjectEventInternal, without its template lookup. */
        struct SpriteFrameImage image;
        image.size = GetObjectEventGraphicsInfo(gObjectEvents[r->object].graphicsId)->size;
        gSprites[r->sprite].images = &image;
        DestroySprite(&gSprites[r->sprite]);
        gObjectEvents[r->object].active = FALSE;
#endif
    }
    memset(r, 0, sizeof(*r));
}

static bool8 NativeNpcAt(unsigned x, unsigned y)
{
    unsigned i, j;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        const struct ObjectEvent *o = &gObjectEvents[i];
        bool8 remote = FALSE;
        if (!o->active || o->isPlayer || o->currentCoords.x != (int)x + MAP_OFFSET
         || o->currentCoords.y != (int)y + MAP_OFFSET) continue;
        for (j = 0; j < WB_REMOTES; j++)
            if (Owned(j) && sWorld.remotes[j].object == i) remote = TRUE;
        if (!remote) return TRUE;
    }
    return FALSE;
}

static bool8 SameGrid(void)
{
    return gSaveBlock1Ptr && sWorld.grid && sWorld.grid == gBackupMapLayout.map
        && sWorld.layout == gMapHeader.mapLayout
        && sWorld.group == gSaveBlock1Ptr->location.mapGroup
        && sWorld.num == gSaveBlock1Ptr->location.mapNum;
}

static bool8 GridCoords(unsigned x, unsigned y)
{
    return gMapHeader.mapLayout && x < (unsigned)gMapHeader.mapLayout->width
        && y < (unsigned)gMapHeader.mapLayout->height
        && x + MAP_OFFSET < (unsigned)gBackupMapLayout.width
        && y + MAP_OFFSET < (unsigned)gBackupMapLayout.height;
}

static u16 Raw(unsigned x, unsigned y)
{
    return gBackupMapLayout.map[(y + MAP_OFFSET) * gBackupMapLayout.width + x + MAP_OFFSET];
}

static void RestoreTiles(void)
{
    unsigned i;
    if (SameGrid()) for (i = 0; i < sWorld.appliedCount; i++) {
        struct Applied a = sWorld.applied[i];
        if (!GridCoords(a.tile.x, a.tile.y)) continue;
        /* A new map load or a local script owns any changed entry. Don't roll it back. */
        if (Raw(a.tile.x, a.tile.y) != a.raw) continue;
        MapGridSetMetatileEntryAt(a.tile.x + MAP_OFFSET, a.tile.y + MAP_OFFSET, a.original);
        if (Overworld()) CurrentMapDrawMetatileAt(a.tile.x + MAP_OFFSET, a.tile.y + MAP_OFFSET);
        a.raw = Raw(a.tile.x, a.tile.y);
        if (sWorld.restoredCount < WB_TILES) sWorld.restored[sWorld.restoredCount++] = a;
    }
    sWorld.appliedCount = 0;
}

static void Disconnect(void)
{
    WorldRally_Disconnected();
#ifdef _WIN32
    if (sWorld.fd != INVALID_SOCKET) closesocket(sWorld.fd);
    sWorld.fd = INVALID_SOCKET;
#else
    if (sWorld.fd >= 0) close(sWorld.fd);
    sWorld.fd = -1;
#endif
    sWorld.connected = sWorld.connecting = sWorld.staging = FALSE;
    sWorld.chatProbe = sWorld.chatAvailable = FALSE;
    sWorld.commandsProbe = FALSE;
    sWorld.live.commandMask = sWorld.live.commandsSeen = 0;
    sWorld.travelProbe = sWorld.travelAvailable = FALSE;
#if GENERATED_MAP_READY
    sWorld.caveProbe = sWorld.caveAvailable = sWorld.caveReturning = FALSE;
#if GENERATED_WORLD_XL
    sWorld.caveV10Probe=FALSE;
#endif
#if GENERATED_CAVE_PROFILES
    sWorld.caveV2Probe = FALSE;
#if GENERATED_CAVE_WILDLIFE
    sWorld.caveV3Probe = FALSE;
#if GENERATED_MAP_LARGE
    sWorld.caveV4Probe = FALSE;
    sWorld.caveV5Probe = FALSE;
#if GENERATED_MAP_WILDS
    sWorld.caveV6Probe = FALSE;
#if GENERATED_WILDS_GUIDE
    sWorld.caveV7Probe = FALSE;
#if GENERATED_WILDS_CAST
    sWorld.caveV8Probe = FALSE;
#if GENERATED_WILDS_EVENTS
    sWorld.caveV9Probe = FALSE;
#if GENERATED_WILDS_SHARED_TERRAIN
    sWorld.caveV9TProbe=FALSE;
#if GENERATED_WILDS_SHARED_GEOMETRY
    sWorld.caveV9GProbe=FALSE;
#if GENERATED_WILDS_LARGE_TERRAIN
    sWorld.caveV9HProbe=FALSE;sWorld.terrainRxNext=sWorld.terrainRxTotal=0;sWorld.terrainRxSize=0;
#endif
#endif
    sWorld.terrainPending=FALSE;sWorld.terrainReportPending=FALSE;sWorld.terrainReportedApplied=FALSE;sWorld.terrainRevision=0;
#endif
    sWorld.eventHead = sWorld.eventCount = 0; sWorld.eventSetSeq = 0;
#endif
#endif
#endif
#endif
#endif
#endif
#endif
    sWorld.caveState = CAVE_DISABLED;
    sWorld.caveTimeout = sWorld.caveRetry = 0;
    sWorld.caveExpected[0] = 0;
    WorldCaveWire_Reset(&sWorld.caveWire);
#endif
    sWorld.inputSize = sWorld.outputSize = sWorld.outputSent = 0;
    sWorld.retry = 30;
    sWorld.live.peerCount = sWorld.live.tileCount = sWorld.live.objectCount = 0;
    sWorld.live.chatCount = 0;
    sWorld.live.travel = FALSE;
    sWorld.live.travelCount = 0;
    sWorld.live.chatStatus[0] = 0;
    sWorld.pendingObject[0] = 0;
    memset(&sWorld.live.meeting, 0, sizeof(sWorld.live.meeting));
    sWorld.generation++;
}

bool8 WorldBridge_Enabled(void) { return sWorld.enabled; }
bool8 WorldBridge_ConnectionActive(void)
{
    return sWorld.enabled && sWorld.connected && sWorld.snapshotAge <= 180;
}
bool8 WorldBridge_GeneratedCaveReady(void)
{
#if GENERATED_MAP_READY
    return sWorld.connected && sWorld.caveAvailable && sWorld.caveState == CAVE_READY
        && sWorld.snapshotAge <= 180;
#else
    return FALSE;
#endif
}

bool8 WorldBridge_GetPeer(unsigned index, struct WorldBridgePeer *peer)
{
    unsigned i;
    if (!peer || !sWorld.connected || sWorld.snapshotAge > 180) return FALSE;
    for (i = 0; i < sWorld.live.peerCount; i++) {
        const struct Peer *p = &sWorld.live.peers[i];
        if (p->id[0] == '@') continue;
        if (index--) continue;
        strcpy(peer->name, p->id);
        peer->group = p->group; peer->num = p->num;
        peer->x = p->x; peer->y = p->y; peer->ready = p->ready;
        return TRUE;
    }
    return FALSE;
}

bool8 WorldBridge_TravelTileClear(unsigned group, unsigned num, unsigned x, unsigned y)
{
    unsigned i;
    if (!sWorld.connected || sWorld.snapshotAge > 180 || !MapCoords(group, num, x, y)) return FALSE;
    for (i = 0; i < sWorld.live.travelCount; i++) {
        const struct TravelPeer *f = &sWorld.live.friends[i];
        const struct Peer *p = &f->peer;
        if (p->group == group && p->num == num
         && (sWorld.snapshotAge >= f->ttl || (p->x == x && p->y == y))) return FALSE;
    }
    for (i = 0; i < sWorld.live.peerCount; i++) {
        const struct Peer *p = &sWorld.live.peers[i];
        if (p->group == group && p->num == num && p->x == x && p->y == y) return FALSE;
    }
    /* A changed tile is outside the base-map reachability proof, even if the
     * authority currently marks it passable. Never turn a gate into a shortcut. */
    for (i = 0; i < sWorld.live.tileCount; i++) {
        const struct Tile *t = &sWorld.live.tiles[i];
        if (t->group == group && t->num == num && t->x == x && t->y == y) return FALSE;
    }
    return TRUE;
}

bool8 WorldBridge_GetTravelPeer(unsigned index, struct WorldBridgePeer *peer)
{
    unsigned i;
    if (!peer || !sWorld.connected || sWorld.snapshotAge > 180) return FALSE;
    /* Render relevance is incomplete occupancy information. Old authorities
     * keep chat/presence, but cannot authorize a safe friend landing. */
    if (!sWorld.live.travel) return FALSE;
    for (i = 0; i < sWorld.live.travelCount; i++) {
        const struct TravelPeer *f = &sWorld.live.friends[i];
        const struct Peer *p = &f->peer;
        if (sWorld.snapshotAge >= f->ttl) continue;
        if (index--) continue;
        strcpy(peer->name, p->id);
        peer->group = p->group; peer->num = p->num;
        peer->x = p->x; peer->y = p->y; peer->ready = p->ready;
        return TRUE;
    }
    return FALSE;
}

const char *WorldBridge_TrainerName(void)
{
    return sWorld.enabled ? sWorld.trainer : NULL;
}

bool8 WorldBridge_Init(const char *configPath)
{
    FILE *file;
    char line[1200], key[32], value[1100];
#ifndef _WIN32
    char extra;
#endif
    unsigned seen = 0, i;
    memset(&sWorld, 0, sizeof(sWorld));
    sWorld.visiblePeers = WB_PEERS;
#ifdef _WIN32
    sWorld.fd = INVALID_SOCKET;
#else
    sWorld.fd = -1;
#endif
    if (!configPath) return TRUE;
#ifdef _WIN32
    file = NativeFile_Open(configPath, "rb");
#else
    file = NativeFile_Open(configPath, "r");
#endif
    if (!file) return FALSE;
#ifndef _WIN32
    /* Validate bytes before fgets/sscanf can hide a NUL in the final record
     * or accept control characters as whitespace or a telemetry pathname. */
    {
        int c;
        while ((c = fgetc(file)) != EOF)
            if ((c < 32 && c != '\t' && c != '\r' && c != '\n') || c == 127) goto invalid;
        if (ferror(file) || fseek(file, 0, SEEK_SET)) goto invalid;
    }
#endif
#ifdef _WIN32
    /* Reject embedded NUL and DOS EOF before C-string parsing can hide bytes. */
    {
        int c;
        while ((c = fgetc(file)) != EOF)
            if ((c < 32 && c != '\t' && c != '\r' && c != '\n') || c == 127) goto invalid;
        if (ferror(file) || fseek(file, 0, SEEK_SET)) goto invalid;
    }
#endif
    while (fgets(line, sizeof(line), file)) {
        unsigned bit;
        char *dest;
        size_t size;
        if ((!strchr(line, '\n') && !feof(file)) || strlen(line) > 1150) goto invalid;
        if (line[0] == '#' || line[0] == '\n') continue;
#ifdef _WIN32
        /* Only this allowlist is accepted. No address or hostname is configurable.
         * Paths consume the remainder so a Windows username may contain spaces. */
        {
            char *p = line, *end;
            size_t n;
            while (*p == ' ' || *p == '\t') p++;
            end = p;
            while (*end && !isspace((unsigned char)*end)) end++;
            n = end - p;
            if (!n || n >= sizeof(key) || !*end) goto invalid;
            memcpy(key, p, n); key[n] = 0;
            p = end;
            while (*p == ' ' || *p == '\t') p++;
            end = p + strlen(p);
            while (end > p && (end[-1] == '\n' || end[-1] == '\r')) end--;
            n = end - p;
            if (!n || n >= sizeof(value)) goto invalid;
            memcpy(value, p, n); value[n] = 0;
            if (strcmp(key, "telemetry"))
                for (p = value; *p; p++) if (isspace((unsigned char)*p)) goto invalid;
        }
        if (!strcmp(key, "loopback_port")) {
            if ((seen & 1) || !Decimal(value, &sWorld.loopbackPort)
             || !sWorld.loopbackPort || sWorld.loopbackPort > 65535) goto invalid;
            seen |= 1;
            continue;
        }
        if (!strcmp(key, "loopback_token")) { bit = 16; dest = sWorld.loopbackToken; size = sizeof(sWorld.loopbackToken); }
#else
        if (sscanf(line, "%31s %1099s %c", key, value, &extra) != 2) goto invalid;
        if (!strcmp(key, "socket")) { bit = 1; dest = sWorld.socketPath; size = sizeof(sWorld.socketPath); }
#endif
        else if (!strcmp(key, "visible_peers")) {
            if ((seen & 32) || !Decimal(value, &sWorld.visiblePeers)
             || !sWorld.visiblePeers || sWorld.visiblePeers > WB_PEERS) goto invalid;
            seen |= 32;
            continue;
        }
        else if (!strcmp(key, "trainer")) { bit = 2; dest = sWorld.trainer; size = sizeof(sWorld.trainer); }
        else if (!strcmp(key, "token")) { bit = 4; dest = sWorld.token; size = sizeof(sWorld.token); }
        else if (!strcmp(key, "telemetry")) { bit = 8; dest = sWorld.telemetry; size = sizeof(sWorld.telemetry); }
        else goto invalid;
        if ((seen & bit) || strlen(value) >= size) goto invalid;
        strcpy(dest, value);
        seen |= bit;
    }
#ifdef _WIN32
    if ((seen & ~32u) != 31 || strlen(sWorld.loopbackToken) != 64) goto invalid;
    for (i = 0; i < 64; i++) if (!isxdigit((unsigned char)sWorld.loopbackToken[i])) goto invalid;
#else
    if ((seen & ~32u) != 15 || sWorld.socketPath[0] != '/') goto invalid;
#endif
    if (ferror(file) || !Identifier(sWorld.trainer) || strlen(sWorld.token) != 64) goto invalid;
    for (i = 0; i < 64; i++) if (!isxdigit((unsigned char)sWorld.token[i])) goto invalid;
    fclose(file);
#ifdef _WIN32
    {
        WSADATA data;
        if (WSAStartup(MAKEWORD(2, 2), &data)) return FALSE;
        if (data.wVersion != MAKEWORD(2, 2)) { WSACleanup(); return FALSE; }
        sWorld.winsockStarted = TRUE;
    }
#endif
    WorldRally_Init(configPath);
    sWorld.enabled = TRUE;
    return TRUE;
invalid:
    fclose(file);
    fprintf(stderr, "Invalid world configuration.\n");
    return FALSE;
}

/* A snapshot is transactional. Malformed/over-limit frames close the connection
 * without publishing any staged peer or tile. Lines and whole snapshots are bounded. */
#if GENERATED_MAP_READY
static bool8 CaveProbeRejected(unsigned n, char **tokens)
{
    if (sWorld.caveProbe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
#if GENERATED_WORLD_XL
        if(sWorld.caveV10Probe){sWorld.caveV10Legacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_LARGE_TERRAIN && GENERATED_CAVE_WILDLIFE
        if(sWorld.caveV9HProbe){sWorld.caveV9HLegacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_SHARED_GEOMETRY && GENERATED_CAVE_WILDLIFE
        if(sWorld.caveV9GProbe){sWorld.caveV9GLegacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_SHARED_TERRAIN && GENERATED_CAVE_WILDLIFE
        if(sWorld.caveV9TProbe){sWorld.caveV9TLegacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_EVENTS && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV9Probe) {sWorld.caveV9Legacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_CAST && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV8Probe) {sWorld.caveV8Legacy=TRUE;return TRUE;}
#endif
#if GENERATED_WILDS_GUIDE && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV7Probe) {
            sWorld.caveV7Legacy = TRUE;
            return TRUE;
        }
#endif
#if GENERATED_MAP_WILDS && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV6Probe) {
            sWorld.caveV6Legacy = TRUE;
            return TRUE;
        }
#endif
#if GENERATED_MAP_LARGE && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV5Probe) {
            sWorld.caveV5Legacy = TRUE;
            return TRUE;
        }
        if (sWorld.caveV4Probe) {
            sWorld.caveV4Legacy = TRUE;
            return TRUE;
        }
#endif
#if GENERATED_CAVE_WILDLIFE
        if (sWorld.caveV3Probe) {
            sWorld.caveV3Legacy = TRUE;
            return TRUE;
        }
#endif
#if GENERATED_CAVE_PROFILES
        if (sWorld.caveV2Probe) {
            sWorld.caveV2Legacy = TRUE;
            return TRUE;
        }
#endif
        sWorld.caveLegacy = TRUE;
        return TRUE;
    }
    return FALSE;
}

static bool8 CaveLine(unsigned n, char **tokens)
{
    int result;
    if (!sWorld.caveAvailable || sWorld.staging) return FALSE;
#if GENERATED_WILDS_SHARED_TERRAIN
    if(n==5 && !strcmp(tokens[1],"TERRAIN") && sWorld.caveState==CAVE_READY) {
        unsigned revision,i,length=strlen(tokens[4]);u8 patch[193]={0};
#if GENERATED_WILDS_LARGE_TERRAIN
        if(sWorld.caveV9HProbe)return FALSE;
#endif
        if(!sWorld.caveV9TProbe || sWorld.caveWire.version!=9 || strcmp(tokens[2],sWorld.caveWire.id)
           || !Decimal(tokens[3],&revision) || revision>2147483647U || length<2 || length>386 || (length&1))return FALSE;
        for(i=0;i<length;i++){char c=tokens[4][i];unsigned v;if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return FALSE;
            if(!(i&1))patch[i/2]=v<<4;else patch[i/2]|=v;}
        if(patch[0]>64 || length!=2*(1+3*(unsigned)patch[0]) || (revision==0 && patch[0]!=0) || !GeneratedMap_ValidateSharedTerrain(patch,length/2))return FALSE;
#if !GENERATED_WILDS_SHARED_GEOMETRY
        if(revision>0 && patch[0]==0)return FALSE;
#endif
#if GENERATED_WILDS_SHARED_GEOMETRY
        if(!sWorld.caveV9GProbe && ((revision>0 && patch[0]==0) || GeneratedMap_SharedTerrainNeedsGeometry(patch,length/2)))return FALSE;
#endif
        if(revision<=sWorld.terrainRevision)return TRUE;
        memcpy(sWorld.terrainData,patch,length/2);sWorld.terrainSize=length/2;sWorld.terrainRevision=revision;sWorld.terrainReportPending=FALSE;sWorld.terrainReportedApplied=FALSE;sWorld.terrainPending=TRUE;return TRUE;
    }
#endif
#if GENERATED_WILDS_LARGE_TERRAIN
    if(n==7 && !strcmp(tokens[1],"TERRAINH") && sWorld.caveState==CAVE_READY) {
        unsigned revision,chunk,total,i,length=strlen(tokens[6]),bytes,offset;
        if(!sWorld.caveV9HProbe || sWorld.caveWire.version!=9 || strcmp(tokens[2],sWorld.caveWire.id)
         || !Decimal(tokens[3],&revision) || revision>2147483647U || !Decimal(tokens[4],&chunk) || !Decimal(tokens[5],&total)
         || !total || total>8 || chunk>=total || !length || length>400 || (length&1) || (chunk+1<total && length!=400))return FALSE;
        if(!chunk){sWorld.terrainRxNext=0;sWorld.terrainRxTotal=total;sWorld.terrainRxSize=0;sWorld.terrainRxRevision=revision;}
        if(chunk!=sWorld.terrainRxNext || total!=sWorld.terrainRxTotal || revision!=sWorld.terrainRxRevision)return FALSE;
        bytes=length/2;offset=sWorld.terrainRxSize;if(offset+bytes>sizeof(sWorld.terrainRx))return FALSE;
        for(i=0;i<length;i++){char c=tokens[6][i];unsigned v;if(c>='0'&&c<='9')v=c-'0';else if(c>='a'&&c<='f')v=c-'a'+10;else return FALSE;
            if(!(i&1))sWorld.terrainRx[offset+i/2]=v<<4;else sWorld.terrainRx[offset+i/2]|=v;}
        sWorld.terrainRxSize+=bytes;sWorld.terrainRxNext++;
        if(sWorld.terrainRxNext==total){
            if(!GeneratedMap_ValidateSharedTerrain(sWorld.terrainRx,sWorld.terrainRxSize) || (revision==0 && (sWorld.terrainRxSize!=1 || sWorld.terrainRx[0]!=0)))return FALSE;
            if(revision>sWorld.terrainRevision){memcpy(sWorld.terrainData,sWorld.terrainRx,sWorld.terrainRxSize);sWorld.terrainSize=sWorld.terrainRxSize;
                sWorld.terrainRevision=revision;sWorld.terrainReportPending=FALSE;sWorld.terrainReportedApplied=FALSE;sWorld.terrainPending=TRUE;}
            sWorld.terrainRxNext=sWorld.terrainRxTotal=0;sWorld.terrainRxSize=0;
        }
        return TRUE;
    }
#endif
#if GENERATED_WILDS_EVENTS
    if (n == 5 && !strcmp(tokens[1], "EVENTSET")) {
        unsigned sequence,state;
        if (!WorldCaveWire_ValidId(tokens[2]) || !Decimal(tokens[3],&sequence) || !sequence || !Decimal(tokens[4],&state) || state>15) return FALSE;
        if (sequence<=sWorld.eventSetSeq) return TRUE;
        sWorld.eventSetSeq=sequence;
        if(sWorld.caveState==CAVE_READY && sWorld.caveWire.version==9 && !strcmp(tokens[2],sWorld.caveWire.id) && GeneratedMap_IsInside()) {
            if(sWorld.eventCount<8) {unsigned i=(sWorld.eventHead+sWorld.eventCount)%8;
                sWorld.eventQueue[i].kind=1;sWorld.eventQueue[i].state=state;sWorld.eventQueue[i].sequence=sequence;sWorld.eventCount++;}
        }
        return TRUE;
    }
    if (n == 8 && !strcmp(tokens[1], "EVENTRULE")) {
        unsigned sequence,state,npc,next,i,length;u8 rule[61]={0};
        if (!WorldCaveWire_ValidId(tokens[2]) || !Decimal(tokens[3],&sequence) || !sequence
         || !Decimal(tokens[4],&state) || state>15 || !Decimal(tokens[5],&npc) || !npc || npc>3
         || !Decimal(tokens[6],&next) || next>15) return FALSE;
        length=strlen(tokens[7]);if(!length || length>114 || (length&1))return FALSE;
        rule[0]=state;rule[1]=npc;rule[2]=next;rule[3]=length/2;
        for(i=0;i<length;i++) {char c=tokens[7][i];unsigned v;
            if(c>='0' && c<='9')v=c-'0';else if(c>='a' && c<='f')v=c-'a'+10;else return FALSE;
            if(!(i&1))rule[4+i/2]=v<<4;else rule[4+i/2]|=v;
        }
        if(sequence<=sWorld.eventSetSeq)return TRUE;
        sWorld.eventSetSeq=sequence;
        if(sWorld.caveState==CAVE_READY && sWorld.caveWire.version==9 && !strcmp(tokens[2],sWorld.caveWire.id) && GeneratedMap_IsInside()) {
            if(sWorld.eventCount<8) {unsigned q=(sWorld.eventHead+sWorld.eventCount)%8;
                memcpy(sWorld.eventQueue[q].rule,rule,61);sWorld.eventQueue[q].kind=2;sWorld.eventQueue[q].sequence=sequence;sWorld.eventCount++;}
        }
        return TRUE;
    }
    if (n == 7 && !strcmp(tokens[1], "EVENTTILE")) {
        unsigned sequence,x,y,terrain;
        if (!WorldCaveWire_ValidId(tokens[2]) || !Decimal(tokens[3],&sequence) || !sequence
         || !Decimal(tokens[4],&x) || x>=63 || !Decimal(tokens[5],&y) || y>=63 || !Decimal(tokens[6],&terrain) || terrain>1) return FALSE;
        if(sequence<=sWorld.eventSetSeq)return TRUE;
        sWorld.eventSetSeq=sequence;
        if(sWorld.caveState==CAVE_READY && sWorld.caveWire.version==9 && !strcmp(tokens[2],sWorld.caveWire.id) && GeneratedMap_IsInside()) {
            if(sWorld.eventCount<8) {unsigned q=(sWorld.eventHead+sWorld.eventCount)%8;
                sWorld.eventQueue[q].x=x;sWorld.eventQueue[q].y=y;sWorld.eventQueue[q].terrain=terrain;
                sWorld.eventQueue[q].kind=3;sWorld.eventQueue[q].sequence=sequence;sWorld.eventCount++;}
        }
        return TRUE;
    }
    if (n == 5 && !strcmp(tokens[1], "EVENTTILES")) {
        unsigned sequence,i,length;u8 patch[193]={0};
        if (!WorldCaveWire_ValidId(tokens[2]) || !Decimal(tokens[3],&sequence) || !sequence) return FALSE;
        length=strlen(tokens[4]);if(length<8 || length>386 || (length&1))return FALSE;
        for(i=0;i<length;i++) {char c=tokens[4][i];unsigned v;
            if(c>='0' && c<='9')v=c-'0';else if(c>='a' && c<='f')v=c-'a'+10;else return FALSE;
            if(!(i&1))patch[i/2]=v<<4;else patch[i/2]|=v;
        }
        if(!patch[0] || patch[0]>64 || length!=2*(1+3*(unsigned)patch[0]))return FALSE;
        if(sequence<=sWorld.eventSetSeq)return TRUE;
        sWorld.eventSetSeq=sequence;
        if(sWorld.caveState==CAVE_READY && sWorld.caveWire.version==9 && !strcmp(tokens[2],sWorld.caveWire.id) && GeneratedMap_IsInside()) {
            if(sWorld.eventCount<8) {unsigned q=(sWorld.eventHead+sWorld.eventCount)%8;
                memcpy(sWorld.eventQueue[q].tiles,patch,length/2);sWorld.eventQueue[q].tilesSize=length/2;
                sWorld.eventQueue[q].kind=4;sWorld.eventQueue[q].sequence=sequence;sWorld.eventCount++;}
        }
        return TRUE;
    }
#endif
    if (n == 3 && !strcmp(tokens[1], "RESET") && WorldCaveWire_ValidId(tokens[2])) {
        bool8 requestInFlight = sWorld.caveState == CAVE_WAIT || sWorld.caveState == CAVE_WAIT_RESET;
#if GENERATED_WILDS_EVENTS
        sWorld.eventHead=sWorld.eventCount=0;
#if GENERATED_WILDS_SHARED_TERRAIN
        sWorld.terrainPending=FALSE;sWorld.terrainReportPending=FALSE;sWorld.terrainReportedApplied=FALSE;sWorld.terrainRevision=0;
#if GENERATED_WILDS_LARGE_TERRAIN
        sWorld.terrainRxNext=sWorld.terrainRxTotal=0;sWorld.terrainRxSize=0;
#endif
#endif
#endif
        WorldCaveWire_Reset(&sWorld.caveWire);
        memcpy(sWorld.caveExpected, tokens[2], sizeof(sWorld.caveExpected));
        /* A GET sent just before RESET may already produce the new map.
         * Wait briefly for it instead of issuing a duplicate request. */
        sWorld.caveState = requestInFlight ? CAVE_WAIT_RESET : CAVE_IDLE;
        sWorld.caveTimeout = requestInFlight ? 60 : 0;
        sWorld.caveRetry = 0;
        return TRUE;
    }
    if (n == 2 && !strcmp(tokens[1], "NONE")
     && (sWorld.caveState == CAVE_WAIT || sWorld.caveState == CAVE_WAIT_RESET)) {
        sWorld.caveState = (GeneratedMap_IsInside() || GeneratedMap_EntryPending()) ? CAVE_RETURN_NONE : CAVE_DISABLED;
        return TRUE;
    }
    if (n == 2 && !strcmp(tokens[1], "BUSY")
     && (sWorld.caveState == CAVE_WAIT || sWorld.caveState == CAVE_WAIT_RESET)) {
        WorldCaveWire_Reset(&sWorld.caveWire);
        sWorld.caveState = CAVE_IDLE;sWorld.caveRetry = 60;return TRUE;
    }
    if (n == 3 && !strcmp(tokens[1], "OK") && sWorld.caveState == CAVE_WAIT_OK
     && !strcmp(tokens[2], sWorld.caveWire.id)) {
        sWorld.caveExpected[0] = 0;
        sWorld.caveState = CAVE_READY;return TRUE;
    }
    if (sWorld.caveState == CAVE_WAIT_RESET && (n == 3 || n == 4 || n == 5) && !strcmp(tokens[1], "BEGIN")) {
        sWorld.caveState = CAVE_WAIT;
        sWorld.caveTimeout = 600;
    }
    if (sWorld.caveState != CAVE_WAIT) return FALSE;
    if ((n == 3 || n == 4 || n == 5) && !strcmp(tokens[1], "BEGIN") && sWorld.caveExpected[0]
     && strcmp(tokens[2], sWorld.caveExpected)) return FALSE;
#if GENERATED_CAVE_PROFILES
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !sWorld.caveV2Probe) return FALSE;
#endif
#if GENERATED_CAVE_WILDLIFE
    if (n == 5 && !strcmp(tokens[1], "BEGIN") && !sWorld.caveV3Probe) return FALSE;
#endif
#if GENERATED_MAP_LARGE
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[3], "LARGE")) {
#if GENERATED_CAVE_WILDLIFE
        if (!sWorld.caveV4Probe) return FALSE;
#else
        return FALSE;
#endif
    }
#endif
#if GENERATED_MAP_LARGE && GENERATED_CAVE_WILDLIFE
    if (n == 5 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[4], "5") && !sWorld.caveV5Probe) return FALSE;
#endif
#if GENERATED_MAP_WILDS
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[3], "WILDS")) {
#if GENERATED_CAVE_WILDLIFE
        if (!sWorld.caveV6Probe) return FALSE;
#else
        return FALSE;
#endif
    }
#endif
#if GENERATED_WILDS_GUIDE
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[3], "GUIDE")) {
#if GENERATED_CAVE_WILDLIFE
        if (!sWorld.caveV7Probe) return FALSE;
#else
        return FALSE;
#endif
    }
#endif
#if GENERATED_WILDS_CAST
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[3], "CAST")) {
#if GENERATED_CAVE_WILDLIFE
        if (!sWorld.caveV8Probe) return FALSE;
#else
        return FALSE;
#endif
    }
#endif
#if GENERATED_WILDS_EVENTS
    if (n == 4 && !strcmp(tokens[1], "BEGIN") && !strcmp(tokens[3], "EVENTS")) {
#if GENERATED_CAVE_WILDLIFE
        if (!sWorld.caveV9Probe) return FALSE;
#else
        return FALSE;
#endif
    }
#endif
#if GENERATED_WORLD_XL
    if(n==4 && !strcmp(tokens[1],"BEGIN") && !strcmp(tokens[3],"XLWILDS") && !sWorld.caveV10Probe) return FALSE;
#endif
    result = WorldCaveWire_Feed(&sWorld.caveWire, n, (const char *const *)tokens);
    if (result < 0) return FALSE;
    if (result == 1) {
#if GENERATED_WORLD_XL
        if(sWorld.caveWire.version==10) {
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending()) && !GeneratedMap_MatchesPreparedXLWilds(sWorld.caveWire.cells,WORLD_CAVE_XL_CELLS)) sWorld.caveState=CAVE_MISMATCH;
            else if(GeneratedMap_MatchesPreparedXLWilds(sWorld.caveWire.cells,WORLD_CAVE_XL_CELLS) || GeneratedMap_StageSharedXLWilds(sWorld.caveWire.cells,WORLD_CAVE_XL_CELLS)) sWorld.caveState=CAVE_ACK;
            else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_WILDS_EVENTS && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 9) {
#if GENERATED_WILDS_SHARED_TERRAIN
            if(sWorld.caveV9TProbe && !sWorld.caveWire.terrainSeen)return FALSE;
#if GENERATED_WILDS_LARGE_TERRAIN
            if(sWorld.caveV9TProbe && (sWorld.caveV9HProbe != sWorld.caveWire.terrainLargeFraming))return FALSE;
#endif
#endif
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
             && !GeneratedMap_MatchesPreparedEventWilds(sWorld.caveWire.events, WORLD_CAVE_EVENT_BYTES, sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_MISMATCH;
            else if (GeneratedMap_StageSharedEventWilds(sWorld.caveWire.events, WORLD_CAVE_EVENT_BYTES, sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) {
#if GENERATED_WILDS_SHARED_TERRAIN
                if(sWorld.caveV9TProbe) {
                    if(!GeneratedMap_ValidateSharedTerrain(sWorld.caveWire.terrain,sWorld.caveWire.terrainSize))return FALSE;
#if GENERATED_WILDS_SHARED_GEOMETRY
                    if(!sWorld.caveV9GProbe && ((sWorld.caveWire.terrainRevision>0 && sWorld.caveWire.terrain[0]==0) || GeneratedMap_SharedTerrainNeedsGeometry(sWorld.caveWire.terrain,sWorld.caveWire.terrainSize)))return FALSE;
#endif
                    sWorld.terrainRevision=sWorld.caveWire.terrainRevision;
                    sWorld.terrainReportPending=FALSE;sWorld.terrainReportedApplied=FALSE;
                    if(GeneratedMap_IsInside() || GeneratedMap_EntryPending()) {
                        memcpy(sWorld.terrainData,sWorld.caveWire.terrain,sWorld.caveWire.terrainSize);sWorld.terrainSize=sWorld.caveWire.terrainSize;sWorld.terrainPending=TRUE;
                    } else {
                        if(!GeneratedMap_StageSharedTerrain(sWorld.caveWire.terrain,sWorld.caveWire.terrainSize))return FALSE;
                        sWorld.terrainReportPending=TRUE;
                    }
                }
#endif
                sWorld.caveState = CAVE_ACK;
            } else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_WILDS_CAST && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 8) {
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
             && !GeneratedMap_MatchesPreparedCastWilds(sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_MISMATCH;
            else if (GeneratedMap_StageSharedCastWilds(sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_ACK;
            else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_WILDS_GUIDE && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 7) {
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
             && !GeneratedMap_MatchesPreparedGuidedWilds(sWorld.caveWire.guide, WORLD_CAVE_GUIDE_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_MISMATCH;
            else if (GeneratedMap_StageSharedGuidedWilds(sWorld.caveWire.guide, WORLD_CAVE_GUIDE_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_ACK;
            else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_MAP_WILDS && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 6) {
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
             && !GeneratedMap_MatchesPreparedWilds(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_MISMATCH;
            else if (GeneratedMap_StageSharedWildsTemplate(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS))
                sWorld.caveState = CAVE_ACK;
            else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_MAP_LARGE && GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 4 || sWorld.caveWire.version == 5) {
            if (sWorld.caveWire.version == 5 && !GeneratedMap_ValidateWildlife(sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)) return FALSE;
            if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
             && !(sWorld.caveWire.version == 5
                 ? GeneratedMap_MatchesPreparedLargeWildlife(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS, sWorld.caveWire.profile, sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)
                 : GeneratedMap_MatchesPreparedLarge(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)))
                sWorld.caveState = CAVE_MISMATCH;
            else if (GeneratedMap_StageSharedLargeTemplate(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) {
                if (sWorld.caveWire.version == 5 && (!GeneratedMap_SetSharedEncounterProfile(sWorld.caveWire.profile)
                 || !GeneratedMap_SetSharedWildlife(sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES))) return FALSE;
                sWorld.caveState = CAVE_ACK;
            } else return FALSE;
            return TRUE;
        }
#endif
#if GENERATED_CAVE_WILDLIFE
        if (sWorld.caveWire.version == 3 && !GeneratedMap_ValidateWildlife(sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)) return FALSE;
#endif
        if ((GeneratedMap_IsInside() || GeneratedMap_EntryPending())
#if GENERATED_CAVE_WILDLIFE
         && !(sWorld.caveWire.version == 3
              ? GeneratedMap_MatchesPreparedWildlife(sWorld.caveWire.cells, WORLD_CAVE_CELLS, sWorld.caveWire.profile, sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)
              : GeneratedMap_MatchesPreparedProfile(sWorld.caveWire.cells, WORLD_CAVE_CELLS, sWorld.caveWire.profile)))
#elif GENERATED_CAVE_PROFILES
         && !GeneratedMap_MatchesPreparedProfile(sWorld.caveWire.cells, WORLD_CAVE_CELLS, sWorld.caveWire.profile))
#else
         && !GeneratedMap_MatchesPrepared(sWorld.caveWire.cells, WORLD_CAVE_CELLS))
#endif
            sWorld.caveState = CAVE_MISMATCH;
        else if (GeneratedMap_StageTemplate(sWorld.caveWire.cells, WORLD_CAVE_CELLS)) {
#if GENERATED_CAVE_PROFILES
            if ((sWorld.caveWire.version == 2 || sWorld.caveWire.version == 3 || sWorld.caveWire.version == 5) && !GeneratedMap_SetSharedEncounterProfile(sWorld.caveWire.profile)) return FALSE;
#endif
#if GENERATED_CAVE_WILDLIFE
            if ((sWorld.caveWire.version == 3 || sWorld.caveWire.version == 5) && !GeneratedMap_SetSharedWildlife(sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)) return FALSE;
#endif
            sWorld.caveState = CAVE_ACK;
        } else return FALSE;
    }
    return TRUE;
}
#endif

static bool8 Line(char *line)
{
    char *tokens[12], *save, *p;
    unsigned v[8], n = 0, i;
    for (p = strtok_r(line, " ", &save); p; p = strtok_r(NULL, " ", &save)) {
        if (n == ARRAY_COUNT(tokens)) return FALSE;
        tokens[n++] = p;
    }
    if (!n) return FALSE;
    if (!sWorld.connected) {
        if (sWorld.commandsProbe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.commandsLegacy = TRUE;
            return FALSE;
        }

#if WORLD_EXTENDED_OBJECTS
        if (sWorld.peer32Probe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.peer32Legacy = TRUE;
            return FALSE;
        }
        if (sWorld.peer16Probe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.peer16Legacy = TRUE;
            return FALSE;
        }
#endif
#if GENERATED_MAP_READY
        if (CaveProbeRejected(n, tokens)) {
#if WORLD_EXTENDED_OBJECTS
            /* Each lower cave capability gets a fresh peer-window probe. */
            sWorld.peer32Legacy = sWorld.peer16Legacy = FALSE;
#endif
            return FALSE;
        }
#endif
        if (sWorld.rallyProbe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.rallyLegacy = TRUE;
            return FALSE;
        }
        if (sWorld.travelProbe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.travelLegacy = TRUE;
            return FALSE;
        }
        /* An older server rejects the optional role before presence is live.
         * Retry once using the legacy role, without weakening authentication. */
        if (sWorld.chatProbe && n == 2 && !strcmp(tokens[0], "ERROR") && !strcmp(tokens[1], "AUTH")) {
            sWorld.chatLegacy = TRUE;
            return FALSE;
        }
        if (n != 4 || strcmp(tokens[0], "WELCOME") || strcmp(tokens[1], "1")
         || strcmp(tokens[2], sWorld.trainer) || !Decimal(tokens[3], &v[0])) return FALSE;
        sWorld.connected = TRUE;
        sWorld.rallyAvailable = sWorld.rallyProbe;
        sWorld.chatAvailable = sWorld.chatProbe;
        sWorld.travelAvailable = sWorld.travelProbe;
#if GENERATED_MAP_READY
        sWorld.caveAvailable = sWorld.caveProbe;
        sWorld.caveState = sWorld.caveAvailable ? CAVE_IDLE :
            ((GeneratedMap_IsInside() || GeneratedMap_EntryPending()) ? CAVE_RETURN_NONE : CAVE_DISABLED);
        sWorld.caveRetry = 0;
#endif
        sWorld.live.revision = v[0];
        return TRUE;
    }
#if GENERATED_MAP_READY
    if (!strcmp(tokens[0], "CAVE")) return CaveLine(n, tokens);
#endif
    if (!strcmp(tokens[0], "BEGIN")) {
        if (n != 2 || sWorld.staging || !Decimal(tokens[1], &v[0]) || v[0] < sWorld.live.revision) return FALSE;
        memset(&sWorld.stage, 0, sizeof(sWorld.stage));
        sWorld.stage.revision = v[0];
        sWorld.staging = TRUE;
        sWorld.stagedBytes = 0;
        return TRUE;
    }
    if (!sWorld.staging) return FALSE;
    if (!strcmp(tokens[0], "END")) {
        if (!ChatCommandGate_Complete(sWorld.commandsProbe, sWorld.stage.commandsSeen)) return FALSE;
        if (n != 1) return FALSE;
        if ((sWorld.travelAvailable && !sWorld.stage.travel)
         || sWorld.stage.travelCount != sWorld.stage.travelExpected) return FALSE;
        if (sWorld.stage.rally.count != sWorld.stage.rallyExpected) return FALSE;
        if (sWorld.stage.rally.id) {
            bool8 own = FALSE, owner = FALSE;
            for (i = 0; i < sWorld.stage.rally.count; i++) {
                if (!strcmp(sWorld.stage.rally.members[i].name, sWorld.trainer)) own = TRUE;
                if (!strcmp(sWorld.stage.rally.members[i].name, sWorld.stage.rally.owner)) owner = TRUE;
            }
            if (!own || !owner) return FALSE;
        }
        if (sWorld.live.meeting.seq != sWorld.stage.meeting.seq) sWorld.meetingAge = 0;
        sWorld.live = sWorld.stage;
        sWorld.snapshotAge = 0;
        sWorld.generation++;
        sWorld.staging = FALSE;
        return TRUE;
    }
    if (!strcmp(tokens[0], "RALLY")) {
        struct WorldRallySnapshot *r = &sWorld.stage.rally;
        if (n != 7 || sWorld.stage.rallySeen) return FALSE;
        for (i = 0; i < 4; i++) if (!Decimal(tokens[i+1], &v[i])) return FALSE;
        if (!Decimal(tokens[6], &v[4]) || v[4] > WORLD_RALLY_ROSTER) return FALSE;
        if (!v[0]) {
            if (v[1] || v[2] || v[3] || v[4] || strcmp(tokens[5], "-")) return FALSE;
        } else if (v[1] < 1 || v[1] > 4 || v[2] != WORLD_RALLY_ROXANNE
                   || v[3] > 1 || !v[4] || !Identifier(tokens[5])) return FALSE;
        r->id=v[0]; r->phase=v[1]; r->scene=v[2]; r->scope=v[3];
        strcpy(r->owner, tokens[5]);
        sWorld.stage.rallyExpected = v[4];
        sWorld.stage.rallySeen = TRUE;
        return TRUE;
    }
    if (!strcmp(tokens[0], "RALLYMEM")) {
        struct WorldRallySnapshot *r = &sWorld.stage.rally;
        struct WorldRallyMember *m;
        if (n != 4 || !sWorld.stage.rallySeen || !Identifier(tokens[1])
         || r->count >= sWorld.stage.rallyExpected || !Decimal(tokens[2], &v[0])
         || !Decimal(tokens[3], &v[1]) || v[0] < 1 || v[0] > 8 || v[1] >= WORLD_RALLY_ROSTER) return FALSE;
        for (i = 0; i < r->count; i++)
            if (!strcmp(r->members[i].name, tokens[1]) || r->members[i].slot == v[1]) return FALSE;
        if ((!v[1]) != (!strcmp(tokens[1], r->owner))) return FALSE;
        m = &r->members[r->count++];
        strcpy(m->name, tokens[1]); m->state=v[0]; m->slot=v[1];
        return TRUE;
    }
    if (!strcmp(tokens[0], "MEET")) {
        struct Meeting *m = &sWorld.stage.meeting;
        if (n != 9 || m->seq || !Decimal(tokens[1], &v[0]) || !v[0]
         || v[0] > sWorld.stage.revision || !Identifier(tokens[2]) || !Identifier(tokens[3])
         || !strcmp(tokens[2], tokens[3]) || strcmp(tokens[8], "explore")
         || (strcmp(tokens[2], sWorld.trainer) && strcmp(tokens[3], sWorld.trainer))) return FALSE;
        for (i = 1; i < 5; i++) if (!Decimal(tokens[i+3], &v[i])) return FALSE;
#if GENERATED_MAP_READY
        if (IsGeneratedCaveMap(v[1], v[2])) return FALSE;
#endif
        if (!MapCoords(v[1],v[2],v[3],v[4])) return FALSE;
        m->seq=v[0]; m->group=v[1]; m->num=v[2]; m->x=v[3]; m->y=v[4];
        strcpy(m->player,tokens[2]); strcpy(m->target,tokens[3]);
        return TRUE;
    }
    if (!strcmp(tokens[0], "COMMANDS")) {
        if (n != 3 || !Decimal(tokens[1], &v[0]) || !Decimal(tokens[2], &v[1])) return FALSE;
        return ChatCommandGate_Record(&sWorld.stage.commandMask, &sWorld.stage.commandsSeen,
                                      v[0], v[1], sWorld.commandsProbe);
    }
    if (!strcmp(tokens[0], "CHATSTATUS")) {
        if (n != 2 || sWorld.stage.chatStatus[0]
         || (strcmp(tokens[1], "ready") && strcmp(tokens[1], "sent")
          && strcmp(tokens[1], "slow") && strcmp(tokens[1], "unavailable"))) return FALSE;
        strcpy(sWorld.stage.chatStatus, tokens[1]);
        return TRUE;
    }
    if (!strcmp(tokens[0], "CHATMSG")) {
        struct ChatMessage *message;
        size_t length, j;
        bool8 visible = FALSE;
        if (n != 5 || sWorld.stage.chatCount == 16 || !Decimal(tokens[1], &v[0]) || !v[0]
         || !Identifier(tokens[2]) || (strcmp(tokens[3], "*") && !Identifier(tokens[3]))
         || (strcmp(tokens[3], "*") && strcmp(tokens[3], sWorld.trainer)
          && strcmp(tokens[2], sWorld.trainer))
         || (sWorld.stage.chatCount && v[0] <= sWorld.stage.chat[sWorld.stage.chatCount-1].seq)) return FALSE;
        length = strlen(tokens[4]);
        if (!length || length % 2 || length > 240) return FALSE;
        message = &sWorld.stage.chat[sWorld.stage.chatCount];
        for (i = 0; i < length / 2; i++) {
            unsigned c = 0;
            for (j = 0; j < 2; j++) {
                char h = tokens[4][2*i+j];
                if (h >= '0' && h <= '9') c = c * 16 + h - '0';
                else if (h >= 'a' && h <= 'f') c = c * 16 + h - 'a' + 10;
                else return FALSE;
            }
            if (c < 32 || c > 126) return FALSE;
            if (c != 32) visible = TRUE;
            message->text[i] = c;
        }
        if (!visible) return FALSE;
        message->text[i] = 0;
        message->seq = v[0];
        strcpy(message->sender, tokens[2]);
        strcpy(message->target, tokens[3]);
        sWorld.stage.chatCount++;
        return TRUE;
    }
    if (!strcmp(tokens[0], "TRAVEL")) {
        if (n != 2 || sWorld.stage.travel || !Decimal(tokens[1], &v[0]) || v[0] > WB_TRAVEL_PEERS) return FALSE;
        sWorld.stage.travel = TRUE;
        sWorld.stage.travelExpected = v[0];
        return TRUE;
    }
    if (!strcmp(tokens[0], "FRIEND")) {
        struct TravelPeer *f;
        struct Peer *peer;
        if (n != 10 || !sWorld.stage.travel || !Identifier(tokens[1])
         || !strcmp(tokens[1], sWorld.trainer)
         || sWorld.stage.travelCount >= sWorld.stage.travelExpected) return FALSE;
        for (i = 0; i < 8; i++) if (!Decimal(tokens[i + 2], &v[i])) return FALSE;
#if GENERATED_MAP_READY
        if (IsGeneratedCaveMap(v[0], v[1])) return FALSE;
#endif
        if (!MapCoords(v[0], v[1], v[2], v[3]) || v[4] < 1 || v[4] > 4
         || v[5] > 255 || v[6] > 1 || v[7] > 180) return FALSE;
        for (i = 0; i < sWorld.stage.travelCount; i++)
            if (!strcmp(sWorld.stage.friends[i].peer.id, tokens[1])) return FALSE;
        f = &sWorld.stage.friends[sWorld.stage.travelCount++];
        peer = &f->peer;
        strcpy(peer->id, tokens[1]);
        peer->group=v[0]; peer->num=v[1]; peer->x=v[2]; peer->y=v[3];
        peer->facing=v[4]; peer->gfx=v[5]; peer->ready=v[6]; f->ttl=v[7];
        return TRUE;
    }
    if (!strcmp(tokens[0], "PEER")) {
        struct Peer *peer;
        if (n != 9 || !Identifier(tokens[1]) || !strcmp(tokens[1], sWorld.trainer)
         || sWorld.stage.peerCount >= WB_REMOTES
         || sWorld.stage.peerCount - sWorld.stage.objectCount >= WB_PEERS) return FALSE;
        for (i = 0; i < 7; i++) if (!Decimal(tokens[i + 2], &v[i])) return FALSE;
        if (!MapCoords(v[0], v[1], v[2], v[3]) || v[4] < 1 || v[4] > 4 || v[5] > 255 || v[6] > 1) return FALSE;
        for (i = 0; i < sWorld.stage.peerCount; i++) if (!strcmp(sWorld.stage.peers[i].id, tokens[1])) return FALSE;
        peer = &sWorld.stage.peers[sWorld.stage.peerCount++];
        strcpy(peer->id, tokens[1]);
        peer->group=v[0]; peer->num=v[1]; peer->x=v[2]; peer->y=v[3];
        peer->facing=v[4]; peer->gfx=v[5]; peer->ready=v[6];
        return TRUE;
    }
    if (!strcmp(tokens[0], "OBJECT")) {
        struct Peer *peer;
        char id[26], text[58];
        if (n != 8 || !Identifier(tokens[1]) || sWorld.stage.peerCount >= WB_REMOTES
         || sWorld.stage.objectCount >= WB_OBJECTS
         || !ObjectText(tokens[7], text)) return FALSE;
        for (i = 0; i < 5; i++) if (!Decimal(tokens[i + 2], &v[i])) return FALSE;
#if GENERATED_MAP_READY
        if (IsGeneratedCaveMap(v[0], v[1])) return FALSE;
#endif
        if (!MapCoords(v[0], v[1], v[2], v[3]) || (v[4] != 7 && v[4] != 8)) return FALSE;
        snprintf(id, sizeof(id), "@%s", tokens[1]);
        for (i = 0; i < sWorld.stage.peerCount; i++) {
            peer = &sWorld.stage.peers[i];
            if (!strcmp(peer->id, id) || (peer->id[0] == '@' && peer->group == v[0]
             && peer->num == v[1] && peer->x == v[2] && peer->y == v[3])) return FALSE;
        }
        peer = &sWorld.stage.peers[sWorld.stage.peerCount++];
        sWorld.stage.objectCount++;
        strcpy(peer->id, id); strcpy(peer->text, text);
        peer->group=v[0]; peer->num=v[1]; peer->x=v[2]; peer->y=v[3];
        peer->gfx=v[4]; peer->facing=1; peer->ready=1;
        return TRUE;
    }
    if (!strcmp(tokens[0], "TILE")) {
        struct Tile *tile;
        if (n != 7 || sWorld.stage.tileCount == WB_TILES) return FALSE;
        for (i = 0; i < 6; i++) if (!Decimal(tokens[i + 1], &v[i])) return FALSE;
#if GENERATED_MAP_READY
        if (IsGeneratedCaveMap(v[0], v[1])) return FALSE;
#endif
        if (!MapCoords(v[0], v[1], v[2], v[3]) || !WorldCatalog_Metatile(v[0], v[1], v[4]) || v[5] > 1) return FALSE;
        for (i = 0; i < sWorld.stage.tileCount; i++) {
            tile = &sWorld.stage.tiles[i];
            if (tile->group == v[0] && tile->num == v[1] && tile->x == v[2] && tile->y == v[3]) return FALSE;
        }
        tile = &sWorld.stage.tiles[sWorld.stage.tileCount++];
        tile->group=v[0]; tile->num=v[1]; tile->x=v[2]; tile->y=v[3]; tile->metatile=v[4]; tile->collision=v[5];
        return TRUE;
    }
    return FALSE;
}

static bool8 SocketOpen(void)
{
#ifdef _WIN32
    return sWorld.fd != INVALID_SOCKET;
#else
    return sWorld.fd >= 0;
#endif
}

static void QueueHello(bool8 headless)
{
    const char *role;
    const char *suffix = "";
    sWorld.rallyProbe = !sWorld.rallyLegacy;
#if GENERATED_MAP_READY
    sWorld.caveProbe = !sWorld.caveLegacy;
    if (sWorld.caveProbe) {
#if GENERATED_CAVE_PROFILES
        sWorld.caveV2Probe = !sWorld.caveV2Legacy;
        suffix = sWorld.caveV2Probe ? "CAVE2" : "CAVE";
#if GENERATED_CAVE_WILDLIFE
        sWorld.caveV3Probe = sWorld.caveV2Probe && !sWorld.caveV3Legacy;
        if (sWorld.caveV3Probe) suffix = "CAVE3";
#if GENERATED_MAP_LARGE
        sWorld.caveV4Probe = sWorld.caveV3Probe && !sWorld.caveV4Legacy;
        if (sWorld.caveV4Probe) suffix = "CAVE4";
        sWorld.caveV5Probe = sWorld.caveV4Probe && !sWorld.caveV5Legacy;
        if (sWorld.caveV5Probe) suffix = "CAVE5";
#if GENERATED_MAP_WILDS
        sWorld.caveV6Probe = sWorld.caveV5Probe && !sWorld.caveV6Legacy;
        if (sWorld.caveV6Probe) suffix = "CAVE6";
#if GENERATED_WILDS_GUIDE
        sWorld.caveV7Probe = sWorld.caveV6Probe && !sWorld.caveV7Legacy;
        if (sWorld.caveV7Probe) suffix = "CAVE7";
#if GENERATED_WILDS_CAST
        sWorld.caveV8Probe = sWorld.caveV7Probe && !sWorld.caveV8Legacy;
        if (sWorld.caveV8Probe) suffix = "CAVE8";
#if GENERATED_WILDS_EVENTS
        sWorld.caveV9Probe = sWorld.caveV8Probe && !sWorld.caveV9Legacy;
        if (sWorld.caveV9Probe) suffix = "CAVE9";
#if GENERATED_WILDS_SHARED_TERRAIN
        sWorld.caveV9TProbe=sWorld.caveV9Probe && !sWorld.caveV9TLegacy;
        if(sWorld.caveV9TProbe)suffix="CAVE9T";
#if GENERATED_WILDS_SHARED_GEOMETRY
        sWorld.caveV9GProbe=sWorld.caveV9TProbe && !sWorld.caveV9GLegacy;
        if(sWorld.caveV9GProbe)suffix="CAVE9G";
#if GENERATED_WILDS_LARGE_TERRAIN
        sWorld.caveV9HProbe=sWorld.caveV9GProbe && !sWorld.caveV9HLegacy;
        if(sWorld.caveV9HProbe)suffix="CAVE9H";
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#else
        suffix = "CAVE";
#endif
#if GENERATED_WORLD_XL && GENERATED_WILDS_LARGE_TERRAIN && GENERATED_CAVE_WILDLIFE
        sWorld.caveV10Probe=sWorld.caveV9HProbe && !sWorld.caveV10Legacy;
        if(sWorld.caveV10Probe)suffix="CAVE10";
#endif
    }
#endif
#if WORLD_EXTENDED_OBJECTS
    sWorld.peer32Probe = !sWorld.peer32Legacy;
    sWorld.peer16Probe = !sWorld.peer32Probe && !sWorld.peer16Legacy;
#define WB_PEER_SUFFIX (sWorld.peer32Probe ? "PEER32" : sWorld.peer16Probe ? "PEER16" : "")
#else
#define WB_PEER_SUFFIX ""
#endif
#ifdef _WIN32
    (void)headless;
    sWorld.chatProbe = FALSE;
    sWorld.commandsProbe = FALSE;
    sWorld.travelProbe = !sWorld.travelLegacy;
    role = sWorld.rallyProbe ? "SOCIALTRAVELRALLY" : sWorld.travelProbe ? "SOCIALTRAVEL" : "SOCIAL";
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "EWLOCAL1 %s\nHELLO 1 %s %s %s%s%s\n", sWorld.loopbackToken, sWorld.trainer, sWorld.token, role, WB_PEER_SUFFIX, suffix);
#else
    sWorld.chatProbe = !headless && !sWorld.chatLegacy;
    sWorld.commandsProbe = sWorld.chatProbe && !sWorld.commandsLegacy;
    sWorld.travelProbe = !sWorld.travelLegacy;
    role = sWorld.rallyProbe ? (sWorld.chatProbe ? "SOCIALTRAVELCHATRALLY" : "SOCIALTRAVELRALLY")
        : sWorld.travelProbe ? (sWorld.chatProbe ? "SOCIALTRAVELCHAT" : "SOCIALTRAVEL")
        : (sWorld.chatProbe ? "SOCIALCHAT" : "SOCIAL");
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "HELLO 1 %s %s %s%s%s%s\n", sWorld.trainer, sWorld.token, role, WB_PEER_SUFFIX, suffix, sWorld.commandsProbe ? "COMMANDS1" : "");
#endif
#undef WB_PEER_SUFFIX
}

static void Flush(void)
{
    while (SocketOpen() && sWorld.outputSent < sWorld.outputSize) {
#ifdef _WIN32
        int n = send(sWorld.fd, sWorld.output + sWorld.outputSent,
                     (int)(sWorld.outputSize - sWorld.outputSent), 0);
        if (n == SOCKET_ERROR) {
            int error = WSAGetLastError();
            if (error == WSAEWOULDBLOCK || error == WSAEINTR) return;
            Disconnect(); return;
        }
#else
        ssize_t n;
#ifdef MSG_NOSIGNAL
        n = send(sWorld.fd, sWorld.output + sWorld.outputSent, sWorld.outputSize - sWorld.outputSent, MSG_NOSIGNAL);
#else
        n = send(sWorld.fd, sWorld.output + sWorld.outputSent, sWorld.outputSize - sWorld.outputSent, 0);
#endif
#endif
        if (n > 0) sWorld.outputSent += n;
#ifndef _WIN32
        else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR)) return;
#endif
        else { Disconnect(); return; }
    }
    if (sWorld.outputSent == sWorld.outputSize) sWorld.outputSent = sWorld.outputSize = 0;
}

static void Connect(bool8 headless)
{
#ifdef _WIN32
    struct sockaddr_in addr;
    u_long nonblocking = 1;
    int result;
    sWorld.fd = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (!SocketOpen()) { sWorld.retry = 30; return; }
    if (ioctlsocket(sWorld.fd, FIONBIO, &nonblocking) == SOCKET_ERROR) { Disconnect(); return; }
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons((u_short)sWorld.loopbackPort);
    result = connect(sWorld.fd, (struct sockaddr *)&addr, sizeof(addr));
    if (result == SOCKET_ERROR) {
        int error = WSAGetLastError();
        if (error != WSAEWOULDBLOCK && error != WSAEINPROGRESS && error != WSAEALREADY) {
            Disconnect(); return;
        }
    }
#else
    struct sockaddr_un addr;
    int result;
    sWorld.fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sWorld.fd < 0) { sWorld.retry = 30; return; }
    if (fcntl(sWorld.fd, F_SETFL, O_NONBLOCK) < 0) { Disconnect(); return; }
    fcntl(sWorld.fd, F_SETFD, FD_CLOEXEC);
#ifdef SO_NOSIGPIPE
    { int one = 1; setsockopt(sWorld.fd, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof(one)); }
#endif
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, sWorld.socketPath);
    result = connect(sWorld.fd, (struct sockaddr *)&addr, sizeof(addr));
    if (result < 0 && errno != EINPROGRESS) { Disconnect(); return; }
#endif
    sWorld.connecting = result < 0;
    sWorld.handshakePolls = WB_HANDSHAKE_POLLS;
    sWorld.seq = 0;
    sWorld.shownMeeting = 0;
    QueueHello(headless);
}

static void Receive(bool8 headless)
{
    unsigned budget = 0;
#ifdef _WIN32
    fd_set reads, writes, errors;
    struct timeval timeout;
    int result;
    FD_ZERO(&reads); FD_ZERO(&writes); FD_ZERO(&errors);
    FD_SET(sWorld.fd, &reads);
    FD_SET(sWorld.fd, &errors);
    if (sWorld.connecting) FD_SET(sWorld.fd, &writes);
    timeout.tv_sec = 0;
    timeout.tv_usec = headless ? 1000 : 0;
    result = select(0, &reads, &writes, &errors, &timeout);
    if (result == SOCKET_ERROR) {
        if (WSAGetLastError() != WSAEINTR) Disconnect();
        return;
    }
    if (sWorld.connecting) {
        int error = 0, len = sizeof(error);
        if (!FD_ISSET(sWorld.fd, &writes) && !FD_ISSET(sWorld.fd, &errors)) return;
        if (getsockopt(sWorld.fd, SOL_SOCKET, SO_ERROR, (char *)&error, &len) == SOCKET_ERROR || error) {
            Disconnect(); return;
        }
        sWorld.connecting = FALSE;
    } else if (FD_ISSET(sWorld.fd, &errors)) { Disconnect(); return; }
#else
    struct pollfd pfd;
    pfd.fd = sWorld.fd;
    pfd.events = POLLIN | (sWorld.connecting ? POLLOUT : 0);
    pfd.revents = 0;
    /* Enabled headless execution yields at most 1 ms per frame to the server. */
    if (poll(&pfd, 1, headless ? 1 : 0) < 0) return;
    if (sWorld.connecting) {
        int error = 0;
        socklen_t len = sizeof(error);
        if (!(pfd.revents & (POLLOUT | POLLERR | POLLHUP))) return;
        if (getsockopt(sWorld.fd, SOL_SOCKET, SO_ERROR, &error, &len) < 0 || error) { Disconnect(); return; }
        sWorld.connecting = FALSE;
    }
#endif
    Flush();
    while (SocketOpen() && budget < WB_BUFFER) {
#ifdef _WIN32
        int n;
#else
        ssize_t n;
#endif
        size_t used = 0, i;
        if (sWorld.inputSize == sizeof(sWorld.input) - 1) { Disconnect(); return; }
        n = recv(sWorld.fd, sWorld.input + sWorld.inputSize, (int)(sizeof(sWorld.input) - 1 - sWorld.inputSize), 0);
        if (n < 0) {
#ifdef _WIN32
            int error = WSAGetLastError();
            if (error != WSAEWOULDBLOCK && error != WSAEINTR) Disconnect();
#else
            if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) Disconnect();
#endif
            return;
        }
        if (!n) { Disconnect(); return; }
        budget += n;
        for (i = sWorld.inputSize; i < sWorld.inputSize + n; i++)
            if ((unsigned char)sWorld.input[i] < 32 && sWorld.input[i] != '\n') { Disconnect(); return; }
        sWorld.inputSize += n;
        for (i = 0; i < sWorld.inputSize; i++) if (sWorld.input[i] == '\n') {
            sWorld.input[i] = 0;
            if (sWorld.staging) {
                sWorld.stagedBytes += i + 1 - used;
                if (sWorld.stagedBytes > WB_BUFFER) { Disconnect(); return; }
            }
            if (!Line(sWorld.input + used)) { Disconnect(); return; }
            used = i + 1;
        }
        if (used) {
            memmove(sWorld.input, sWorld.input + used, sWorld.inputSize - used);
            sWorld.inputSize -= used;
        }
    }
}

/* The server HASH field is a 16-hex-digit opaque FNV-1a change fingerprint,
 * not a cryptographic integrity claim. Authentication uses the separate token. */
static void Fingerprint(const void *data, size_t size, char out[17])
{
    const u8 *p = data;
    u64 hash = 0xcbf29ce484222325ULL;
    size_t i;
    for (i = 0; i < size; i++) hash = (hash ^ p[i]) * 0x100000001b3ULL;
    snprintf(out, 17, "%016llx", (unsigned long long)hash);
}

int WorldBridge_ChatCommandAllowed(const char *target, const char *text)
{
    return sWorld.connected && sWorld.chatAvailable
        && ChatCommandGate_Allowed(sWorld.live.commandMask, target, text);
}

int WorldBridge_ChatSend(const char *target, const char *text)
{
    char hex[241];
    size_t i, length = strlen(text);
    bool8 visible = FALSE;
    if (!sWorld.connected || !sWorld.chatAvailable || sWorld.outputSize || !length || length > 120
     || (strcmp(target, "*") && !Identifier(target)) || sWorld.seq == UINT_MAX) return 0;
    for (i = 0; i < length; i++) {
        unsigned c = (unsigned char)text[i];
        if (c < 32 || c > 126) return 0;
        if (c != 32) visible = TRUE;
        hex[2*i] = "0123456789abcdef"[c >> 4];
        hex[2*i+1] = "0123456789abcdef"[c & 15];
    }
    if (!visible || !WorldBridge_ChatCommandAllowed(target, text)) return 0;
    hex[2*i] = 0;
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "CHAT %u %s %s\n", ++sWorld.seq, target, hex);
    Flush();
    return 1;
}

bool8 WorldBridge_RallySend(unsigned action, unsigned id, unsigned arg)
{
    if (!sWorld.connected || !sWorld.rallyAvailable || sWorld.outputSize || sWorld.seq == UINT_MAX
     || action > WORLD_RALLY_FAIL || arg > 3) return FALSE;
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "RALLY %u %u %u %u\n", ++sWorld.seq, action, id, arg);
    Flush();
    return TRUE;
}

bool8 WorldBridge_RallySnapshot(struct WorldRallySnapshot *out)
{
    if (!out || !sWorld.connected || sWorld.snapshotAge > 180 || !sWorld.live.rallySeen) return FALSE;
    *out = sWorld.live.rally;
    return TRUE;
}

unsigned WorldBridge_ChatCount(void)
{
    return sWorld.live.chatCount;
}

const char *WorldBridge_ChatStatus(void)
{
    return !sWorld.connected ? "offline" : !sWorld.chatAvailable ? "unsupported" : sWorld.live.chatStatus;
}

void WorldBridge_ChatLine(unsigned index, char *out, unsigned size)
{
    const struct ChatMessage *message;
    if (!size) return;
    out[0] = 0;
    if (index >= sWorld.live.chatCount) return;
    message = &sWorld.live.chat[index];
    if (!strcmp(message->target, "*"))
        snprintf(out, size, "%s: %s", message->sender, message->text);
    else
        snprintf(out, size, "%s > %s: %s", message->sender, message->target, message->text);
}


#if GENERATED_MAP_READY
static void CavePump(void)
{
    if (!sWorld.connected) return;
#if GENERATED_WILDS_EVENTS
#if GENERATED_WILDS_SHARED_TERRAIN
    if(sWorld.terrainPending && sWorld.caveState==CAVE_READY) {
        if(!GeneratedMap_IsInside() && !GeneratedMap_EntryPending()) {
            if(!GeneratedMap_StageSharedTerrain(sWorld.terrainData,sWorld.terrainSize)){Disconnect();return;}
            sWorld.terrainPending=FALSE;sWorld.terrainReportPending=TRUE;sWorld.terrainReportedApplied=FALSE;
        } else if(GeneratedMap_IsInside() && Ready()) {
            if(!GeneratedMap_ApplySharedTerrain(sWorld.terrainData,sWorld.terrainSize)){Disconnect();return;}
            sWorld.terrainPending=FALSE;sWorld.terrainReportPending=TRUE;sWorld.terrainReportedApplied=TRUE;
        }
    }
    if(sWorld.caveV9TProbe && sWorld.caveState==CAVE_READY && !sWorld.terrainPending) {
        if(GeneratedMap_IsInside() && Ready() && !sWorld.terrainReportedApplied) {sWorld.terrainReportPending=TRUE;sWorld.terrainReportedApplied=TRUE;}
        if(sWorld.terrainReportPending && !sWorld.outputSize) {
            sWorld.outputSize=snprintf(sWorld.output,sizeof(sWorld.output),"CAVE TERRAINACK %s %u %s\n",sWorld.caveWire.id,(unsigned)sWorld.terrainRevision,sWorld.terrainReportedApplied ? "APPLIED" : "STAGED");
            sWorld.terrainReportPending=FALSE;Flush();
        }
    }
#endif
    if(sWorld.eventCount) {
        if(sWorld.caveState!=CAVE_READY || sWorld.caveWire.version!=9 || !GeneratedMap_IsInside())sWorld.eventHead=sWorld.eventCount=0;
        else if(Ready() && !sWorld.outputSize) {unsigned i=sWorld.eventHead;bool8 applied=FALSE;
            if(sWorld.eventQueue[i].kind==1)applied=GeneratedMap_SetSharedEventState(sWorld.eventQueue[i].state);
            else if(sWorld.eventQueue[i].kind==2)applied=GeneratedMap_SetSharedEventRule(sWorld.eventQueue[i].rule,61);
            else if(sWorld.eventQueue[i].kind==3)applied=GeneratedMap_SetSharedEventTile(sWorld.eventQueue[i].x,sWorld.eventQueue[i].y,sWorld.eventQueue[i].terrain);
            else if(sWorld.eventQueue[i].kind==4)applied=GeneratedMap_SetSharedEventTiles(sWorld.eventQueue[i].tiles,sWorld.eventQueue[i].tilesSize);
            sWorld.outputSize=snprintf(sWorld.output,sizeof(sWorld.output),"CAVE EVENTACK %s %u %s\n",sWorld.caveWire.id,sWorld.eventQueue[i].sequence,applied ? "APPLIED" : "REJECTED");
            sWorld.eventHead=(i+1)%8;sWorld.eventCount--;Flush();
        }
    }
#endif
    if (sWorld.caveState == CAVE_MISMATCH || sWorld.caveState == CAVE_RETURN_NONE) {
        /* A warp can still be entering the old cave even before its map ID
         * changes. Never acknowledge a replacement during that window. */
        if (GeneratedMap_EntryPending()) return;
        if (GeneratedMap_IsInside()) {
            if (!sWorld.caveReturning && Ready() && GeneratedMap_Leave()) sWorld.caveReturning = TRUE;
            return;
        }
        sWorld.caveReturning = FALSE;
        if (sWorld.caveState == CAVE_MISMATCH) {
#if GENERATED_WORLD_XL
            if (sWorld.caveWire.version == 10) {
                if (!GeneratedMap_StageSharedXLWilds(sWorld.caveWire.cells, WORLD_CAVE_XL_CELLS)) { Disconnect(); return; }
            } else
#endif
#if GENERATED_WILDS_EVENTS && GENERATED_CAVE_WILDLIFE
            if (sWorld.caveWire.version == 9) {
                if (!GeneratedMap_StageSharedEventWilds(sWorld.caveWire.events, WORLD_CAVE_EVENT_BYTES, sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) { Disconnect(); return; }
#if GENERATED_WILDS_SHARED_TERRAIN
                if(sWorld.caveV9TProbe) {
                    if(!sWorld.caveWire.terrainSeen) { Disconnect();return; }
#if GENERATED_WILDS_SHARED_GEOMETRY
                    if(!sWorld.caveV9GProbe && ((sWorld.caveWire.terrainRevision>0 && sWorld.caveWire.terrain[0]==0) || GeneratedMap_SharedTerrainNeedsGeometry(sWorld.caveWire.terrain,sWorld.caveWire.terrainSize))) { Disconnect();return; }
#endif
                    if(!GeneratedMap_StageSharedTerrain(sWorld.caveWire.terrain,sWorld.caveWire.terrainSize)) { Disconnect();return; }
                    sWorld.terrainRevision=sWorld.caveWire.terrainRevision;sWorld.terrainPending=FALSE;sWorld.terrainReportPending=TRUE;sWorld.terrainReportedApplied=FALSE;
                }
#endif
            } else
#endif
#if GENERATED_WILDS_CAST && GENERATED_CAVE_WILDLIFE
            if (sWorld.caveWire.version == 8) {
                if (!GeneratedMap_StageSharedCastWilds(sWorld.caveWire.cast, WORLD_CAVE_CAST_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) { Disconnect(); return; }
            } else
#endif
#if GENERATED_WILDS_GUIDE && GENERATED_CAVE_WILDLIFE
            if (sWorld.caveWire.version == 7) {
                if (!GeneratedMap_StageSharedGuidedWilds(sWorld.caveWire.guide, WORLD_CAVE_GUIDE_BYTES, sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) { Disconnect(); return; }
            } else
#endif
#if GENERATED_MAP_WILDS && GENERATED_CAVE_WILDLIFE
            if (sWorld.caveWire.version == 6) {
                if (!GeneratedMap_StageSharedWildsTemplate(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) { Disconnect(); return; }
            } else
#endif
#if GENERATED_MAP_LARGE && GENERATED_CAVE_WILDLIFE
            if (sWorld.caveWire.version == 4 || sWorld.caveWire.version == 5) {
                if (!GeneratedMap_StageSharedLargeTemplate(sWorld.caveWire.cells, WORLD_CAVE_LARGE_CELLS)) { Disconnect(); return; }
            } else
#endif
            if (!GeneratedMap_StageTemplate(sWorld.caveWire.cells, WORLD_CAVE_CELLS)) { Disconnect(); return; }
#if GENERATED_CAVE_PROFILES
            if ((sWorld.caveWire.version == 2 || sWorld.caveWire.version == 3 || sWorld.caveWire.version == 5) && !GeneratedMap_SetSharedEncounterProfile(sWorld.caveWire.profile)) { Disconnect(); return; }
#endif
#if GENERATED_CAVE_WILDLIFE
            if ((sWorld.caveWire.version == 3 || sWorld.caveWire.version == 5) && !GeneratedMap_SetSharedWildlife(sWorld.caveWire.wildlife, WORLD_CAVE_WILDLIFE_BYTES)) { Disconnect(); return; }
#endif
            sWorld.caveState = CAVE_ACK;
        } else sWorld.caveState = CAVE_DISABLED;
    }
    if (sWorld.caveState == CAVE_WAIT_RESET && sWorld.caveTimeout && --sWorld.caveTimeout == 0)
        sWorld.caveState = CAVE_IDLE;
    if ((sWorld.caveState == CAVE_WAIT || sWorld.caveState == CAVE_WAIT_OK)
     && sWorld.caveTimeout && --sWorld.caveTimeout == 0) { Disconnect(); return; }
    if (sWorld.caveRetry) { sWorld.caveRetry--; return; }
    if (sWorld.outputSize) return;
    if (sWorld.caveState == CAVE_IDLE) {
        WorldCaveWire_Reset(&sWorld.caveWire);
        sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output), "CAVE GET\n");
        sWorld.caveState = CAVE_WAIT;sWorld.caveTimeout = 600;Flush();
    } else if (sWorld.caveState == CAVE_ACK) {
        sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output), "CAVE ACK %s\n", sWorld.caveWire.id);
        sWorld.caveState = CAVE_WAIT_OK;sWorld.caveTimeout = 600;Flush();
    }
}
#endif

static void SendState(void)
{
    const struct Peer *p = &sWorld.field;
    char party[17], bag[17];
    bool8 ready;
    if (!sWorld.connected || sWorld.outputSize) return;
#if GENERATED_MAP_READY
    /* Do not rely on frame ordering: no call site may publish a stale cave
     * position before this connection has acknowledged its exact layout. */
    if (GeneratedMap_IsInside() && !WorldBridge_GeneratedCaveReady())
        sWorld.fieldKnown = sWorld.menuAnchor = FALSE;
#endif
    /* Pending encounters lock controls but retain authoritative tag range.
     * Never revive a revoked or unsafe field position. */
    ready = sWorld.fieldKnown && Overworld()
        && (PresenceReady() || WorldActivity_IsEncounterPending());
    Fingerprint(gPlayerParty, sizeof(gPlayerParty), party);
    if (gSaveBlock1Ptr)
        Fingerprint(gSaveBlock1Ptr->bagPocket_Items,
                    sizeof(gSaveBlock1Ptr->bagPocket_Items) + sizeof(gSaveBlock1Ptr->bagPocket_KeyItems)
                  + sizeof(gSaveBlock1Ptr->bagPocket_PokeBalls) + sizeof(gSaveBlock1Ptr->bagPocket_TMHM)
                  + sizeof(gSaveBlock1Ptr->bagPocket_Berries), bag);
    else Fingerprint(NULL, 0, bag);
    sWorld.outputSize = snprintf(sWorld.output, sizeof(sWorld.output),
        "%s %u %u %u %u %u %u %u %u %s %s\n", sWorld.fieldKnown && !ready ? "FIELD" : "STATE", ++sWorld.seq,
        sWorld.fieldKnown ? p->group : 0, sWorld.fieldKnown ? p->num : 0,
        sWorld.fieldKnown ? p->x : 0, sWorld.fieldKnown ? p->y : 0,
        sWorld.fieldKnown ? p->facing : 1, sWorld.fieldKnown ? p->gfx : OBJ_EVENT_GFX_BOY_1,
        ready, party, bag);
    Flush();
}

/* A world may contain many more humans than the wire relevance window or
 * stock sixteen-object pool. Spend only genuinely free/owned slots, nearest
 * humans first, shared objects second. Never evict a campaign NPC. */
static unsigned SelectPeers(unsigned order[WB_REMOTES])
{
    unsigned i, j, count = 0, capacity = 0, humans = 0, selected = 0;
    unsigned limit = sWorld.visiblePeers ? sWorld.visiblePeers : WB_PEERS;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        bool8 ours = FALSE;
        for (j = 0; j < WB_REMOTES; j++)
            if (Owned(j) && sWorld.remotes[j].object == i) ours = TRUE;
        if (!gObjectEvents[i].active || ours) capacity++;
    }
    for (i = 0; i < sWorld.live.peerCount; i++) {
        const struct Peer *p = &sWorld.live.peers[i];
        unsigned distance = abs((int)p->x - (int)sWorld.field.x) + abs((int)p->y - (int)sWorld.field.y);
        if (p->group != (unsigned)sWorld.group || p->num != (unsigned)sWorld.num
         || !GridCoords(p->x, p->y) || NativeNpcAt(p->x, p->y)) continue;
        for (j = count; j; j--) {
            const struct Peer *q = &sWorld.live.peers[order[j - 1]];
            unsigned other = abs((int)q->x - (int)sWorld.field.x) + abs((int)q->y - (int)sWorld.field.y);
            if ((p->id[0] == '@') > (q->id[0] == '@')
             || ((p->id[0] == '@') == (q->id[0] == '@') && distance >= other)) break;
            order[j] = order[j - 1];
        }
        order[j] = i;
        count++;
    }
    for (i = 0; i < count && selected < capacity; i++) {
        if (sWorld.live.peers[order[i]].id[0] != '@' && humans++ >= limit) continue;
        order[selected++] = order[i];
    }
    return selected;
}

#if WORLD_SMOOTH_PRESENCE
// Limit walking animation to graphics with known standard animation tables.
static bool8 RemoteWalkAnimationSafe(u8 gfx)
{
    switch (gfx)
    {
    case OBJ_EVENT_GFX_BOY_1:
    case OBJ_EVENT_GFX_BRENDAN_NORMAL:
    case OBJ_EVENT_GFX_BRENDAN_MACH_BIKE:
    case OBJ_EVENT_GFX_BRENDAN_ACRO_BIKE:
    case OBJ_EVENT_GFX_MAY_NORMAL:
    case OBJ_EVENT_GFX_MAY_MACH_BIKE:
    case OBJ_EVENT_GFX_MAY_ACRO_BIKE:
        return TRUE;
    default:
        return FALSE;
    }
}
#endif

static void SyncEngine(void)
{
    unsigned i, j, k, order[WB_REMOTES], selected;
    bool8 updateTiles, fieldLocked;
    /* Our own modal owns the field lock. Keep its NPC alive, but do not
     * mutate engine objects or map tiles while the text task is running. */
    if (sWorld.dialogueActive && Overworld()) return;
    /* Native scripts can add objects after yielding. Return their pool slots
     * before the next command, but keep trainers visible during field menus. */
    if (!Overworld() || gPaletteFade.active || ScriptContext_IsEnabled()) {
        for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
        RestoreTiles();
        sWorld.tilesLive = FALSE;
        return;
    }
    fieldLocked = ArePlayerFieldControlsLocked();
    if (fieldLocked) {
        RestoreTiles();
        sWorld.tilesLive = FALSE;
    }
    updateTiles = !fieldLocked && (!SameGrid() || !sWorld.tilesLive || sWorld.appliedGeneration != sWorld.generation);
    if (!SameGrid()) {
        sWorld.appliedCount = 0;
        /* The engine may reuse both object and sprite slots after a map load.
         * Ownership also requires the map IDs and our sprite marker. */
        for (i = 0; i < WB_REMOTES; i++) if (!Owned(i)) memset(&sWorld.remotes[i], 0, sizeof(sWorld.remotes[i]));
    }
    if (updateTiles) {
        sWorld.restoredCount = 0;
        RestoreTiles();
    }
    sWorld.layout = gMapHeader.mapLayout;
    sWorld.grid = gBackupMapLayout.map;
    sWorld.group = gSaveBlock1Ptr->location.mapGroup;
    sWorld.num = gSaveBlock1Ptr->location.mapNum;
    selected = SelectPeers(order);
    for (i = 0; i < WB_REMOTES; i++) {
        struct Remote *r = &sWorld.remotes[i];
        const struct Peer *p = NULL;
        for (j = 0; j < selected; j++)
            if (!strcmp(r->id, sWorld.live.peers[order[j]].id)) p = &sWorld.live.peers[order[j]];
        if (!p || p->group != (unsigned)sWorld.group || p->num != (unsigned)sWorld.num)
            RemoveRemote(i);
        else if (!Owned(i)) memset(r, 0, sizeof(*r));
    }
    for (k = 0; k < selected; k++) {
        const struct Peer *p = &sWorld.live.peers[order[k]];
        struct Remote *r = NULL;
        struct ObjectEvent *o;
        u8 gfx;
        if (p->group != (unsigned)sWorld.group || p->num != (unsigned)sWorld.num || !GridCoords(p->x, p->y)) continue;
        /* Never place a template-less remote over a real scripted NPC. Vanilla
         * could otherwise select our object first when A is passed through. */
        if (NativeNpcAt(p->x, p->y)) {
            for (i = 0; i < WB_REMOTES; i++)
                if (!strcmp(sWorld.remotes[i].id, p->id)) RemoveRemote(i);
            continue;
        }
        for (i = 0; i < WB_REMOTES; i++) if (!strcmp(sWorld.remotes[i].id, p->id)) { r = &sWorld.remotes[i]; break; }
        if (!r) {
            for (i = 0; i < WB_REMOTES; i++) {
                unsigned id;
                bool8 collision = FALSE;
                if (sWorld.remotes[i].id[0]) continue;
                /* A native object or template may own one reserved local ID.
                 * Skip that ID, not this peer: later slots can still host it. */
                for (id = 0; id < OBJECT_EVENTS_COUNT; id++)
                    if (gObjectEvents[id].active && gObjectEvents[id].localId == WB_LOCALID + i) collision = TRUE;
                if (gMapHeader.events) for (id = 0; id < gMapHeader.events->objectEventCount; id++)
                    if (gSaveBlock1Ptr->objectEventTemplates[id].localId == WB_LOCALID + i) collision = TRUE;
                if (!collision) { r = &sWorld.remotes[i]; break; }
            }
            if (!r) continue;
        }
        /* Standard NPC palettes cannot overwrite the local avatar's palette.
         * The fallback is deliberately a normal trainer, never a dynamic GFX ID. */
        gfx = OBJ_EVENT_GFX_BOY_1;
        if (p->gfx < NUM_OBJ_EVENT_GFX && GetObjectEventGraphicsInfo(p->gfx)->paletteSlot >= PALSLOT_NPC_1
         && GetObjectEventGraphicsInfo(p->gfx)->paletteSlot <= PALSLOT_NPC_4
         && !GetObjectEventGraphicsInfo(p->gfx)->inanimate) gfx = p->gfx;
#if WORLD_EXTENDED_OBJECTS && WORLD_MATCHED_TRAINERS
        else if (p->gfx < NUM_OBJ_EVENT_GFX && WorldPlayerPaletteCompatible(p->gfx)) gfx = p->gfx;
#endif
        /* A different size needs a fresh OBJ allocation. Replace it during
         * this reconciliation, rather than hiding the peer for a frame. */
        if (r->id[0] && Owned(i) && gObjectEvents[r->object].graphicsId != gfx)
            RemoveRemote(i);
        if (!r->id[0]) {
            u8 id;
            bool8 collision = FALSE;
            /* Both live objects and map templates must leave this local ID unused. */
            for (id = 0; id < OBJECT_EVENTS_COUNT; id++) if (gObjectEvents[id].active && gObjectEvents[id].localId == WB_LOCALID + i) collision = TRUE;
            if (gMapHeader.events) for (id = 0; id < gMapHeader.events->objectEventCount; id++)
                if (gSaveBlock1Ptr->objectEventTemplates[id].localId == WB_LOCALID + i) collision = TRUE;
            if (collision) continue;
#if WORLD_EXTENDED_OBJECTS
            id = SpawnWorldObjectEventParameterized(gfx, MOVEMENT_TYPE_NONE, WB_LOCALID + i,
#else
            id = SpawnSpecialObjectEventParameterized(gfx, MOVEMENT_TYPE_NONE, WB_LOCALID + i,
#endif
                p->x + MAP_OFFSET, p->y + MAP_OFFSET, MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET));
            if (id >= OBJECT_EVENTS_COUNT) continue;
            strcpy(r->id, p->id);
            r->object = id; r->sprite = gObjectEvents[id].spriteId;
            r->group = p->group; r->num = p->num;
            gSprites[r->sprite].data[7] = WB_MARKER;
        }
        if (!Owned(i)) continue;
        o = &gObjectEvents[r->object];
        if (o->currentCoords.x != (int)p->x + MAP_OFFSET || o->currentCoords.y != (int)p->y + MAP_OFFSET)
        {
#if WORLD_SMOOTH_PRESENCE
            int dx = (int)p->x + MAP_OFFSET - o->currentCoords.x;
            int dy = (int)p->y + MAP_OFFSET - o->currentCoords.y;
            // Interpolate only adjacent human steps. Authority, collision and
            // interaction positions remain at the committed destination.
            if (r->id[0] != '@' && RemoteWalkAnimationSafe(o->graphicsId) && ((dx == 0 && (dy == -1 || dy == 1))
                                  || (dy == 0 && (dx == -1 || dx == 1))))
            {
                int nextX = r->motionX - 16 * dx;
                int nextY = r->motionY - 16 * dy;
                if (nextX >= -32 && nextX <= 32 && nextY >= -32 && nextY <= 32)
                {
                    r->motionX = nextX; r->motionY = nextY;
                    r->motionDirection = dx < 0 ? DIR_WEST : dx > 0 ? DIR_EAST
                                             : dy < 0 ? DIR_NORTH : DIR_SOUTH;
                }
                else r->motionX = r->motionY = 0;
            }
            else r->motionX = r->motionY = 0;
#endif
            MoveObjectEventToMapCoords(o, p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        }
        o->initialCoords = o->currentCoords;
        o->currentElevation = o->previousElevation = MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        if (o->facingDirection != p->facing) ObjectEventTurn(o, p->facing);
    }
    if (!updateTiles) return;
    sWorld.tilesLive = TRUE;
    sWorld.appliedGeneration = sWorld.generation;
    for (i = 0; i < sWorld.live.tileCount; i++) {
        const struct Tile *t = &sWorld.live.tiles[i];
        struct Applied *a;
        if (t->group != (unsigned)sWorld.group || t->num != (unsigned)sWorld.num || !GridCoords(t->x, t->y)
         || !WorldCatalog_Metatile(t->group, t->num, t->metatile)) continue;
        a = &sWorld.applied[sWorld.appliedCount++];
        a->tile = *t;
        a->original = Raw(t->x, t->y);
        MapGridSetMetatileIdAt(t->x + MAP_OFFSET, t->y + MAP_OFFSET, t->metatile | (t->collision ? MAPGRID_IMPASSABLE : 0));
        a->raw = Raw(t->x, t->y);
        CurrentMapDrawMetatileAt(t->x + MAP_OFFSET, t->y + MAP_OFFSET);
    }
}

static bool8 FacingObject(const struct ObjectEvent *p, const struct ObjectEvent *o)
{
    int dx = o->currentCoords.x - p->currentCoords.x;
    int dy = o->currentCoords.y - p->currentCoords.y;
    return ((dx == 0 && dy == 1 && p->facingDirection == DIR_SOUTH)
         || (dx == 0 && dy == -1 && p->facingDirection == DIR_NORTH)
         || (dy == 0 && dx == -1 && p->facingDirection == DIR_WEST)
         || (dy == 0 && dx == 1 && p->facingDirection == DIR_EAST))
        && (!o->currentElevation || !p->currentElevation || o->currentElevation == p->currentElevation);
}

/* Match the field engine's reach before shielding template-less remotes.
 * Two-tile lookups are possible only through a counter, not a sign or PC.
 * Objects on another elevation are not candidates for that lookup. */
static bool8 InteractionTarget(const struct ObjectEvent *p, const struct ObjectEvent *o)
{
    int dx = o->currentCoords.x - p->currentCoords.x;
    int dy = o->currentCoords.y - p->currentCoords.y;
    if (FacingObject(p, o)) return TRUE;
    if (o->currentElevation && p->currentElevation && o->currentElevation != p->currentElevation) return FALSE;
    if (!((dx == 0 && dy == 2 && p->facingDirection == DIR_SOUTH)
       || (dx == 0 && dy == -2 && p->facingDirection == DIR_NORTH)
       || (dy == 0 && dx == -2 && p->facingDirection == DIR_WEST)
       || (dy == 0 && dx == 2 && p->facingDirection == DIR_EAST))) return FALSE;
    return MetatileBehavior_IsCounter(MapGridGetMetatileBehaviorAt(
        p->currentCoords.x + dx / 2, p->currentCoords.y + dy / 2));
}

/* This runs only after the game loop, never from the raw key reader. */
static void SyncDialogue(void)
{
    unsigned i, j;
    char talkPeer[25];
    bool8 talk = WorldActivity_TakeTalkRequest(talkPeer);
    const struct Meeting *meeting = &sWorld.live.meeting;
    if (WorldActivity_OwnsFieldInput() || WorldTravel_OwnsFieldInput()) {
        sWorld.shownMeeting = meeting->seq;
        sWorld.pendingObject[0] = 0;
        sWorld.dialogueKeys = 0;
        return;
    }
    if (talk) strcpy(sWorld.pendingObject, talkPeer);
    if (sWorld.socialCooldown) sWorld.socialCooldown--;
    if (sWorld.meetingAge < 180) sWorld.meetingAge++;
    if (sWorld.dialogueActive) {
        if (!Overworld()) {
            /* A reset owns the new UI and its lock, not this old dialogue. */
            sWorld.dialogueActive = FALSE;
        } else if (!sWorld.connected || (sWorld.dialogueMeeting && meeting->seq != sWorld.dialogueMeeting)
                || (sWorld.dialogueKeys && IsFieldMessageBoxHidden())) {
            HideFieldMessageBox();
            UnlockPlayerFieldControls();
            sWorld.dialogueActive = FALSE;
        }
    } else if (meeting->seq && meeting->seq > sWorld.shownMeeting && sWorld.meetingAge < 180
            && Ready() && sWorld.connected && IsFieldMessageBoxHidden()) {
        const struct ObjectEvent *player = &gObjectEvents[gPlayerAvatar.objectEventId];
        int dx = (int)meeting->x + MAP_OFFSET - player->currentCoords.x;
        int dy = (int)meeting->y + MAP_OFFSET - player->currentCoords.y;
        sWorld.shownMeeting = meeting->seq;
        /* Only a committed authority signal can open this native modal. Never
         * interrupt another UI, or show it after the player walks away. */
        if (meeting->group == (unsigned)gSaveBlock1Ptr->location.mapGroup
         && meeting->num == (unsigned)gSaveBlock1Ptr->location.mapNum
         && abs(dx) + abs(dy) <= 1) {
            const char *other = !strcmp(meeting->player, sWorld.trainer) ? meeting->target : meeting->player;
            snprintf(sWorld.dialogueLiteral, sizeof(sWorld.dialogueLiteral), "%s\nLet's explore together!", other);
            EncodeText(sWorld.dialogueLiteral, sWorld.dialogueText);
            if (ShowFieldMessage(sWorld.dialogueText)) {
                strcpy(sWorld.dialogueObject, other);
                sWorld.dialogueMeeting = meeting->seq;
                sWorld.dialogueActive = TRUE;
                LockPlayerFieldControls();
            }
        }
    } else if (sWorld.pendingObject[0] && Ready() && sWorld.connected && !sWorld.outputSize
            && IsFieldMessageBoxHidden()) {
        for (i = 0; i < WB_REMOTES; i++) {
            const struct Remote *r = &sWorld.remotes[i];
            if (strcmp(r->id, sWorld.pendingObject) || !Owned(i)
             || !FacingObject(&gObjectEvents[gPlayerAvatar.objectEventId], &gObjectEvents[r->object])) continue;
            for (j = 0; j < sWorld.live.peerCount; j++) {
                const struct Peer *p = &sWorld.live.peers[j];
                if (strcmp(p->id, r->id) || !p->ready
                 || p->group != (unsigned)gSaveBlock1Ptr->location.mapGroup
                 || p->num != (unsigned)gSaveBlock1Ptr->location.mapNum
                 || (int)p->x + MAP_OFFSET != gObjectEvents[r->object].currentCoords.x
                 || (int)p->y + MAP_OFFSET != gObjectEvents[r->object].currentCoords.y) continue;
                if (r->id[0] != '@') {
                    if (!talk && WorldActivity_Interact(r->id)) break;
                    if (sWorld.socialCooldown) break;
                    SendState();
                    if (sWorld.connected) {
                        sWorld.outputSize += snprintf(sWorld.output + sWorld.outputSize,
                            sizeof(sWorld.output) - sWorld.outputSize, "MEET %u %s\n", ++sWorld.seq, r->id);
                        sWorld.interactionSeq = sWorld.seq;
                        sWorld.socialCooldown = 60;
                        Flush();
                    }
                    break;
                }
                EncodeText(p->text, sWorld.dialogueText);
                if (!ShowFieldMessage(sWorld.dialogueText)) break;
                /* Publish the precise ready position before taking our modal
                 * lock. Both messages share one monotonically increasing seq. */
                SendState();
                if (sWorld.connected) {
                    sWorld.outputSize += snprintf(sWorld.output + sWorld.outputSize,
                        sizeof(sWorld.output) - sWorld.outputSize, "INTERACT %u %s\n", ++sWorld.seq, r->id + 1);
                    sWorld.interactionSeq = sWorld.seq;
                    Flush();
                }
                strcpy(sWorld.dialogueObject, r->id + 1);
                strcpy(sWorld.dialogueLiteral, p->text);
                sWorld.dialogueMeeting = 0;
                sWorld.dialogueActive = TRUE;
                LockPlayerFieldControls();
                break;
            }
            break;
        }
    }
    sWorld.pendingObject[0] = 0;
    sWorld.dialogueKeys = 0;
}

u16 WorldBridge_FilterInput(u16 keys)
{
    unsigned i, j;
    bool8 adjacentRemote = FALSE;
    const struct ObjectEvent *p;
    u16 pressed = keys & ~sWorld.previousKeys;
    if (!sWorld.enabled) return keys;
    sWorld.previousKeys = keys;
    if (WorldTravel_OwnsFieldInput()) return 0;
    if (WorldActivity_OwnsFieldInput()) return keys;
    if (sWorld.dialogueActive) {
        sWorld.dialogueKeys |= pressed & (A_BUTTON | B_BUTTON);
        return keys & (A_BUTTON | B_BUTTON);
    }
    if (!(keys & A_BUTTON) || !Ready() || !IsFieldMessageBoxHidden()) return keys;
    p = &gObjectEvents[gPlayerAvatar.objectEventId];
    for (i = 0; i < WB_REMOTES; i++)
        if (Owned(i) && FacingObject(p, &gObjectEvents[sWorld.remotes[i].object])) adjacentRemote = TRUE;
    /* An ordinary map NPC always wins, even if a remote overlaps it or stands
     * behind it. A farther NPC cannot win through an adjacent remote: the
     * engine looks at that object's missing template before trying a counter. */
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        const struct ObjectEvent *o = &gObjectEvents[i];
        bool8 remote = FALSE;
        if (!o->active || o->isPlayer || !InteractionTarget(p, o)) continue;
        if (adjacentRemote && !FacingObject(p, o)) continue;
        for (j = 0; j < WB_REMOTES; j++)
            if (Owned(j) && sWorld.remotes[j].object == i) remote = TRUE;
        if (!remote) return keys;
    }
    for (i = 0; i < WB_REMOTES; i++) if (Owned(i)) {
        const struct ObjectEvent *o = &gObjectEvents[sWorld.remotes[i].object];
        /* Dynamic peers have no map-script template. Do not pass them to the
         * vanilla interaction lookup, including through a counter tile. */
        if (InteractionTarget(p, o)) {
            if ((pressed & A_BUTTON) && FacingObject(p, o)
#if GENERATED_MAP_READY
             && !GeneratedMap_IsInside()
#endif
               ) strcpy(sWorld.pendingObject, sWorld.remotes[i].id);
            return keys & ~A_BUTTON;
        }
    }
    return keys;
}

void WorldBridge_WriteJSON(FILE *file, u32 frame)
{
    unsigned i, count = 0;
    const struct ObjectEvent *p = Overworld() ? &gObjectEvents[gPlayerAvatar.objectEventId] : NULL;
    fprintf(file, "{\"chat_count\":%u,\"in_battle\":%s,\"trainer\":\"%s\",\"frame\":%u,\"connected\":%s,\"revision\":%u,\"ready\":%s,\"map\":[%d,%d],\"pos\":[%d,%d],\"peers\":[",
        sWorld.live.chatCount, gMain.inBattle ? "true" : "false",
        sWorld.trainer, frame, sWorld.connected ? "true" : "false", sWorld.live.revision, Ready() ? "true" : "false",
        gSaveBlock1Ptr ? gSaveBlock1Ptr->location.mapGroup : -1, gSaveBlock1Ptr ? gSaveBlock1Ptr->location.mapNum : -1,
        p ? p->currentCoords.x - MAP_OFFSET : 0, p ? p->currentCoords.y - MAP_OFFSET : 0);
    for (i = 0; i < WB_REMOTES; i++) if (Overworld() && Owned(i) && sWorld.remotes[i].id[0] != '@') {
        const struct Remote *r = &sWorld.remotes[i];
        const struct ObjectEvent *o = &gObjectEvents[r->object];
        fprintf(file, "%s{\"trainer\":\"%s\",\"object_id\":%u,\"local_id\":%u,\"sprite_id\":%u,\"gfx\":%u,\"map\":[%u,%u],\"pos\":[%d,%d],\"sprite_pos\":[%d,%d],\"visible\":%s}",
            count++ ? "," : "", r->id, r->object, o->localId, o->spriteId, o->graphicsId, o->mapGroup, o->mapNum,
            o->currentCoords.x - MAP_OFFSET, o->currentCoords.y - MAP_OFFSET,
            gSprites[o->spriteId].x, gSprites[o->spriteId].y, gSprites[o->spriteId].invisible ? "false" : "true");
    }
    /* Public roster survives allocation exhaustion. No team, bag, credentials
     * or partner data: only the already-public PEER position/readiness. */
    fprintf(file, "],\"visible_peer_limit\":%u,\"peer_wire_limit\":%u,\"roster\":[", sWorld.visiblePeers, WB_PEERS);
    count = 0;
    for (i = 0; i < sWorld.live.peerCount; i++) {
        const struct Peer *peer = &sWorld.live.peers[i];
        unsigned j;
        bool8 rendered = FALSE;
        if (peer->id[0] == '@') continue;
        for (j = 0; j < WB_REMOTES; j++)
            if (Overworld() && Owned(j) && !strcmp(sWorld.remotes[j].id, peer->id)) rendered = TRUE;
        fprintf(file, "%s{\"trainer\":\"%s\",\"map\":[%u,%u],\"pos\":[%u,%u],\"ready\":%s,\"status\":\"%s\",\"rendered\":%s,\"nearby\":%s}",
            count++ ? "," : "", peer->id, peer->group, peer->num, peer->x, peer->y,
            peer->ready ? "true" : "false", peer->ready ? "available" : "busy",
            rendered ? "true" : "false",
            gSaveBlock1Ptr && peer->group == (unsigned)gSaveBlock1Ptr->location.mapGroup
             && peer->num == (unsigned)gSaveBlock1Ptr->location.mapNum ? "true" : "false");
    }
    fprintf(file, "],\"objects\":[");
    count = 0;
    for (i = 0; i < WB_REMOTES; i++) if (Overworld() && Owned(i) && sWorld.remotes[i].id[0] == '@') {
        const struct Remote *r = &sWorld.remotes[i];
        const struct ObjectEvent *o = &gObjectEvents[r->object];
        fprintf(file, "%s{\"id\":\"%s\",\"object_id\":%u,\"local_id\":%u,\"sprite_id\":%u,\"gfx\":%u,\"map\":[%u,%u],\"pos\":[%d,%d],\"visible\":%s}",
            count++ ? "," : "", r->id + 1, r->object, o->localId, o->spriteId, o->graphicsId, o->mapGroup, o->mapNum,
            o->currentCoords.x - MAP_OFFSET, o->currentCoords.y - MAP_OFFSET, gSprites[o->spriteId].invisible ? "false" : "true");
    }
    fprintf(file, "],\"object_count\":%u,\"dialogue_active\":%s,\"dialogue_object\":\"%s\",\"interaction_seq\":%u,\"dialogue_text\":\"",
        count, sWorld.dialogueActive ? "true" : "false", sWorld.dialogueObject, sWorld.interactionSeq);
    /* Validated literals cannot contain quotes or slashes. Escape their only
     * control character rather than placing raw newlines in telemetry JSON. */
    for (i = 0; sWorld.dialogueLiteral[i]; i++) {
        if (sWorld.dialogueLiteral[i] == '\n') fputs("\\n", file);
        else fputc(sWorld.dialogueLiteral[i], file);
    }
    fprintf(file, "\",\"dialogue_kind\":\"%s\",\"meeting\":", sWorld.dialogueMeeting ? "trainer" : "object");
    if (sWorld.live.meeting.seq) {
        const struct Meeting *m = &sWorld.live.meeting;
        fprintf(file, "{\"seq\":%u,\"player\":\"%s\",\"target\":\"%s\",\"signal\":\"explore\"}",
            m->seq, m->player, m->target);
    } else fputs("null", file);
    fprintf(file, ",\"tiles\":[");
    for (i = 0; i < sWorld.appliedCount; i++) {
        const struct Applied *a = &sWorld.applied[i];
        fprintf(file, "%s{\"map\":[%u,%u],\"pos\":[%u,%u],\"metatile\":%u,\"collision\":%u,\"original\":%u,\"raw\":%u}",
            i ? "," : "", a->tile.group, a->tile.num, a->tile.x, a->tile.y, a->tile.metatile, a->tile.collision,
            a->original, SameGrid() && GridCoords(a->tile.x, a->tile.y) ? Raw(a->tile.x, a->tile.y) : a->raw);
    }
    fprintf(file, "],\"restored_tiles\":[");
    for (i = 0; i < sWorld.restoredCount; i++) {
        const struct Applied *a = &sWorld.restored[i];
        fprintf(file, "%s{\"map\":[%u,%u],\"pos\":[%u,%u],\"original\":%u,\"raw\":%u}",
            i ? "," : "", a->tile.group, a->tile.num, a->tile.x, a->tile.y, a->original, a->raw);
    }
    fprintf(file, "],\"travel_available\":%s,\"friends\":[", sWorld.travelAvailable ? "true" : "false");
    {
        struct WorldBridgePeer friend;
        for (i = 0; WorldBridge_GetTravelPeer(i, &friend); i++)
            fprintf(file, "%s{\"trainer\":\"%s\",\"map\":[%u,%u],\"pos\":[%u,%u],\"ready\":%s}",
                i ? "," : "", friend.name, friend.group, friend.num, friend.x, friend.y, friend.ready ? "true" : "false");
    }
    fputs("],\"travel\":", file);
    WorldTravel_WriteJSON(file);
    fputc('}', file);
}

void WorldBridge_Poll(bool8 headless)
{
    if (!sWorld.enabled) return;
    if (!SocketOpen()) {
        if (sWorld.retry) sWorld.retry--;
        else Connect(headless);
    }
    if (SocketOpen() && !sWorld.connected) {
        /* Include connection setup and partial replies in one attempt budget.
         * Existing cleanup retires stale snapshots before the usual retry. */
        if (!sWorld.handshakePolls) { Disconnect(); return; }
        sWorld.handshakePolls--;
    }
    if (SocketOpen()) Receive(headless);
}

#if WORLD_SMOOTH_PRESENCE
// Called once per game frame, not once per reconciliation (which can run twice).
static void AdvanceRemoteMotion(void)
{
    unsigned i;
    for (i = 0; i < WB_REMOTES; i++)
    {
        struct Remote *r = &sWorld.remotes[i];
        struct Sprite *sprite;
        struct ObjectEvent *object;
        if (!Owned(i) || r->id[0] == '@' || !RemoteWalkAnimationSafe(gObjectEvents[r->object].graphicsId)) continue;
        sprite = &gSprites[r->sprite];
        object = &gObjectEvents[r->object];
        sprite->x2 = r->motionX;
        sprite->y2 = r->motionY;
        if (r->motionX || r->motionY)
        {
            if (RemoteWalkAnimationSafe(object->graphicsId))
            {
                StartSpriteAnimIfDifferent(sprite, GetMoveDirectionAnimNum(r->motionDirection));
                r->walking = TRUE;
            }
            if (r->motionX > 0) r->motionX -= 2;
            else if (r->motionX < 0) r->motionX += 2;
            if (r->motionY > 0) r->motionY -= 2;
            else if (r->motionY < 0) r->motionY += 2;
        }
        else if (r->walking)
        {
            ObjectEventTurn(object, object->facingDirection);
            r->walking = FALSE;
        }
    }
}
#endif

void WorldBridge_BeforeFrame(u32 frame, bool8 headless)
{
    (void)frame;
    if (!sWorld.enabled) return;
    WorldBridge_Poll(headless);
    SyncEngine();
#if WORLD_SMOOTH_PRESENCE
    AdvanceRemoteMotion();
#endif
}

void WorldBridge_AfterFrame(u32 frame)
{
    FILE *file;
    char path[1100];
    WorldMenu_Update();
    if (!sWorld.enabled) return;
#if GENERATED_MAP_READY
    CavePump();
#endif
    UpdateFieldPresence();
    if (sWorld.snapshotAge <= 180) sWorld.snapshotAge++;
    WorldTravel_Update();
    WorldRally_Update();
    SyncDialogue();
    SyncEngine();
    if (frame % 6 == 0) SendState();
    snprintf(path, sizeof(path), "%s.tmp", sWorld.telemetry);
    file = NativeFile_Open(path, "w");
    if (!file) return;
    WorldBridge_WriteJSON(file, frame);
    fputc('\n', file);
    if (fclose(file) == 0) {
        NativeFile_Replace(path, sWorld.telemetry);
    }
}

void WorldBridge_PrepareSave(void)
{
    unsigned i;
    if (!sWorld.enabled) return;
    RestoreTiles();
    sWorld.tilesLive = FALSE;
    /* Serialization can run during a warp, outside CB2_Overworld. Owned()
     * protects engine-reused slots without relying on the current callback. */
    for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
}

void WorldBridge_Close(void)
{
    unsigned i;
    if (!sWorld.enabled) return;
    WorldTravel_Close();
    RestoreTiles();
    if (Overworld()) for (i = 0; i < WB_REMOTES; i++) RemoveRemote(i);
    Disconnect();
#ifdef _WIN32
    if (sWorld.winsockStarted) {
        WSACleanup();
        sWorld.winsockStarted = FALSE;
    }
#endif
    sWorld.enabled = FALSE;
}
#endif /* PORTABLE */
