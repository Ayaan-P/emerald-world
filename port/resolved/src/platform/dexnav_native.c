/* RC7's world menu and encounter ownership bound to the full Expansion
 * DexNav implementation. Species, abilities, moves, progress and HUD resources
 * remain owned by Expansion, not a second vanilla ABI or a second sidecar. */
#ifdef PORTABLE
#include "global.h"
#include "battle.h"
#include "battle_pike.h"
#include "battle_pyramid.h"
#include "dexnav.h"
#include "event_data.h"
#include "link.h"
#include "main.h"
#include "overworld.h"
#include "safari_zone.h"
#include "platform/dexnav_native.h"
#include "platform/generated_map.h"
#include "platform/native_link.h"
#include "constants/region_map_sections.h"

bool8 DexNavNative_Available(void)
{
    u32 i;
    if (!DEXNAV_ENABLED || !FlagGet(FLAG_SYS_POKEDEX_GET)
        || GetSafariZoneFlag() || InBattlePike()
        || CurrentBattlePyramidLocation() != PYRAMID_LOCATION_NONE
        || gMapHeader.regionMapSectionId == MAPSEC_BATTLE_FRONTIER
        || IsOverworldLinkActive() || NativeLink_IsActive() || gMain.inBattle
        || GeneratedMap_Wildlife() != NULL)
        return FALSE;
    for (i = 0; i < PARTY_SIZE; ++i)
        if (GetMonData(&gPlayerParty[i], MON_DATA_SPECIES)
            && !GetMonData(&gPlayerParty[i], MON_DATA_IS_EGG)
            && GetMonData(&gPlayerParty[i], MON_DATA_HP))
            return TRUE;
    return FALSE;
}

bool8 DexNav_RequestOpen(void)
{
    return DexNav_OpenFromField();
}

void DexNavNative_AbandonBattle(void)
{
    ResetDexNavSearch();
    gDexNavSpecies = SPECIES_NONE;
}

void DexNavNative_PrepareNativeActivity(bool8 preserveEncounter)
{
    // The initiating client's actual DexNav encounter can enter co-op. The
    // joining client must not acquire the initiator's private chain/progress.
    bool8 ownsEncounter = preserveEncounter && gDexNavSpecies != SPECIES_NONE
        && gDexNavSpecies == GetMonData(&gEnemyParty[0], MON_DATA_SPECIES);
    if (ownsEncounter)
        EndDexNavSearch();
    else
        DexNavNative_AbandonBattle();
}
#endif
