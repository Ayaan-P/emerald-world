/* Experimental Expansion-native projection of authenticated world presence.
 * The host side validates and atomically publishes peers.txt. This component
 * reads it as untrusted data and never touches a trainer's save or party. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>
#include "global.h"
#include "global.fieldmap.h"
#include "fieldmap.h"
#include "field_player_avatar.h"
#include "event_object_movement.h"
#include "sprite.h"
#include "script.h"
#include "task.h"
#include "start_menu.h"
#include "constants/event_objects.h"

#define MAX_PEERS 8
#define LOCAL_BASE 224
#define PEER_MARKER 0x5742
struct Peer { char id[25]; unsigned group, num, x, y, facing, gfx; };
struct Remote { char id[25]; u8 object, sprite, group, num; };
static struct Remote remotes[MAX_PEERS];

static int owned(unsigned i)
{
    struct Remote *r = &remotes[i];
    struct ObjectEvent *o;
    if (!r->id[0] || r->object >= OBJECT_EVENTS_COUNT || r->sprite >= MAX_SPRITES) return 0;
    o = &gObjectEvents[r->object];
    return o->active && !o->isPlayer && (unsigned)o->localId == LOCAL_BASE + i
        && o->mapGroup == r->group && o->mapNum == r->num && o->spriteId == r->sprite
        && gSprites[r->sprite].inUse && gSprites[r->sprite].data[0] == r->object
        && gSprites[r->sprite].data[7] == PEER_MARKER;
}
static void remove_remote(unsigned i)
{
    if (owned(i)) RemoveObjectEvent(&gObjectEvents[remotes[i].object]);
    memset(&remotes[i], 0, sizeof remotes[i]);
}
static int peer_id(const char *s)
{
    size_t n = strlen(s);
    if (!n || n > 24) return 0;
    for (; *s; s++)
        if (!((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z')
              || (*s >= '0' && *s <= '9') || *s == '_' || *s == '-')) return 0;
    return 1;
}
static unsigned read_peers(struct Peer *out)
{
    const char *path = getenv("EW_EXPANSION_PEERS");
    struct stat st;
    char line[128], extra;
    unsigned n = 0, j;
    FILE *f;
    if (!path || stat(path, &st) || !S_ISREG(st.st_mode) || st.st_size > 2048
        || st.st_mtime > time(NULL) + 1 || time(NULL) - st.st_mtime > 5) return 0;
    f = fopen(path, "r");
    if (!f) return 0;
    if (!fgets(line, sizeof line, f) || strcmp(line, "EWPEERS 1\n")) goto invalid;
    while (fgets(line, sizeof line, f)) {
        struct Peer p;
        if (n == MAX_PEERS || !strchr(line, '\n')
            || sscanf(line, "%24s %u %u %u %u %u %u %c", p.id, &p.group, &p.num,
                      &p.x, &p.y, &p.facing, &p.gfx, &extra) != 7 || !peer_id(p.id)
            || p.group > 255 || p.num > 255 || p.x > 32767 || p.y > 32767
            || p.facing < 1 || p.facing > 4 || p.gfx > 255) goto invalid;
        for (j = 0; j < n; j++) if (!strcmp(out[j].id, p.id)) goto invalid;
        out[n++] = p;
    }
    if (ferror(f)) goto invalid;
    fclose(f);
    return n;
invalid:
    fclose(f);
    return 0;
}
static int blocked_position(unsigned x, unsigned y)
{
    unsigned i, j;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++) {
        const struct ObjectEvent *o = &gObjectEvents[i];
        int ours = 0;
        for (j = 0; j < MAX_PEERS; j++) if (owned(j) && remotes[j].object == i) ours = 1;
        if (!ours && o->active && !o->isPlayer && o->currentCoords.x == (int)x + MAP_OFFSET
            && o->currentCoords.y == (int)y + MAP_OFFSET) return 1;
    }
    return 0;
}
static int local_id_free(unsigned slot)
{
    unsigned i;
    for (i = 0; i < OBJECT_EVENTS_COUNT; i++)
        if (gObjectEvents[i].active && (unsigned)gObjectEvents[i].localId == LOCAL_BASE + slot) return 0;
    if (gMapHeader.events)
        for (i = 0; i < (unsigned)gMapHeader.events->objectEventCount; i++)
            if ((unsigned)gSaveBlock1Ptr->objectEventTemplates[i].localId == LOCAL_BASE + slot) return 0;
    return 1;
}
void ExpansionPeers_Update(int overworld)
{
    struct Peer peers[MAX_PEERS];
    unsigned n, i, j, group, num;
    if (!overworld || !gMapHeader.mapLayout || ScriptContext_IsEnabled()
        || FuncIsActiveTask(Task_ShowStartMenu)) {
        for (i = 0; i < MAX_PEERS; i++) remove_remote(i);
        return;
    }
    group = gSaveBlock1Ptr->location.mapGroup;
    num = gSaveBlock1Ptr->location.mapNum;
    n = read_peers(peers);
    for (i = 0; i < MAX_PEERS; i++) {
        for (j = 0; j < n; j++)
            if (!strcmp(remotes[i].id, peers[j].id) && peers[j].group == group && peers[j].num == num) break;
        if (j == n || !owned(i)) remove_remote(i);
    }
    for (j = 0; j < n; j++) {
        struct Peer *p = &peers[j];
        struct ObjectEvent *o;
        if (p->group != group || p->num != num || p->x >= (unsigned)gMapHeader.mapLayout->width
            || p->y >= (unsigned)gMapHeader.mapLayout->height || p->x > 32760 || p->y > 32760) continue;
        if (blocked_position(p->x, p->y)) {
            for (i = 0; i < MAX_PEERS; i++) if (!strcmp(remotes[i].id, p->id)) remove_remote(i);
            continue;
        }
        for (i = 0; i < MAX_PEERS; i++) if (!strcmp(remotes[i].id, p->id)) break;
        if (i < MAX_PEERS && owned(i) && gObjectEvents[remotes[i].object].graphicsId !=
            (p->gfx == OBJ_EVENT_GFX_GIRL_1 ? OBJ_EVENT_GFX_GIRL_1 : OBJ_EVENT_GFX_BOY_1))
            remove_remote(i);
        if (i == MAX_PEERS || !remotes[i].id[0]) {
            u8 id;
            for (i = 0; i < MAX_PEERS; i++) if (!remotes[i].id[0] && local_id_free(i)) break;
            if (i == MAX_PEERS) continue;
            id = SpawnSpecialObjectEventParameterized(p->gfx == OBJ_EVENT_GFX_GIRL_1 ? OBJ_EVENT_GFX_GIRL_1 : OBJ_EVENT_GFX_BOY_1, MOVEMENT_TYPE_NONE,
                LOCAL_BASE + i, p->x + MAP_OFFSET, p->y + MAP_OFFSET,
                MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET));
            if (id >= OBJECT_EVENTS_COUNT || gObjectEvents[id].spriteId >= MAX_SPRITES) continue;
            strcpy(remotes[i].id, p->id);
            remotes[i].object = id; remotes[i].sprite = gObjectEvents[id].spriteId;
            remotes[i].group = group; remotes[i].num = num;
            gSprites[remotes[i].sprite].data[7] = PEER_MARKER;
        }
        if (!owned(i)) continue;
        o = &gObjectEvents[remotes[i].object];
        if (o->currentCoords.x != (int)p->x + MAP_OFFSET || o->currentCoords.y != (int)p->y + MAP_OFFSET)
            MoveObjectEventToMapCoords(o, p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        o->initialCoords = o->currentCoords;
        o->currentElevation = o->previousElevation = MapGridGetElevationAt(p->x + MAP_OFFSET, p->y + MAP_OFFSET);
        if ((unsigned)o->facingDirection != p->facing) ObjectEventTurn(o, p->facing);
    }
}

unsigned ExpansionPeers_Count(void)
{
    unsigned i, count = 0;
    for (i = 0; i < MAX_PEERS; i++) if (owned(i)) count++;
    return count;
}

/* Do not persist projected peers when the game snapshots overworld objects.
 * Both entry points are wrapped: the full-save helper calls SaveObjectEvents
 * from the same translation unit, where a direct reference may bypass --wrap.
 * Other game code calls SaveObjectEvents directly for map transitions. */
void __real_SaveObjectEvents(void);
void __real_CopyPartyAndObjectsToSave(void);
static void clear_saved_peers(void)
{
    unsigned i;
    for (i = 0; i < MAX_PEERS; i++)
        if (owned(i)) gSaveBlock1Ptr->objectEvents[remotes[i].object].active = 0;
}
void __wrap_SaveObjectEvents(void)
{
    __real_SaveObjectEvents();
    clear_saved_peers();
}
void __wrap_CopyPartyAndObjectsToSave(void)
{
    __real_CopyPartyAndObjectsToSave();
    clear_saved_peers();
}

/* An injected peer has no map template or event script. Hide it from the
 * game's object-interaction lookup until real multiplayer interaction is
 * ported, while retaining ordinary overworld collision behavior. */
u8 __real_GetObjectEventIdByPosition(u16 x, u16 y, u8 elevation);
u8 __wrap_GetObjectEventIdByPosition(u16 x, u16 y, u8 elevation)
{
    u8 id = __real_GetObjectEventIdByPosition(x, y, elevation);
    unsigned i;
    for (i = 0; i < MAX_PEERS; i++)
        if (owned(i) && remotes[i].object == id) return OBJECT_EVENTS_COUNT;
    return id;
}

/* Borrowed peer name; the caller copies it before the next projection update. */
const char *ExpansionPeers_Facing(void)
{
    unsigned i;
    s16 x, y;
    if (gPlayerAvatar.objectEventId >= OBJECT_EVENTS_COUNT) return NULL;
    GetXYCoordsOneStepInFrontOfPlayer(&x, &y);
    for (i = 0; i < MAX_PEERS; i++)
        if (owned(i) && gObjectEvents[remotes[i].object].currentCoords.x == x
            && gObjectEvents[remotes[i].object].currentCoords.y == y)
            return remotes[i].id;
    return NULL;
}
