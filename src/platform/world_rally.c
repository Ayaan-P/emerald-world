#ifdef PORTABLE
#include "global.h"
#include "main.h"
#include "overworld.h"
#include "palette.h"
#include "script.h"
#include "fieldmap.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "event_data.h"
#include "battle_setup.h"
#include "pokemon.h"
#include "link.h"
#include "constants/flags.h"
#include "constants/opponents.h"
#include "constants/map_groups.h"
#include "platform/native_link.h"
#include "platform/world_activity.h"
#include "platform/world_bridge.h"
#include "platform/world_travel.h"
#include "platform/world_rally.h"
#include "platform/world_menu.h"
#include <string.h>
#include <stdio.h>
#ifndef _WIN32
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <errno.h>
#endif

/* A private spatial anchor, never a save snapshot. Committed party, bag, trades
 * and story remain precisely the current engine state on return/restart. */
struct RallyAnchor {
    u32 magic;
    char trainer[25];
    u8 trainerId[4];
    u8 group, num, elevation;
    s16 x, y;
};
static struct {
    bool8 autoJoin, loaded, ledgerOK, anchored, recover, offering, cancelOffer;
    unsigned pulse, consent, trip, transit, timer, returning;
    unsigned pending, pendingId, pendingArg, pendingDelay, pendingAge;
    s16 destX, destY;
    struct RallyAnchor anchor;
    const char *status;
#ifndef _WIN32
    int directory;
    char file[256];
#endif
} sRally = {
#ifndef _WIN32
    .directory = -1,
#endif
    .status = "ASK. Rally at Roxanne after clearing her Gym trainers."
};
static const s16 sSlots[WORLD_RALLY_ROSTER][2] = {{5,3}, {4,3}, {6,3}, {5,4}};

static bool8 FieldReady(void)
{
    return gSaveBlock1Ptr && gSaveBlock2Ptr && gMain.callback1 == CB1_Overworld
        && gMain.callback2 == CB2_Overworld && !gMain.inBattle && !gPaletteFade.active
        && !ScriptContext_IsEnabled() && !ArePlayerFieldControlsLocked()
        && !gPlayerAvatar.tileTransitionState && !gWirelessCommType
        && !NativeLink_IsActive() && !WorldActivity_OwnsFieldInput()
        && !WorldTravel_OwnsFieldInput() && !WorldTravel_NativeFlyRunning()
        && !WorldMenu_OwnsFieldInput();
}

static bool8 Eligible(void)
{
    unsigned i;
    if (!sRally.ledgerOK || !FieldReady() || FlagGet(FLAG_BADGE01_GET)
        || FlagGet(FLAG_DEFEATED_RUSTBORO_GYM) || HasTrainerBeenFought(TRAINER_ROXANNE_1)
        || VarGet(VAR_RUSTBORO_CITY_STATE) != 0 || !FlagGet(FLAG_VISITED_RUSTBORO_CITY)
        || !HasTrainerBeenFought(TRAINER_JOSH) || !HasTrainerBeenFought(TRAINER_TOMMY)
        || !HasTrainerBeenFought(TRAINER_MARC)) return FALSE;
    for (i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP)) return TRUE;
    return FALSE;
}

void WorldRally_Init(const char *configPath)
{
#ifndef _WIN32
    char parent[1100], *slash;
    struct stat st;
    size_t length;
    if (sRally.directory >= 0) close(sRally.directory);
    memset(&sRally, 0, sizeof(sRally));
    sRally.directory = -1;
    sRally.status = "ASK. Rally at Roxanne after clearing her Gym trainers.";
    if (!configPath || (length = strlen(configPath)) >= sizeof(parent)) return;
    memcpy(parent, configPath, length+1);
    slash = strrchr(parent, '/');
    if (!slash || !slash[1] || strlen(slash+1)+7 >= sizeof(sRally.file)) return;
    snprintf(sRally.file, sizeof(sRally.file), "%s.rally", slash+1);
    *slash = 0;
    sRally.directory = open(parent, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (sRally.directory < 0) return;
    if (fstat(sRally.directory, &st) || st.st_uid != getuid() || (st.st_mode & 077)) {
        close(sRally.directory);
        sRally.directory = -1;
        sRally.status = "Rally requires a private trainer directory.";
    }
#else
    (void)configPath;
    sRally.status = "Rally travel is not supported on this platform.";
#endif
}

static void LoadAnchor(void)
{
    sRally.loaded = TRUE;
#ifndef _WIN32
    {
        int fd;
        struct stat st;
        struct RallyAnchor anchor;
        if (sRally.directory < 0) return;
        fd = openat(sRally.directory, sRally.file, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) {
            sRally.ledgerOK = errno == ENOENT;
            return;
        }
        memset(&anchor, 0, sizeof(anchor));
        if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid()
            || st.st_nlink != 1 || (st.st_mode & 077) || st.st_size != (off_t)sizeof(anchor)
            || read(fd, &anchor, sizeof(anchor)) != (ssize_t)sizeof(anchor)
            || anchor.magic != 0x52414c31 || !memchr(anchor.trainer, 0, sizeof(anchor.trainer))
            || strcmp(anchor.trainer, WorldBridge_TrainerName())
            || memcmp(anchor.trainerId, gSaveBlock2Ptr->playerTrainerId, sizeof(anchor.trainerId))
            || anchor.x < 0 || anchor.y < 0 || anchor.x > 127 || anchor.y > 127
            || anchor.elevation != ELEVATION_DEFAULT) {
            close(fd);
            sRally.status = "Return record does not match this trainer save.";
            return;
        }
        close(fd);
        sRally.anchor = anchor;
        sRally.ledgerOK = sRally.anchored = sRally.recover = TRUE;
        sRally.status = "Recovering your pre-rally position when the field is free.";
    }
#endif
}

static bool8 ClearAnchor(void)
{
#ifndef _WIN32
    if (sRally.directory < 0 || (unlinkat(sRally.directory, sRally.file, 0) && errno != ENOENT)
        || fsync(sRally.directory)) return FALSE;
#endif
    sRally.anchored = sRally.recover = FALSE;
    sRally.transit = sRally.trip = sRally.returning = 0;
    return TRUE;
}

static bool8 CaptureAnchor(void)
{
#ifndef _WIN32
    int fd;
    bool8 written;
    struct RallyAnchor anchor;
    const struct ObjectEvent *player;
    if (!FieldReady() || !sRally.ledgerOK || sRally.anchored
        || sRally.directory < 0 || gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return FALSE;
    player = &gObjectEvents[gPlayerAvatar.objectEventId];
    if (!player->active || !player->isPlayer) return FALSE;
    memset(&anchor, 0, sizeof(anchor));
    anchor.magic = 0x52414c31;
    strcpy(anchor.trainer, WorldBridge_TrainerName());
    memcpy(anchor.trainerId, gSaveBlock2Ptr->playerTrainerId, sizeof(anchor.trainerId));
    anchor.group = gSaveBlock1Ptr->location.mapGroup;
    anchor.num = gSaveBlock1Ptr->location.mapNum;
    anchor.x = player->currentCoords.x - MAP_OFFSET;
    anchor.y = player->currentCoords.y - MAP_OFFSET;
    anchor.elevation = player->currentElevation;
    if (!WorldTravel_RallyTileSafe(anchor.group, anchor.num, anchor.x, anchor.y, anchor.elevation, TRUE)) return FALSE;
    fd = openat(sRally.directory, sRally.file, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (fd < 0) return FALSE;
    written = write(fd, &anchor, sizeof(anchor)) == (ssize_t)sizeof(anchor) && !fsync(fd);
    if (close(fd)) written = FALSE;
    if (fsync(sRally.directory)) written = FALSE;
    if (!written) {
        unlinkat(sRally.directory, sRally.file, 0);
        return FALSE;
    }
    sRally.anchor = anchor;
    sRally.anchored = TRUE;
    return TRUE;
#else
    return FALSE;
#endif
}

void WorldRally_SetAutoJoin(bool8 enabled) { sRally.autoJoin = !!enabled; }
bool8 WorldRally_GetAutoJoin(void) { return sRally.autoJoin; }
bool8 WorldRally_HasReturn(void) { return sRally.anchored; }
const char *WorldRally_Status(void) { return sRally.status; }
bool8 WorldRally_GetSnapshot(struct WorldRallySnapshot *out) { return WorldBridge_RallySnapshot(out); }

/* UI closes its field window before queueing. Wait for two ordinary STATE
 * intervals after a fresh local eligibility report; the relay must never admit
 * stale menu-time readiness or be told that a busy client is ready. */
static bool8 QueueChoice(unsigned action, unsigned id, unsigned arg)
{
    if (sRally.pending || !FieldReady()) return FALSE;
    sRally.pending = action+1;
    sRally.pendingId = id;
    sRally.pendingArg = arg;
    sRally.pendingDelay = sRally.pendingAge = 0;
    sRally.status = "Sending rally choice after local field readiness.";
    return TRUE;
}

bool8 WorldRally_Request(unsigned scene, unsigned scope)
{
    struct WorldRallySnapshot rally;
    if (!WorldBridge_RallySnapshot(&rally) || rally.id || sRally.offering) return FALSE;
    if (scene != WORLD_RALLY_ROXANNE || scope > 1 || !Eligible() || sRally.anchored
        || gSaveBlock1Ptr->location.mapGroup != MAP_GROUP(MAP_RUSTBORO_CITY_GYM)
        || gSaveBlock1Ptr->location.mapNum != MAP_NUM(MAP_RUSTBORO_CITY_GYM)) return FALSE;
    {
        const struct ObjectEvent *player;
        if (gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return FALSE;
        player = &gObjectEvents[gPlayerAvatar.objectEventId];
        if (!player->active || !player->isPlayer || player->currentCoords.x != 5+MAP_OFFSET
            || player->currentCoords.y != 3+MAP_OFFSET || player->currentElevation != ELEVATION_DEFAULT) return FALSE;
    }
    if (!QueueChoice(WORLD_RALLY_OFFER, 0, scope)) return FALSE;
    sRally.offering = TRUE;
    return TRUE;
}

bool8 WorldRally_Choose(unsigned action)
{
    struct WorldRallySnapshot rally;
    bool8 cancelledOffer = FALSE;
    if (action == WORLD_RALLY_CANCEL || action == WORLD_RALLY_LATER || action == WORLD_RALLY_BACK) {
        if (sRally.offering && action == WORLD_RALLY_CANCEL) {
            cancelledOffer = TRUE;
            if (sRally.pending == WORLD_RALLY_OFFER+1) sRally.offering = FALSE;
            else sRally.cancelOffer = TRUE;
        }
        sRally.pending = sRally.consent = 0;
        if (action != WORLD_RALLY_LATER) sRally.recover = sRally.anchored;
    }
    if (!WorldBridge_RallySnapshot(&rally) || !rally.id) {
        if (cancelledOffer) { sRally.status = "Rally cancelled."; return TRUE; }
        if (action == WORLD_RALLY_BACK && sRally.anchored) { sRally.recover = TRUE; return TRUE; }
        if (action == WORLD_RALLY_KEEP && sRally.anchored && FieldReady()) return ClearAnchor();
        return FALSE;
    }
    if (action == WORLD_RALLY_ACCEPT) {
        if (rally.phase != WORLD_RALLY_GATHER || !Eligible() || sRally.anchored) return FALSE;
        return QueueChoice(action, rally.id, 0);
    }
    if (action == WORLD_RALLY_GO) {
        if (rally.phase != WORLD_RALLY_GATHER || !Eligible() || strcmp(rally.owner, WorldBridge_TrainerName())) return FALSE;
        return QueueChoice(action, rally.id, 0);
    }
    if (action != WORLD_RALLY_LATER && action != WORLD_RALLY_CANCEL && action != WORLD_RALLY_GO
        && action != WORLD_RALLY_BACK && action != WORLD_RALLY_KEEP && action != WORLD_RALLY_FINISH) return FALSE;
    if (action == WORLD_RALLY_LATER || action == WORLD_RALLY_CANCEL || action == WORLD_RALLY_BACK) {
        sRally.pending = sRally.consent = 0;
        if (action != WORLD_RALLY_LATER) sRally.recover = sRally.anchored;
    }
    if (action == WORLD_RALLY_KEEP) {
        unsigned i;
        bool8 returning = FALSE;
        for (i = 0; i < rally.count; i++)
            if (!strcmp(rally.members[i].name, WorldBridge_TrainerName())
                && rally.members[i].state == WORLD_RALLY_RETURNING) returning = TRUE;
        if (!returning || !FieldReady() || sRally.transit) return FALSE;
    }
    if (!WorldBridge_RallySend(action, rally.id, 0)) return FALSE;
    if (action == WORLD_RALLY_BACK || action == WORLD_RALLY_CANCEL) sRally.recover = sRally.anchored;
    if (action == WORLD_RALLY_KEEP && sRally.anchored) return ClearAnchor();
    return TRUE;
}

void WorldRally_Disconnected(void)
{
    if (sRally.anchored) sRally.recover = TRUE;
    sRally.consent = sRally.pulse = sRally.pending = 0;
    sRally.offering = sRally.cancelOffer = FALSE;
}

static bool8 At(unsigned group, unsigned num, s16 x, s16 y, unsigned elevation)
{
    const struct ObjectEvent *player;
    if (!FieldReady() || gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return FALSE;
    player = &gObjectEvents[gPlayerAvatar.objectEventId];
    return player->active && player->isPlayer && gSaveBlock1Ptr->location.mapGroup == group
        && gSaveBlock1Ptr->location.mapNum == num && player->currentCoords.x == x + MAP_OFFSET
        && player->currentCoords.y == y + MAP_OFFSET && player->currentElevation == elevation;
}

void WorldRally_Update(void)
{
    struct WorldRallySnapshot rally;
    struct WorldRallyMember *member = NULL;
    struct WorldBridgePeer owner;
    unsigned i;
    bool8 online = WorldBridge_RallySnapshot(&rally);
    if (!sRally.loaded && FieldReady()) LoadAnchor();
    if (!sRally.loaded) return;
    if (online && rally.id && !strcmp(rally.owner, WorldBridge_TrainerName())) {
        sRally.offering = FALSE;
        if (sRally.cancelOffer && WorldBridge_RallySend(WORLD_RALLY_CANCEL, rally.id, 0)) {
            sRally.cancelOffer = FALSE;
            sRally.status = "Rally cancelled.";
        }
    }
    if (sRally.offering && !sRally.pending && online && !rally.id && ++sRally.pendingAge > 300) {
        sRally.offering = sRally.cancelOffer = FALSE;
        sRally.status = "Rally was unavailable. Check your position and try again.";
    }
    if (sRally.pending) {
        if (++sRally.pendingAge > 1800) {
            sRally.pending = 0;
            sRally.offering = FALSE;
            sRally.status = "Rally request timed out. No travel was started.";
        }
        else if (FieldReady()) {
            unsigned action = sRally.pending-1;
            if (!Eligible() || sRally.anchored) {
                sRally.pending = 0;
                sRally.offering = FALSE;
                sRally.status = "Rally no longer available from your local field state.";
            }
            else if (!sRally.pendingDelay) {
                if (WorldBridge_RallySend(WORLD_RALLY_REPORT, 0, 1 | (sRally.autoJoin ? 2 : 0)))
                    sRally.pendingDelay = 12;
            } else if (sRally.pendingDelay > 1) sRally.pendingDelay--;
            else if (WorldBridge_RallySend(action, sRally.pendingId, sRally.pendingArg)) {
                if (action == WORLD_RALLY_ACCEPT) sRally.consent = sRally.pendingId;
                sRally.pending = 0;
            }
        } else sRally.pendingDelay = 0;
    }
    if (++sRally.pulse >= 60) {
        if (WorldBridge_RallySend(WORLD_RALLY_REPORT, 0,
                (Eligible() && !sRally.anchored ? 1 : 0) | (sRally.autoJoin ? 2 : 0))) sRally.pulse = 0;
    }
    if (online) for (i = 0; i < rally.count; i++)
        if (!strcmp(rally.members[i].name, WorldBridge_TrainerName())) member = &rally.members[i];
    if (sRally.anchored && (!online || !member || rally.id != sRally.trip)) sRally.recover = TRUE;
    if (sRally.transit) {
        if (++sRally.timer > 1200) sRally.recover = TRUE;
        if (!FieldReady()) return; /* Never abort a battle, trade, script or warp. */
        if (sRally.transit == 2) {
            if (At(sRally.anchor.group, sRally.anchor.num, sRally.destX, sRally.destY, sRally.anchor.elevation)
                && WorldTravel_RallyTileSafe(sRally.anchor.group, sRally.anchor.num,
                    sRally.destX, sRally.destY, sRally.anchor.elevation, online)) {
                if (online && rally.id == sRally.trip) WorldBridge_RallySend(WORLD_RALLY_HOME, rally.id, 0);
                if (ClearAnchor()) sRally.status = "Returned. Your current party, items and progress are unchanged.";
                return;
            }
            sRally.transit = 0;
            sRally.recover = TRUE;
        } else {
            sRally.transit = 0;
            if (!At(MAP_GROUP(MAP_RUSTBORO_CITY_GYM), MAP_NUM(MAP_RUSTBORO_CITY_GYM),
                    sRally.destX, sRally.destY, ELEVATION_DEFAULT)
                || !WorldTravel_RallyTileSafe(MAP_GROUP(MAP_RUSTBORO_CITY_GYM), MAP_NUM(MAP_RUSTBORO_CITY_GYM),
                    sRally.destX, sRally.destY, ELEVATION_DEFAULT, online)) sRally.recover = TRUE;
            else sRally.status = "Arrived. Use the normal Gym script and two-player tag controls.";
        }
    }
    if (sRally.anchored && sRally.recover && FieldReady()) {
        /* Prefer the exact anchor. If occupied, use the nearest checked tile
         * within one step at the SAME elevation. No gate/warp/script tiles. */
        int radius, dx, dy;
        for (radius = 0; radius <= 1; radius++) for (dy = -radius; dy <= radius; dy++)
            for (dx = -radius; dx <= radius; dx++) {
                if (abs(dx)+abs(dy) != radius) continue;
                if (WorldTravel_RallyWarp(sRally.anchor.group, sRally.anchor.num,
                        sRally.anchor.x+dx, sRally.anchor.y+dy, sRally.anchor.elevation, online)) {
                    sRally.destX = sRally.anchor.x+dx; sRally.destY = sRally.anchor.y+dy;
                    sRally.transit = 2; sRally.timer = 0;
                    sRally.status = "Returning to your pre-rally map.";
                    return;
                }
            }
        sRally.status = "Return ground is occupied. Move freely, then retry Return or Stay.";
        return;
    }
    if (!online || !member) return;
    if (member->state == WORLD_RALLY_RETURNING) {
        if (!sRally.returning++) sRally.status = "Rally ended. Choose Return or Stay.";
        if (!sRally.anchored) WorldBridge_RallySend(WORLD_RALLY_HOME, rally.id, 0);
        else if (sRally.returning >= 7200) sRally.recover = TRUE;
        return;
    }
    sRally.returning = 0;
    if (rally.phase == WORLD_RALLY_GATHER && member->state == WORLD_RALLY_INVITED && sRally.autoJoin)
        WorldRally_Choose(WORLD_RALLY_ACCEPT);
    if (rally.phase == WORLD_RALLY_ACTIVE && !strcmp(rally.owner, WorldBridge_TrainerName())
        && FieldReady() && FlagGet(FLAG_BADGE01_GET)) WorldBridge_RallySend(WORLD_RALLY_FINISH, rally.id, 0);
    if (member->state != WORLD_RALLY_MOVING || !FieldReady()) return;
    if (sRally.anchored && sRally.trip == rally.id) {
        if (!sRally.recover) WorldBridge_RallySend(WORLD_RALLY_LAND, rally.id, 0);
        return;
    }
    if (sRally.consent != rally.id || !Eligible() || member->slot >= WORLD_RALLY_ROSTER) {
        WorldBridge_RallySend(WORLD_RALLY_FAIL, rally.id, 0);
        return;
    }
    for (i = 0; WorldBridge_GetTravelPeer(i, &owner); i++)
        if (!strcmp(owner.name, rally.owner)) break;
    if (!WorldBridge_GetTravelPeer(i, &owner) || !owner.ready
        || owner.group != MAP_GROUP(MAP_RUSTBORO_CITY_GYM) || owner.num != MAP_NUM(MAP_RUSTBORO_CITY_GYM)
        || abs((int)owner.x-5)+abs((int)owner.y-3) > 1) {
        WorldBridge_RallySend(WORLD_RALLY_FAIL, rally.id, 0);
        return;
    }
    sRally.destX = sSlots[member->slot][0]; sRally.destY = sSlots[member->slot][1];
    if (!CaptureAnchor()) { WorldBridge_RallySend(WORLD_RALLY_FAIL, rally.id, 0); return; }
    sRally.trip = rally.id;
    if (!WorldTravel_RallyWarp(MAP_GROUP(MAP_RUSTBORO_CITY_GYM), MAP_NUM(MAP_RUSTBORO_CITY_GYM),
            sRally.destX, sRally.destY, ELEVATION_DEFAULT, TRUE)) {
        ClearAnchor();
        WorldBridge_RallySend(WORLD_RALLY_FAIL, rally.id, 0);
        return;
    }
    sRally.transit = 1; sRally.timer = 0;
    sRally.status = "Travelling to Roxanne. Only the encounter owner earns boss credit.";
}
#endif
