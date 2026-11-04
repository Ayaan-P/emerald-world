/* Production co-op functions with explicit IO/Pokemon accessor fixtures.
 * This tests boundaries and ownership, not native gameplay acceptance. */
#include "../../src/platform/world_coop.c"
#undef NDEBUG
#include <assert.h>
#include <stdio.h>

struct Pokemon gPlayerParty[PARTY_SIZE], gEnemyParty[PARTY_SIZE];
u8 gPlayerPartyCount, gActiveBattler, gBattlerAttacker, gBattlerTarget, gBattleOutcome;
u16 gLastUsedItem, gBattlerPartyIndexes[MAX_BATTLERS_COUNT];
struct BattlePokemon gBattleMons[MAX_BATTLERS_COUNT];
static int bag[LAST_BALL + 1], removals, aborts, storageFull;
static u32 generation = 17;
u32 NativeLink_Generation(void) { return generation; }
void NativeLink_Abort(void) { aborts++; }
bool8 IsPokemonStorageFull(void) { return storageFull; }
bool8 CheckBagHasItem(u16 item, u16 count) { return item <= LAST_BALL && bag[item] >= count; }
bool8 RemoveBagItem(u16 item, u16 count)
{
    if (!CheckBagHasItem(item, count)) return FALSE;
    bag[item] -= count;
    removals++;
    return TRUE;
}
static int caughtDex;
static u8 emitted[2][112];
static u16 emittedSize[2];
void PrepareBufferDataTransferLink(u8 direction, u16 size, u8 *data)
{
    assert(direction == B_COMM_TO_CONTROLLER && !(gActiveBattler & BIT_SIDE));
    assert(size <= sizeof(emitted[0]));
    memset(emitted[gActiveBattler / 2], 0, sizeof(emitted[0]));
    memcpy(emitted[gActiveBattler / 2], data, size);
    emittedSize[gActiveBattler / 2] = size;
}
void MarkBattlerForControllerExec(u8 battler) { assert(battler == 0 || battler == 2); }
static void Seal(struct Pokemon *mon, u16 species, u16 ball);
void SetMonData(struct Pokemon *mon, s32 field, const void *value)
{
    if (field == MON_DATA_HP) memcpy(&mon->hp, value, sizeof(mon->hp));
    else if (field == MON_DATA_STATUS) memcpy(&mon->status, value, sizeof(mon->status));
    else if (field == MON_DATA_POKEBALL)
        Seal(mon, GetMonData(mon, MON_DATA_SPECIES), *(const u16 *)value);
    else assert(!"unexpected fixture setter");
}
s8 GetSetPokedexFlag(u16 species, u8 operation) { return caughtDex; }
u16 SpeciesToNationalPokedexNum(u16 species) { return species; }
u32 GetMonData(struct Pokemon *mon, s32 field, u8 *dest)
{
    u32 key = mon->box.personality ^ mon->box.otId;
    switch (field)
    {
    case MON_DATA_SPECIES: return (mon->box.secure.raw[0] ^ key) & 0xFFFF;
    case MON_DATA_POKEBALL: return (mon->box.secure.raw[0] ^ key) >> 16;
    case MON_DATA_IS_EGG: return 0;
    case MON_DATA_HELD_ITEM: return 0;
    case MON_DATA_EXP: return 1000;
    case MON_DATA_PP_BONUSES: return 0;
    default: return 0;
    }
}
u32 GetMonData2(struct Pokemon *mon, s32 field) { return GetMonData3(mon, field, NULL); }
u8 CalculatePPWithBonus(u16 move, u8 bonus, u8 index) { return 40; }
static void Seal(struct Pokemon *mon, u16 species, u16 ball)
{
    u32 key = mon->box.personality ^ mon->box.otId;
    u32 word = species | ((u32)ball << 16);
    mon->box.checksum = species + ball;
    for (unsigned i = 0; i < ARRAY_COUNT(mon->box.secure.raw); i++)
        mon->box.secure.raw[i] = key ^ (i ? 0 : word);
}
static void Reset(void)
{
    memset(&sCoop, 0, sizeof(sCoop));
    memset(bag, 0, sizeof(bag));
    sCoop.state = COOP_BATTLE;
    sCoop.generation = generation = 17;
    sCoop.seed = 123;
    sCoop.enemyCount = 1;
    sCoop.originalCount = 6;
    sCoop.enemies[0].box.personality = 55;
    sCoop.enemies[0].box.otId = 77;
    sCoop.enemies[0].box.hasSpecies = TRUE;
    sCoop.enemies[0].box.language = LANGUAGE_ENGLISH;
    sCoop.enemies[0].level = 10;
    sCoop.enemies[0].hp = sCoop.enemies[0].maxHP = 30;
    sCoop.enemies[0].attack = sCoop.enemies[0].defense = 20;
    sCoop.enemies[0].speed = sCoop.enemies[0].spAttack = sCoop.enemies[0].spDefense = 20;
    Seal(&sCoop.enemies[0], 100, ITEM_POKE_BALL);
    bag[ITEM_POKE_BALL] = bag[ITEM_REPEAT_BALL] = bag[ITEM_DIVE_BALL] = 2;
    storageFull = removals = aborts = caughtDex = 0;
    gBattleOutcome = B_OUTCOME_CAUGHT;
}
static struct CoopCompletion Completion(void)
{
    struct CoopCompletion packet = {0};
    packet.magic = COOP_MAGIC;
    packet.version = COOP_VERSION;
    packet.phase = COOP_READY;
    packet.generation = generation;
    packet.seed = sCoop.seed;
    packet.sender = 1;
    packet.outcome = B_OUTCOME_CAUGHT;
    packet.catchOwner = sCoop.catchOwner;
    return packet;
}
int main(int argc, char **argv)
{
    Reset();
    if (argc > 1)
    {
        struct CoopCompletion packet;
        sCoop.catchOwner = 1;
        packet = Completion();
        packet.reward = 1; /* A single wild mon cannot be defeated and caught. */
        assert(WorldCoop_ReceiveCompletion((u8 *)&packet, sizeof(packet), 1) == -1);
        puts("caught completion rejects invented defeat reward");
        return 0;
    }
    for (int local = 0; local < 2; local++)
    {
        u8 event[12] = {CONTROLLER_EXPUPDATE, COOP_BALL_USE, local + 1, ITEM_POKE_BALL};
        Reset(); sCoop.local = local; gActiveBattler = local * 2;
        memcpy(event + 4, &generation, 4);
        assert(WorldCoop_SelectBall(ITEM_POKE_BALL) == ITEM_POKE_BALL);
        assert(removals == 0); /* Menu selection must never consume. */
        assert(WorldCoop_CatchPacketValid(event, sizeof(event)));
        WorldCoop_RecordCatchEvent(event);
        assert(removals == 1 && bag[ITEM_POKE_BALL] == 1 && !aborts);
        WorldCoop_RecordCatchEvent(event);
        assert(removals == 1 && aborts == 1); /* No replay double charge. */
        generation++;
        assert(!WorldCoop_CatchPacketValid(event, sizeof(event)));
    }
    Reset();
    caughtDex = 1;
    assert(WorldCoop_SelectBall(ITEM_REPEAT_BALL) == (ITEM_REPEAT_BALL | 0x100));
    sCoop.environment = BATTLE_ENVIRONMENT_UNDERWATER;
    assert(WorldCoop_SelectBall(ITEM_DIVE_BALL) == (ITEM_DIVE_BALL | 0x200));
    for (unsigned value = 0; value < 65536; value++)
    {
        unsigned ball = value & 255;
        int expected = !value || (ball >= ITEM_MASTER_BALL && ball <= LAST_BALL
            && ball != ITEM_SAFARI_BALL && !(value & ~0x3FF)
            && (!(value & 0x100) || ball == ITEM_REPEAT_BALL)
            && (!(value & 0x200) || ball == ITEM_DIVE_BALL));
        assert(WorldCoop_BallReplyValid(value) == expected);
    }
    sCoop.kind = 1;
    assert(!WorldCoop_BallReplyValid(ITEM_POKE_BALL));
    assert(!WorldCoop_SelectBall(ITEM_POKE_BALL));
    Reset();
    {
        u8 wire[112] = {0};
        struct CoopCatchPacket packet = { CONTROLLER_EXPUPDATE, COOP_CATCH, 2, 0, generation };
        packet.mon = sCoop.enemies[0]; packet.mon.hp = 4; packet.mon.status = 8;
        Seal(&packet.mon, 100, ITEM_REPEAT_BALL);
        memcpy(wire, &packet, sizeof(packet));
        assert(WorldCoop_CatchPacketValid(wire, sizeof(wire)));
        for (int size = 0; size < 112; size++)
            assert(!WorldCoop_CatchPacketValid(wire, size));
        wire[111] = 1; assert(!WorldCoop_CatchPacketValid(wire, 112)); wire[111] = 0;
        wire[2] = 3; assert(!WorldCoop_CatchPacketValid(wire, 112)); wire[2] = 2;
        packet.mon.box.checksum++; memcpy(wire, &packet, sizeof(packet));
        assert(!WorldCoop_CatchPacketValid(wire, 112));
        packet.mon.box.checksum--; memcpy(wire, &packet, sizeof(packet));
        WorldCoop_RecordCatchEvent(wire);
        assert(sCoop.catchOwner == 2 && sCoop.caughtMon.hp == 4 && sCoop.caughtMon.status == 8);
        sCoop.commitSent = sCoop.peerReady = TRUE;
        assert(!WorldCoop_CompletionCommitted());
        assert(!WorldCoop_BeginCatchRewards());
        sCoop.peerCommit = TRUE;
        assert(WorldCoop_CompletionCommitted());
        generation++;
        assert(!WorldCoop_CompletionCommitted());
        generation--;
        sCoop.state = COOP_REWARDS;
        assert(!WorldCoop_BeginCatchRewards()); /* Wrong human. */
        sCoop.local = 1;
        storageFull = 1;
        assert(!WorldCoop_BeginCatchRewards());
        storageFull = 0;
        assert(WorldCoop_BeginCatchRewards());
        assert(gEnemyParty[0].hp == 4 && gEnemyParty[0].status == 8);
        assert(gBattleMons[1].species == 100 && gBattleMons[1].hp == 4
            && gBattleMons[1].status1 == 8 && gBattleMons[1].level == 10);
        assert(gBattlerAttacker == 0 && gBattlerTarget == 1 && gLastUsedItem == ITEM_REPEAT_BALL);
        assert(!WorldCoop_BeginCatchRewards()); /* Exactly once. */
    }
    Reset();
    gEnemyParty[0] = sCoop.enemies[0];
    gBattlerAttacker = 2;
    gLastUsedItem = ITEM_ULTRA_BALL;
    gBattleMons[1].hp = 3;
    gBattleMons[1].status1 = 8;
    WorldCoop_EmitBallUse(ITEM_ULTRA_BALL);
    assert(emittedSize[1] == 9 && emitted[1][2] == 2 && emitted[1][3] == ITEM_ULTRA_BALL);
    assert(WorldCoop_EmitCatch());
    for (int peer = 0; peer < 2; peer++)
    {
        assert(emittedSize[peer] == 108);
        assert(WorldCoop_CatchPacketValid(emitted[peer], 112));
    }
    assert(!memcmp(emitted[0], emitted[1], 112));
    WorldCoop_RecordCatchEvent(emitted[1]);
    assert(sCoop.catchOwner == 2 && sCoop.caughtMon.hp == 3 && sCoop.caughtMon.status == 8);
    assert(GetMonData(&sCoop.caughtMon, MON_DATA_POKEBALL) == ITEM_ULTRA_BALL);
    assert(!WorldCoop_EmitCatch());
    puts("catch boundaries: private consumption, context, malformed wire, generation, commit and single-owner delivery passed");
    return 0;
}
