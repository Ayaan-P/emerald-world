"""Execute WriteTestState's actual C serializer with bounded engine fixtures.

Only includes are replaced: the complete PORTABLE translation unit is compiled.
No save, graphical client, private trainer party, or simulated battle is needed.
"""
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/platform/test_state.c"

STUBS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#define PORTABLE 1
#define TRUE 1
#define FALSE 0
#define PARTY_SIZE 6
#define MAX_MON_MOVES 4
#define MAX_BATTLERS_COUNT 4
#define MAX_SPRITES 64
#define DISPLAY_WIDTH 240
#define DISPLAY_HEIGHT 160
#define BIT_SIDE 1
#define B_SIDE_PLAYER 0
#define OBJECT_EVENTS_COUNT 16
#define MAP_OFFSET 7
#define MUSICPLAYER_STATUS_PAUSE 1
#define MUSICPLAYER_STATUS_TRACK 2
#define PH_NURSE_SOLO 0
#define MON_DATA_SPECIES 1
#define MON_DATA_LEVEL 2
#define MON_DATA_HP 3
#define MON_DATA_MAX_HP 4
#define MON_DATA_STATUS 5
#define MON_DATA_MOVE1 6
#define MON_DATA_PP1 10
#define MON_DATA_IS_EGG 14
typedef uint8_t u8;
typedef int8_t s8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int bool32;
struct Pokemon { u32 data[15]; };
struct BattlePokemon {
    u16 species, hp, maxHP; u8 level; u32 status1;
    u16 moves[4]; u8 pp[4];
};
struct BattleStruct { int unused; };
struct BattleResources { int unused; };
struct Sprite {
    int inUse, invisible, coordOffsetEnabled;
    int16_t x, y, x2, y2, data[8];
    void (*callback)(struct Sprite *);
};
static void SpriteCallbackDummy(struct Sprite *sprite) { (void)sprite; }
static void SpriteRevealing(struct Sprite *sprite) { (void)sprite; }
struct BattleAnimationInfo { int introAnimActive, wildMonInvisible; };
struct BattleHealthboxInfo { int ballAnimActive; };
struct BattleSpriteData {
    struct BattleAnimationInfo *animationData;
    struct BattleHealthboxInfo *healthBoxesData;
};
static struct BattleAnimationInfo animationData;
static struct BattleHealthboxInfo healthBoxesData[MAX_BATTLERS_COUNT];
static struct BattleSpriteData battleSpritesData, *gBattleSpritesDataPtr;
struct ObjectEvent { int active, isPlayer, invisible, facingDirection;
    struct { int x, y; } currentCoords; };
static struct ObjectEvent gObjectEvents[OBJECT_EVENTS_COUNT];
static struct { int objectEventId, tileTransitionState; } gPlayerAvatar;
struct SaveBlock { struct { s8 mapGroup, mapNum; } location; };
static struct SaveBlock save1, save2, *gSaveBlock1Ptr, *gSaveBlock2Ptr;
static void CB2_Overworld(void) {}
static struct { void (*callback2)(void); int inBattle; } gMain;
static struct { int active; } gPaletteFade;
static struct { void *songHeader; int status; } gMPlayInfo_BGM;
static struct { void *header; } gSongTable[1];
static struct Pokemon gPlayerParty[PARTY_SIZE];
static u8 gPlayerPartyCount;
static struct BattlePokemon gBattleMons[MAX_BATTLERS_COUNT];
static struct BattleStruct battleStruct, *gBattleStruct;
static struct BattleResources battleResources, *gBattleResources;
static struct Sprite gSprites[MAX_SPRITES + 1];
static u8 gBattlersCount, gBattlerPositions[4], gBattlerSpriteIds[4];
static u8 gAbsentBattlerFlags;
static u32 gBattleTypeFlags;
static struct { u8 battleTurnCounter; } gBattleResults;
static int ArePlayerFieldControlsLocked(void) { return 0; }
static int ScriptContext_IsEnabled(void) { return 0; }
static __attribute__((unused)) const char *WorldActivity_Status(void) { return "peer menu"; }
static __attribute__((unused)) const char *WorldActivity_Phase(void) { return "menu"; }
static __attribute__((unused)) unsigned WorldActivity_Mode(void) { return 0; }
static __attribute__((unused)) int NativeLink_IsConnected(void) { return 1; }
static __attribute__((unused)) unsigned NativeLink_Generation(void) { return 17; }
static const char *tradePhase = "inactive";
static const char *TradeMenu_Phase(void) { return tradePhase; }
static int WorldBridge_Enabled(void) { return 0; }
static void WorldBridge_WriteJSON(FILE *file, u32 frame) {
    (void)file; (void)frame; abort();
}
static u32 __attribute__((unused)) GetMonData(struct Pokemon *mon, int field) {
    if (!gSaveBlock1Ptr || !gSaveBlock2Ptr) abort();
    if (mon < gPlayerParty || mon >= gPlayerParty + PARTY_SIZE) abort();
    if (field < MON_DATA_SPECIES || field > MON_DATA_IS_EGG) abort();
    return mon->data[field];
}
'''

MAIN = r'''
int main(int argc, char **argv) {
    int mode = argc > 1 ? atoi(argv[1]) : 0;
    gSaveBlock1Ptr = &save1; gSaveBlock2Ptr = &save2;
    gMain.callback2 = CB2_Overworld;
    gPlayerPartyCount = 2;
    for (int i = 0; i < PARTY_SIZE; i++) {
        gPlayerParty[i].data[MON_DATA_SPECIES] = 252 + i;
        gPlayerParty[i].data[MON_DATA_LEVEL] = 5 + i;
        gPlayerParty[i].data[MON_DATA_HP] = i ? 0 : 17;
        gPlayerParty[i].data[MON_DATA_MAX_HP] = 20 + i;
        gPlayerParty[i].data[MON_DATA_STATUS] = i ? 0x80 : 0;
        for (int j = 0; j < MAX_MON_MOVES; j++) {
            gPlayerParty[i].data[MON_DATA_MOVE1 + j] = 33 + j;
            gPlayerParty[i].data[MON_DATA_PP1 + j] = 35 - j;
        }
    }
    if (mode == 1) gPlayerPartyCount = 255;
    if (mode == 2) gSaveBlock1Ptr = NULL;
    if (mode == 3) gSaveBlock2Ptr = NULL;
    if (mode >= 4) {
        gMain.inBattle = 1; gBattleStruct = &battleStruct;
        gBattleResources = &battleResources;
        gBattleSpritesDataPtr = &battleSpritesData;
        battleSpritesData.animationData = &animationData;
        battleSpritesData.healthBoxesData = healthBoxesData;
        gBattleTypeFlags = 0x80000001u; gBattlersCount = 4;
        gBattleResults.battleTurnCounter = 9;
        for (int i = 0; i < 4; i++) {
            gBattlerPositions[i] = i; gBattlerSpriteIds[i] = i;
            gSprites[i].inUse = 1;
            gSprites[i].x = 120; gSprites[i].y = 60;
            gSprites[i].callback = SpriteCallbackDummy;
            gSprites[i].data[0] = i; gSprites[i].data[2] = 100 + i;
            gBattleMons[i].species = 100 + i;
            gBattleMons[i].level = 50; gBattleMons[i].hp = 123;
            gBattleMons[i].maxHP = 150; gBattleMons[i].status1 = 8;
            gBattleMons[i].moves[0] = 65530;
        }
    }
    if (mode == 5) gMain.inBattle = 0;
    if (mode == 6) gBattleStruct = NULL;
    if (mode == 7) gBattleResources = NULL;
    if (mode == 8) gBattlersCount = 255;
    if (mode == 9) gBattlersCount = 0;
    if (mode == 10) {
        gSprites[1].invisible = 1; gBattlerSpriteIds[2] = MAX_SPRITES;
        gAbsentBattlerFlags = 1 << 3;
    }
    if (mode == 11) { gSaveBlock1Ptr = NULL; gSaveBlock2Ptr = NULL; }
    if (mode == 12) {
        gSprites[0].inUse = 0;
        gSprites[1].data[2] = 0; /* Trainer sprite, not a revealed Pokemon. */
        gBattleMons[2].species = 0;
        gBattlerPositions[3] = 255;
    }
    if (mode == 13) {
        gPlayerPartyCount = PARTY_SIZE;
        for (int i = 0; i < PARTY_SIZE; i++)
            for (int j = 1; j < 15; j++)
                gPlayerParty[i].data[j] = UINT32_MAX;
    }
    if (mode == 14) gPlayerPartyCount = 0;
    if (mode == 15) gBattlersCount = 2;
    /* Native load path populates species before sliding in from x2=-240. */
    if (mode == 16) gSprites[1].x2 = -DISPLAY_WIDTH;
    if (mode == 17) animationData.introAnimActive = 1;
    if (mode == 18) healthBoxesData[1].ballAnimActive = 1;
    if (mode == 19) gSprites[1].callback = SpriteRevealing;
    if (mode == 20) gBattleSpritesDataPtr = NULL;
    if (mode == 21) battleSpritesData.animationData = NULL;
    if (mode == 22) battleSpritesData.healthBoxesData = NULL;
    if (mode == 23) gSprites[1].x = DISPLAY_WIDTH;
    if (mode == 24) gSprites[1].x = -1;
    if (mode == 25) gSprites[1].y = DISPLAY_HEIGHT;
    if (mode == 26) gSprites[1].y = -1;
    if (mode == 27) gSprites[1].y2 = -DISPLAY_HEIGHT;
    if (mode == 28) gSprites[1].coordOffsetEnabled = 1;
    if (mode == 29) animationData.wildMonInvisible = 1;
    if (mode == 30) gSprites[1].x2 = -1; /* Partial send-out, not settled. */
    if (mode == 31) {
        /* Side is positional, not the battler index's parity. */
        gBattlerPositions[0] = 1; gBattlerPositions[1] = 0;
    }
    if (mode == 32) {
        gBattleMons[1].hp = 1; gBattleMons[1].maxHP = 65535;
        gBattleMons[1].status1 = UINT32_MAX;
    }
    if (mode >= 33 && mode <= 37) {
        const char *phases[] = {"choosing", "selected", "confirm", "cancel_confirm", "busy"};
        tradePhase = phases[mode - 33];
    }
    WriteTestState(stdout, 42);
    return 0;
}
'''


class BattleObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="emerald-observation-")
        cls.addClassCleanup(cls.tmp.cleanup)
        source = SOURCE.read_text()
        source = re.sub(r'^#include[^\n]*\n', '', source, flags=re.M)
        c_file = Path(cls.tmp.name) / "observation.c"
        cls.binary = Path(cls.tmp.name) / "observation"
        c_file.write_text(STUBS + source + MAIN)
        subprocess.run(["cc", "-std=gnu99", "-Wall", "-Wextra", "-Werror",
                        "-Wno-unused-variable", str(c_file), "-o", str(cls.binary)],
                       check=True, capture_output=True, text=True)

    def observe(self, mode=0):
        raw = subprocess.check_output([str(self.binary), str(mode)], text=True)
        self.assertLess(len(raw), 16384)
        return json.loads(raw)

    def test_nonportable_translation_unit_stays_empty(self):
        result = subprocess.run(["cc", "-E", "-P", "-x", "c", "-"],
                                input=SOURCE.read_text(), check=True,
                                capture_output=True, text=True)
        self.assertEqual(result.stdout.strip(), "")

    def test_activity_observation_is_allowlisted_local_state(self):
        self.assertEqual(self.observe()["activity"], {
            "phase": "menu", "mode": 0, "status": "peer menu",
            "link_connected": True, "generation": 17, "trade_phase": "inactive"})

    def test_trade_phase_getter_reaches_actual_serializer(self):
        for mode, phase in enumerate(
                ("choosing", "selected", "confirm", "cancel_confirm", "busy"), 33):
            with self.subTest(phase=phase):
                self.assertEqual(self.observe(mode)["activity"]["trade_phase"], phase)

    def test_party_getter_values_and_legacy_state(self):
        state = self.observe()
        self.assertEqual(state["frame"], 42)
        self.assertEqual(state["battle"], 0)
        self.assertEqual(state["objects"], [])
        self.assertEqual(state["party"], [
            {"slot": i, "species": 252 + i, "level": 5 + i,
             "hp": 0 if i else 17, "max_hp": 20 + i,
             "status": 128 if i else 0,
             "moves": [{"id": 33 + j, "pp": 35 - j} for j in range(4)]}
            for i in range(2)])

    def test_party_is_bounded_and_precontinue_is_safe(self):
        self.assertEqual(len(self.observe(1)["party"]), 6)
        for mode in (2, 3):
            with self.subTest(mode=mode):
                self.assertEqual(self.observe(mode)["party"], [])

    def test_public_runtime_values_have_exact_allowlisted_schema(self):
        state = self.observe(4)
        self.assertEqual(state["battle_state"], {
            "battle_type_flags": 0x80000001, "battlers_count": 4, "turn": 9,
            "battlers": [dict({"battler": i, "side": i & 1, "species": 100 + i,
                               "level": 50},
                              **({"hp": 123, "max_hp": 150, "status": 8}
                                 if not (i & 1) else {}))
                         for i in range(4)]})
        self.assertNotIn("65530", json.dumps(state))
        self.assertEqual(set(state), {"frame", "map", "pos", "facing", "moving",
                                     "overworld", "locked", "script", "battle",
                                     "fade", "bgm", "objects", "party", "battle_state", "activity"})

    def test_opponent_private_fields_are_absent_by_position_not_index(self):
        for mode in (4, 15, 31, 32):
            with self.subTest(mode=mode):
                for mon in self.observe(mode)["battle_state"]["battlers"]:
                    if mon["side"] == 1:
                        self.assertEqual(set(mon), {"battler", "side", "species", "level"})
                    else:
                        self.assertEqual((mon["hp"], mon["max_hp"], mon["status"]),
                                         (123, 150, 8))
        self.assertEqual(self.observe(4)["battle_state"],
                         self.observe(32)["battle_state"])

    def test_opponent_species_requires_settled_onscreen_reveal(self):
        for mode in range(16, 31):
            with self.subTest(mode=mode):
                state = self.observe(mode)
                battlers = state["battle_state"]["battlers"]
                self.assertNotIn(1, [mon["battler"] for mon in battlers])
                self.assertNotIn(101, [mon["species"] for mon in battlers])
                # A missing opponent reveal must not blank the safe own HUD/party.
                self.assertEqual([mon["battler"] for mon in battlers if mon["side"] == 0],
                                 [0, 2])
                self.assertEqual(battlers[0]["hp"], 123)
                self.assertEqual(state["party"], self.observe()["party"])
        self.assertEqual([mon["species"] for mon in
                          self.observe(4)["battle_state"]["battlers"]],
                         [100, 101, 102, 103])

    def test_runtime_requires_live_battle_valid_count_and_allocations(self):
        for mode in (0, 5, 6, 7, 8, 9, 11):
            with self.subTest(mode=mode):
                self.assertIsNone(self.observe(mode)["battle_state"])

    def test_unrevealed_absent_and_invalid_sprites_are_not_exposed(self):
        battlers = self.observe(10)["battle_state"]["battlers"]
        self.assertEqual([b["battler"] for b in battlers], [0])
        self.assertEqual(self.observe(12)["battle_state"]["battlers"], [])

    def test_maximum_numeric_payload_and_single_battle_are_bounded(self):
        state = self.observe(13)
        self.assertEqual(len(state["party"]), 6)
        self.assertEqual(state["party"][5]["status"], 0xFFFFFFFF)
        self.assertEqual(state["party"][5]["moves"][3]["id"], 0xFFFFFFFF)
        self.assertEqual(self.observe(14)["party"], [])
        state = self.observe(15)["battle_state"]
        self.assertEqual(state["battlers_count"], 2)
        self.assertEqual([b["battler"] for b in state["battlers"]], [0, 1])


if __name__ == "__main__":
    unittest.main()
