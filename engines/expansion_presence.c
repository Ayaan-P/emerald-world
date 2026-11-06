/* Read-only adapter compiled against the donor's public inspection interface.
 * No vanilla engine headers, Pokemon layouts or save bytes cross this seam.
 * --wrap affects BIOS calls to frame_run, preserving the donor's frame hook. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "global.h"
#include "global.fieldmap.h"
#include "battle.h"
#include "pokemon.h"
#include "constants/event_objects.h"
#include "platform/frame.h"
#include "platform/inspect.h"

int LinkTransport_Init(const char *configPath);
void LinkTransport_Pump(void);
int LinkTransport_Ready(void);
void NativeLink_AfterFrame(void);
int NativeLink_BeforeFrame(const u16 send[8]);
extern u16 gSendCmd[8];
void ExpansionPeers_Update(int overworld);
void ExpansionActivity_Update(void);
void ExpansionCave_Update(void);
void ExpansionDexNav_Update(void);
int ExpansionActivity_PresenceReady(void);
int ExpansionTrade_PairValid(const void *data, size_t size);
unsigned ExpansionPeers_Count(void);
bool ExpansionControl_BeforeFrame(void);
void ExpansionControl_AfterFrame(void);
void ExpansionControl_WriteObservation(FILE *, uint32_t);
enum frame_result __real_frame_run(void);
enum frame_result __wrap_frame_run(void)
{
    static int link_state;
    if (!ExpansionControl_BeforeFrame()) {
        fputs("Expansion player control could not initialize.\n", stderr);
        exit(EXIT_FAILURE);
    }
    const char *config = getenv("EW_EXPANSION_LINK_CONFIG");
    if (config && link_state == 0)
        link_state = LinkTransport_Init(config) ? 1 : -1;
    if (link_state == 1) {
        NativeLink_AfterFrame();
        LinkTransport_Pump();
        (void)NativeLink_BeforeFrame(gSendCmd);
        ExpansionActivity_Update();
    }
    ExpansionCave_Update();
    ExpansionDexNav_Update();
    enum frame_result result = __real_frame_run();
    ExpansionControl_AfterFrame();
    const char *path = getenv("EW_EXPANSION_PRESENCE");
    if (path == NULL || frame_count() % 6 != 0)
        return result;
    char map[256], pos[256], callback[256], battle[256];
    inspect_get("map", map, sizeof map);
    inspect_get("pos", pos, sizeof pos);
    inspect_get("callback2", callback, sizeof callback);
    inspect_get("in_battle", battle, sizeof battle);
    unsigned group = 0, num = 0, x = 0, y = 0;
    int field = sscanf(map, "%u.%u", &group, &num) == 2
             && sscanf(pos, "%u,%u", &x, &y) == 2
             && strcmp(callback, "CB2_Overworld") == 0
             && strcmp(battle, "0") == 0;
    unsigned facing = 1, gfx = OBJ_EVENT_GFX_BOY_1;
    if (field && gPlayerAvatar.objectEventId < OBJECT_EVENTS_COUNT) {
        const struct ObjectEvent *player = &gObjectEvents[gPlayerAvatar.objectEventId];
        if (player->active && player->isPlayer && player->facingDirection >= 1 && player->facingDirection <= 4)
            facing = player->facingDirection;
        if (gPlayerAvatar.gender == 1) gfx = OBJ_EVENT_GFX_GIRL_1;
    }
    if (getenv("EW_EXPERIMENTAL_EXPANSION_PEERS") != NULL)
        ExpansionPeers_Update(field);
    int trade_valid = -1;
    if (getenv("EW_EXPANSION_TRADE_AUDIT") && gPartiesCount[B_TRAINER_PLAYER] >= 2)
        trade_valid = ExpansionTrade_PairValid(&gParties[B_TRAINER_PLAYER][0], 2 * sizeof(struct Pokemon));
    char temporary[4096];
    if (snprintf(temporary, sizeof temporary, "%s.tmp", path) >= (int)sizeof temporary)
        return result;
    FILE *out = fopen(temporary, "w");
    if (out != NULL) {
        int written = fprintf(out, "{\"schema\":1,\"engine\":\"expansion-native\",\"frame\":%u,"
                          "\"field\":%s,\"group\":%u,\"num\":%u,\"x\":%u,\"y\":%u,\"peers\":%u,\"facing\":%u,\"gfx\":%u,\"link_ready\":%s,\"ready\":%s,\"trade_pair_valid\":%s",
                          frame_count(), field ? "true" : "false", group, num, x, y, ExpansionPeers_Count(), facing, gfx, link_state == 1 && LinkTransport_Ready() ? "true" : "false",
                          field && ExpansionActivity_PresenceReady() ? "true" : "false",
                          trade_valid < 0 ? "null" : trade_valid ? "true" : "false");
        if (getenv("EW_EXPANSION_BATTLE_AUDIT")) {
            if (!strcmp(battle, "1")) fprintf(out, ",\"battle_turn\":%u", (unsigned)gBattleResults.battleTurnCounter);
            else fputs(",\"battle_turn\":null", out);
        }
        if (getenv("EW_EXPANSION_CONTROL_AUDIT")) {
            fputs(",\"control_audit\":", out);
            ExpansionControl_WriteObservation(out, frame_count());
        }
        fputs("}\n", out);
        if (ferror(out)) written = -1;
        int closed = fclose(out);
        if (written > 0 && closed == 0)
            (void)rename(temporary, path);
    }
    return result;
}

