#ifdef PORTABLE
#include <stdio.h>
#include "global.h"
#include "battle.h"
#include "sprite.h"
#include "global.fieldmap.h"
#include "fieldmap.h"
#include "main.h"
#include "m4a.h"
#include "overworld.h"
#include "palette.h"
#include "pokemon.h"
#include "script.h"
#include "constants/songs.h"
#include "platform/test_state.h"
#include "platform/world_bridge.h"
#include "platform/world_activity.h"
#include "platform/native_link.h"
#include "trade.h"

// The song the BGM player is playing, or -1
static int GetBgmSong(void)
{
    if (gMPlayInfo_BGM.songHeader == NULL || (gMPlayInfo_BGM.status & MUSICPLAYER_STATUS_PAUSE)
     || !(gMPlayInfo_BGM.status & MUSICPLAYER_STATUS_TRACK))
        return -1;
    // PH_NURSE_SOLO is the last song in the table
    for (int i = 0; i <= PH_NURSE_SOLO; i++)
    {
        if (gSongTable[i].header == gMPlayInfo_BGM.songHeader)
            return i;
    }
    return -1;
}

// Numeric own-party data only. GetMonData handles the engine's encrypted fields.
static void WriteOwnParty(FILE *file)
{
    fprintf(file, ", \"party\": [");
    if (gSaveBlock1Ptr != NULL && gSaveBlock2Ptr != NULL)
    {
        for (int i = 0; i < gPlayerPartyCount && i < PARTY_SIZE; i++)
        {
            struct Pokemon *mon = &gPlayerParty[i];
            fprintf(file, "%s{\"slot\": %d, \"species\": %u, \"level\": %u, \"hp\": %u, \"max_hp\": %u, \"status\": %u, \"moves\": [",
                    i ? ", " : "", i, (unsigned)GetMonData(mon, MON_DATA_SPECIES),
                    (unsigned)GetMonData(mon, MON_DATA_LEVEL), (unsigned)GetMonData(mon, MON_DATA_HP),
                    (unsigned)GetMonData(mon, MON_DATA_MAX_HP), (unsigned)GetMonData(mon, MON_DATA_STATUS));
            for (int move = 0; move < MAX_MON_MOVES; move++)
            {
                fprintf(file, "%s{\"id\": %u, \"pp\": %u}", move ? ", " : "",
                        (unsigned)GetMonData(mon, MON_DATA_MOVE1 + move),
                        (unsigned)GetMonData(mon, MON_DATA_PP1 + move));
            }
            fprintf(file, "]}");
        }
    }
    fprintf(file, "]");
}

// Current on-screen battlers only, never enemy party data or controller move buffers.
static void WritePublicBattle(FILE *file)
{
    bool32 first = TRUE;

    fprintf(file, ", \"battle_state\": ");
    if (!gMain.inBattle || gSaveBlock1Ptr == NULL || gSaveBlock2Ptr == NULL
     || gBattleStruct == NULL || gBattleResources == NULL
     || gBattlersCount == 0 || gBattlersCount > MAX_BATTLERS_COUNT)
    {
        fprintf(file, "null");
        return;
    }
    fprintf(file, "{\"battle_type_flags\": %u, \"battlers_count\": %u, \"turn\": %u, \"battlers\": [",
            (unsigned)gBattleTypeFlags, (unsigned)gBattlersCount,
            (unsigned)gBattleResults.battleTurnCounter);
    for (int i = 0; i < gBattlersCount; i++)
    {
        const struct BattlePokemon *mon = &gBattleMons[i];
        unsigned spriteId = gBattlerSpriteIds[i];

        // During intro/switching the battle mon may already contain unrevealed data.
        // Controllers set sprite data[0]/[2] to battler/species when loading a mon.
        if ((gAbsentBattlerFlags & (1u << i)) || mon->species == 0
         || gBattlerPositions[i] >= MAX_BATTLERS_COUNT || spriteId >= MAX_SPRITES
         || !gSprites[spriteId].inUse || gSprites[spriteId].invisible
         || gSprites[spriteId].data[0] != i || gSprites[spriteId].data[2] != mon->species)
            continue;
        // Loading sets species while x2 is still -DISPLAY_WIDTH. Ball release
        // also makes sprites visible before their reveal animation has ended.
        // Only admit settled opponent sprites after both native reveal phases.
        // Unknown offsets/animation state fail closed, without hiding own HUD.
        if ((gBattlerPositions[i] & BIT_SIDE) != B_SIDE_PLAYER
         && (gBattleSpritesDataPtr == NULL
          || gBattleSpritesDataPtr->animationData == NULL
          || gBattleSpritesDataPtr->healthBoxesData == NULL
          || gBattleSpritesDataPtr->animationData->introAnimActive
          || gBattleSpritesDataPtr->animationData->wildMonInvisible
          || gBattleSpritesDataPtr->healthBoxesData[i].ballAnimActive
          || gSprites[spriteId].callback != SpriteCallbackDummy
          || gSprites[spriteId].coordOffsetEnabled
          || gSprites[spriteId].x2 != 0 || gSprites[spriteId].y2 != 0
          || gSprites[spriteId].x < 0 || gSprites[spriteId].x >= DISPLAY_WIDTH
          || gSprites[spriteId].y < 0 || gSprites[spriteId].y >= DISPLAY_HEIGHT))
            continue;
        fprintf(file, "%s{\"battler\": %d, \"side\": %u, \"species\": %u, \"level\": %u",
                first ? "" : ", ", i, (unsigned)(gBattlerPositions[i] & BIT_SIDE),
                (unsigned)mon->species, (unsigned)mon->level);
        // Opponent HP numbers are never public. Raw status also contains hidden
        // sleep/toxic counters, so do not expose that internal word for opponents.
        if ((gBattlerPositions[i] & BIT_SIDE) == B_SIDE_PLAYER)
            fprintf(file, ", \"hp\": %u, \"max_hp\": %u, \"status\": %u",
                    (unsigned)mon->hp, (unsigned)mon->maxHP, (unsigned)mon->status1);
        fprintf(file, "}");
        first = FALSE;
    }
    fprintf(file, "]}");
}

// What the headless tests' driver needs to know to play: where the player is,
// whether they can move, and what's going on, as one line of JSON
void WriteTestState(FILE *file, u32 frame)
{
    const struct ObjectEvent *player = &gObjectEvents[gPlayerAvatar.objectEventId];
    bool32 first = TRUE;
    // There's no save block until a game is started or continued
    s8 mapGroup = gSaveBlock1Ptr != NULL ? gSaveBlock1Ptr->location.mapGroup : -1;
    s8 mapNum = gSaveBlock1Ptr != NULL ? gSaveBlock1Ptr->location.mapNum : -1;

    fprintf(file, "{\"frame\": %u, \"map\": [%d, %d], \"pos\": [%d, %d], \"facing\": %d, \"moving\": %d, "
                  "\"overworld\": %d, \"locked\": %d, \"script\": %d, \"battle\": %d, \"fade\": %d, \"bgm\": %d, \"objects\": [",
            frame, mapGroup, mapNum,
            player->currentCoords.x - MAP_OFFSET, player->currentCoords.y - MAP_OFFSET, player->facingDirection,
            gPlayerAvatar.tileTransitionState, gMain.callback2 == CB2_Overworld, ArePlayerFieldControlsLocked(),
            ScriptContext_IsEnabled(), gMain.inBattle, gPaletteFade.active, GetBgmSong());

    // Where the other people and things are, since they block the way
    for (int i = 0; i < OBJECT_EVENTS_COUNT; i++)
    {
        const struct ObjectEvent *object = &gObjectEvents[i];

        if (!object->active || object->isPlayer || object->invisible)
            continue;
        fprintf(file, "%s[%d, %d]", first ? "" : ", ", object->currentCoords.x - MAP_OFFSET,
                object->currentCoords.y - MAP_OFFSET);
        first = FALSE;
    }
    fprintf(file, "]");
    WriteOwnParty(file);
    WritePublicBattle(file);
    // Phase and status are fixed local literals, never remote names or payloads.
    fprintf(file, ", \"activity\": {\"phase\": \"%s\", \"mode\": %u, \"status\": \"%s\", \"link_connected\": %s, \"generation\": %u, \"trade_phase\": \"%s\"}",
            WorldActivity_Phase(), WorldActivity_Mode(), WorldActivity_Status(),
            NativeLink_IsConnected() ? "true" : "false", (unsigned)NativeLink_Generation(), TradeMenu_Phase());
    if (WorldBridge_Enabled())
    {
        fprintf(file, ", \"world\": ");
        WorldBridge_WriteJSON(file, frame);
    }
    fprintf(file, "}\n");
    fflush(file);
}
#endif // PORTABLE
