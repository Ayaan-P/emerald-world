/* Production co-op boundaries plus the stock Pokemon encryption/accessors and
 * GiveMonToPlayer, with explicit IO and PC-sink fixtures, not native gameplay. */
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
#include "string_util.h"
#include "constants/battle.h"
#include "constants/species.h"
static union PokemonSubstruct *GetSubstruct(struct BoxPokemon *, u32, u8);
static u16 CalculateBoxMonChecksum(struct BoxPokemon *);
static void EncryptBoxMon(struct BoxPokemon *);
static void DecryptBoxMon(struct BoxPokemon *);
static u16 GetDeoxysStat(struct Pokemon *mon, s32 stat) { return 0; }
static struct BoxPokemon storedMon;
static u8 CopyMonToPC(struct Pokemon *mon)
{
    storedMon = mon->box;
    return MON_GIVEN_TO_PC;
}
static struct SaveBlock2 saveBlock2;
struct SaveBlock2 *gSaveBlock2Ptr = &saveBlock2;
const u8 gText_EggNickname[] = { EOS }, gText_BadEgg[] = { EOS };
const u32 gBitTable[] = {1, 2, 4, 8}; /* Stock moves-known query only. */
#include "stock_pokemon.inc"
s8 GetSetPokedexFlag(u16 species, u8 operation) { return caughtDex; }
u16 SpeciesToNationalPokedexNum(u16 species) { return species; }
u8 CalculatePPWithBonus(u16 move, u8 bonus, u8 index) { return 40; }
u8 *StringCopy(u8 *dest, const u8 *src)
{
    while ((*dest = *src++) != EOS) dest++;
    return dest;
}
u16 StringLength(const u8 *src)
{
    const u8 *end = src;
    while (*end != EOS) end++;
    return end - src;
}
static void Seal(struct Pokemon *mon, u16 species, u16 ball)
{
    /* Valid encrypted fixture in all 24 stock personality permutations. */
    u32 exp = 1000;
    memset(&mon->box.secure, 0, sizeof(mon->box.secure));
    mon->box.checksum = 0;
    EncryptBoxMon(&mon->box);
    SetMonData(mon, MON_DATA_SPECIES, &species);
    SetMonData(mon, MON_DATA_POKEBALL, &ball);
    SetMonData(mon, MON_DATA_EXP, &exp);
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
static void TestStockCatchOwnership(void)
{
    for (int local = 0; local < 2; local++)
    for (int permutation = 0; permutation < 24; permutation++)
    for (int pc = 0; pc < 2; pc++)
    for (int nickname = 0; nickname < 2; nickname++)
    {
        u32 hostId = 2703024129u, catcherId = local ? 2964324354u : hostId;
        u16 move = MOVE_TACKLE, move2 = MOVE_STRING_SHOT;
        u32 exp = 27;
        u8 pp = 35, pp2 = 40, gender = 1;
        u8 name[POKEMON_NAME_LENGTH] = {0xBB, 0xBC, EOS, EOS, EOS, EOS, EOS, EOS, EOS, EOS};
        struct Pokemon snapshot, original;
        struct Pokemon *caught;
        struct Pokemon boxed = {0};
        Reset();
        memset(gPlayerParty, 0, sizeof(gPlayerParty));
        memcpy(saveBlock2.playerTrainerId, &catcherId, sizeof(catcherId));
        memset(saveBlock2.playerName, EOS, sizeof(saveBlock2.playerName));
        saveBlock2.playerName[0] = 0xBC;
        saveBlock2.playerGender = gender;
        sCoop.local = local;
        sCoop.originalCount = pc ? PARTY_SIZE : 1;
        sCoop.enemies[0].box.personality = permutation + 240;
        sCoop.enemies[0].box.otId = hostId;
        Seal(&sCoop.enemies[0], SPECIES_WURMPLE, ITEM_POKE_BALL);
        SetMonData(&sCoop.enemies[0], MON_DATA_EXP, &exp);
        SetMonData(&sCoop.enemies[0], MON_DATA_MOVE1, &move);
        SetMonData(&sCoop.enemies[0], MON_DATA_MOVE2, &move2);
        SetMonData(&sCoop.enemies[0], MON_DATA_PP1, &pp);
        SetMonData(&sCoop.enemies[0], MON_DATA_PP2, &pp2);
        assert(MonValid(&sCoop.enemies[0], FALSE));
        gEnemyParty[0] = sCoop.enemies[0];
        gBattlerAttacker = local * 2;
        gLastUsedItem = ITEM_MASTER_BALL;
        gBattleMons[1].hp = 4;
        gBattleMons[1].status1 = 8;
        assert(WorldCoop_EmitCatch());
        assert(WorldCoop_CatchPacketValid(emitted[local], 112));
        WorldCoop_RecordCatchEvent(emitted[local]);
        snapshot = sCoop.caughtMon;
        original = gPlayerParty[0] = sCoop.enemies[0];
        if (pc)
            for (int slot = 1; slot < PARTY_SIZE; slot++) gPlayerParty[slot] = original;
        sCoop.commitSent = sCoop.peerReady = sCoop.peerCommit = TRUE;
        assert(WorldCoop_CompletionCommitted());
        sCoop.state = COOP_REWARDS;
        assert(WorldCoop_BeginCatchRewards());
        assert(MonValid(&gEnemyParty[0], FALSE));
        assert(gEnemyParty[0].box.checksum == snapshot.box.checksum);
        assert(gEnemyParty[0].hp == 4 && gEnemyParty[0].status == 8);
        assert(gEnemyParty[0].maxHP == snapshot.maxHP);
        assert(gEnemyParty[0].attack == snapshot.attack && gEnemyParty[0].defense == snapshot.defense);
        assert(gEnemyParty[0].speed == snapshot.speed && gEnemyParty[0].spAttack == snapshot.spAttack
            && gEnemyParty[0].spDefense == snapshot.spDefense);
        /* Dex/nickname queries and optional nickname edit precede stock give. */
        assert(GetMonData(&gEnemyParty[0], MON_DATA_SPECIES) == SPECIES_WURMPLE);
        assert(GetMonData(&gEnemyParty[0], MON_DATA_PERSONALITY) == (u32)permutation + 240);
        if (nickname) SetMonData(&gEnemyParty[0], MON_DATA_NICKNAME, name);
        assert(GiveMonToPlayer(&gEnemyParty[0]) == (pc ? MON_GIVEN_TO_PC : MON_GIVEN_TO_PARTY));
        boxed.box = storedMon;
        caught = pc ? &boxed : &gPlayerParty[1];
        if (!MonValid(&gEnemyParty[0], FALSE))
            fprintf(stderr, "stock catch corruption: local=%d permutation=%d pc=%d nickname=%d exp=%u move=%u\n",
                    local, permutation, pc, nickname,
                    GetMonData(caught, MON_DATA_EXP), GetMonData(caught, MON_DATA_MOVE1));
        assert(MonValid(&gEnemyParty[0], FALSE));
        assert(GetMonData(caught, MON_DATA_SPECIES) == SPECIES_WURMPLE);
        assert(GetMonData(caught, MON_DATA_EXP) == exp);
        assert(GetMonData(caught, MON_DATA_MOVE1) == move);
        assert(GetMonData(caught, MON_DATA_MOVE2) == move2);
        assert(GetMonData(caught, MON_DATA_MOVE3) == MOVE_NONE);
        assert(GetMonData(caught, MON_DATA_MOVE4) == MOVE_NONE);
        assert(GetMonData(caught, MON_DATA_PP1) == pp);
        assert(GetMonData(caught, MON_DATA_PP2) == pp2);
        assert(GetMonData(caught, MON_DATA_PP3) == 0);
        assert(GetMonData(caught, MON_DATA_PP4) == 0);
        assert(GetMonData(caught, MON_DATA_POKEBALL) == ITEM_MASTER_BALL);
        assert(GetMonData(caught, MON_DATA_OT_ID) == catcherId);
        assert(gBattleMons[1].otId == catcherId);
        assert(GetMonData(caught, MON_DATA_PERSONALITY) == snapshot.box.personality);
        if (!pc)
        {
            assert(caught->hp == 4 && caught->status == 8 && caught->maxHP == snapshot.maxHP);
            assert(caught->level == snapshot.level);
            assert(MonValid(caught, FALSE));
        }
        assert(GetMonData(caught, MON_DATA_OT_GENDER) == gender);
        assert(!memcmp(caught->box.otName, saveBlock2.playerName, PLAYER_NAME_LENGTH));
        if (nickname) assert(!memcmp(caught->box.nickname, name, sizeof(name)));
        assert(!memcmp(&snapshot, &sCoop.caughtMon, sizeof(snapshot)));
        assert(!memcmp(&original, &gPlayerParty[0], sizeof(original)));
        assert(!WorldCoop_BeginCatchRewards());
    }
    puts("stock catch ownership: host/follower, 24 permutations, party/PC and nickname passed");
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
    TestStockCatchOwnership();
    puts("catch boundaries: private consumption, context, malformed wire, generation, commit and single-owner delivery passed");
    return 0;
}
