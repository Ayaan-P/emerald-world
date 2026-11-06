"""Execute the bounded Expansion ability module, then real damage/type hooks."""
from pathlib import Path
import subprocess
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'build/rc4-expanded-abilities'


class ExpandedAbilityTests(unittest.TestCase):
    def compile_run(self, name, body):
        BUILD.mkdir(parents=True, exist_ok=True)
        stubs = BUILD / 'stubs'
        stubs.mkdir(exist_ok=True)
        (stubs / 'global.h').write_text('''#ifndef TEST_GLOBAL_H
#define TEST_GLOBAL_H
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
typedef int32_t s32; typedef uint8_t bool8; typedef uint32_t bool32;
#define TRUE 1
#define FALSE 0
#include "constants/pokemon.h"
#endif
''')
        (stubs / 'battle.h').write_text('''#include "constants/battle.h"
extern u32 gBattleTypeFlags;
#define IS_TYPE_PHYSICAL(t) ((t) < TYPE_MYSTERY)
#define IS_TYPE_SPECIAL(t) ((t) > TYPE_MYSTERY)
''')
        (stubs / 'pokemon.h').write_text('''#ifndef TEST_POKEMON_H
#define TEST_POKEMON_H
struct BattleMove {u8 effect, power, type, accuracy, pp, secondaryEffectChance, target; int8_t priority; u32 flags;};
extern const struct BattleMove gBattleMoves[];
#endif
''')
        (stubs / 'event_data.h').write_text('')
        source = BUILD / (name + '.c')
        exe = BUILD / name
        source.write_text(body + '\n/* Inert legacy chart: ability probes do not inspect type charts. */\nconst unsigned char gTypeEffectiveness[336] = {0};\n')
        result = subprocess.run([
            'cc', '-std=gnu99', '-Wall', '-Wextra', '-Werror',
            '-DPORTABLE', '-DVER_64BIT', '-iquote', str(stubs), '-iquote', 'include', '-iquote', '.', '-iquote', 'gflib',
            str(source), 'src/platform/expanded_abilities.c', 'src/platform/expanded_moves.c', '-o', str(exe)
        ], cwd=ROOT, capture_output=True, text=True)
        (BUILD / (name + '.compile.txt')).write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(exe)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_technician_resolved_power_and_world_gate(self):
        self.compile_run('technician', r'''
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "constants/abilities.h"
#include "constants/moves.h"
#include "platform/expanded_abilities.h"
#include <assert.h>
u32 gBattleTypeFlags;
static bool8 modern;
bool8 WorldRules_Enabled(u32 rule) { assert(rule == 4); return modern; }
int NativeLink_IsActive(void) { return FALSE; }
const struct BattleMove gBattleMoves[MOVES_COUNT] = {
    [MOVE_QUICK_ATTACK] = {.power=40, .type=TYPE_NORMAL, .flags=FLAG_MAKES_CONTACT},
    [MOVE_WATER_GUN] = {.power=40, .type=TYPE_WATER},
    [MOVE_LOW_KICK] = {.power=1, .type=TYPE_FIGHTING, .flags=FLAG_MAKES_CONTACT},
    [MOVE_GROWL] = {.power=0, .type=TYPE_NORMAL},
};
int main(void) {
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_QUICK_ATTACK, 40) == 40);
    modern=TRUE;
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_QUICK_ATTACK, 40) == 60);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_WATER_GUN, 40) == 60);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_LOW_KICK, 60) == 90);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_LOW_KICK, 61) == 61);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_LOW_KICK, 1) == 1);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_LOW_KICK, 0) == 0);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_NONE, MOVE_QUICK_ATTACK, 40) == 40);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_GROWL, 40) == 40);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVES_COUNT, 40) == 40);
    gBattleTypeFlags=BATTLE_TYPE_RECORDED;
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TECHNICIAN, MOVE_QUICK_ATTACK, 40) == 40);
    return 0;
}
''')

    def test_real_damage_hook_order_and_confusion(self):
        from test.world.test_move_split_damage import PRELUDE
        text = (ROOT / 'src/pokemon.c').read_text()
        fn = 's32 CalculateBaseDamage(' + text.split('s32 CalculateBaseDamage(', 1)[1].split('\n}', 1)[0] + '\n}'
        wired = 'ExpandedAbilities_ModifyBasePower' in fn
        if not wired:
            # Compile the exact proposed production hunk too, but fail the final
            # assertion until the owner installs it. No silent helper-only pass.
            fn = fn.replace('    attack = attacker->attack;', '''#ifdef PORTABLE
    if (attacker != defender && battlerIdAtk != battlerIdDef)
        gBattleMovePower = ExpandedAbilities_ModifyBasePower(attacker->ability, move, gBattleMovePower);
#endif
    attack = attacker->attack;''', 1)
        constants = sorted({n for n in re.findall(r'\b[A-Z][A-Z0-9_]+\b', fn)
                            if n.startswith(('HOLD_EFFECT_', 'SPECIES_', 'ABILITYEFFECT_'))})
        defines = '\n'.join(f'#define {n} {100+i}' for i,n in enumerate(constants)) + '\n'
        stubs = r'''
#include "constants/abilities.h"
#include "constants/moves.h"
#include "platform/expanded_abilities.h"
#include "pokemon.h"
struct BattlePokemon {u16 ability,attack,defense,hp,item,level,maxHP,spAttack,spDefense,species;u8 statStages[8];u32 status1;};
const struct BattleMove gBattleMoves[MOVES_COUNT] = {
 [MOVE_POUND]={.power=40,.type=TYPE_NORMAL,.flags=1},
 [MOVE_QUICK_ATTACK]={.power=40,.type=TYPE_NORMAL,.flags=1},
 [MOVE_FIRE_PUNCH]={.power=75,.type=TYPE_FIRE,.flags=1},
 [MOVE_WATER_GUN]={.power=40,.type=TYPE_WATER},
 [MOVE_PETAL_DANCE]={.power=70,.type=TYPE_GRASS,.flags=1},
 [MOVE_EARTHQUAKE]={.power=100,.type=4},
};
struct Berry {u8 holdEffect,holdEffectParam;} gEnigmaBerries[4];
struct Flags {u32 flags[4];};struct Resources {struct Flags *flags;};
struct Flags flags;struct Resources resources={&flags},*gBattleResources=&resources;
u32 gBattleTypeFlags,gBattleWeather,gBattleMovePower;u8 gCritMultiplier=1;u16 gCurrentMove;
static const u16 sHoldEffectToType[][2]={{0,0}};
int flag;
bool8 FlagGet(u16 id) {(void)id;return 0;}
bool8 WorldRules_Enabled(u32 rule) {assert(rule==4);return flag;}
int NativeLink_IsActive(void) {return 0;}
#include "battle_move_split.h"
int GetItemHoldEffect(int x) {(void)x;return 0;}
int GetItemHoldEffectParam(int x) {(void)x;return 0;}
int ShouldGetStatBadgeBoost(int x,int y) {(void)x;(void)y;return 0;}
int AbilityBattleEffects(int a,int b,int c,int d,int e) {(void)a;(void)b;(void)c;(void)d;(void)e;return 0;}
int CountAliveMonsInBattle(int x) {(void)x;return 1;}
'''
        main = r'''
int main(void) {
 struct BattlePokemon a={0},d={0};
 a.attack=a.spAttack=a.defense=a.spDefense=100;a.level=50;a.hp=a.maxHP=100;
 d.defense=d.spDefense=100;gCurrentMove=MOVE_QUICK_ATTACK;
 a.ability=ABILITY_TECHNICIAN;
 assert(CalculateBaseDamage(&a,&d,MOVE_QUICK_ATTACK,0,60,0,0,1)==28);
 flag=1;
 /* Power 60 becomes 90 before the formula/+2. Multiplying 28 damage
  * by 1.5 afterwards would incorrectly produce 42 instead of 41. */
 assert(CalculateBaseDamage(&a,&d,MOVE_QUICK_ATTACK,0,60,0,0,1)==41);
 assert(CalculateBaseDamage(&a,&d,MOVE_QUICK_ATTACK,0,61,0,0,1)==28);
 assert(CalculateBaseDamage(&a,&d,MOVE_WATER_GUN,0,60,0,0,1)==41);
 assert(CalculateBaseDamage(&a,&a,MOVE_POUND,0,40,0,0,0)==19);
 a.ability=ABILITY_TOUGH_CLAWS;gCurrentMove=MOVE_FIRE_PUNCH;
 assert(CalculateBaseDamage(&a,&d,MOVE_FIRE_PUNCH,0,0,0,0,1)==45);
 assert(CalculateBaseDamage(&a,&d,MOVE_EARTHQUAKE,0,0,0,0,1)==46);
 assert(CalculateBaseDamage(&a,&d,MOVE_PETAL_DANCE,0,0,0,0,1)==42);
 return 0;
}
'''
        self.compile_run('production_damage', PRELUDE + defines + stubs + fn + main)
        self.assertTrue(wired, 'Owner must apply build/rc4-expanded-abilities/production-hooks.patch: damage hook absent')

    def test_live_and_ai_stab_prefixes_and_probe_wiring(self):
        text = (ROOT / 'src/battle_script_commands.c').read_text()
        funcs = []
        wired = True
        for signature, attacker, move, end in (
            ('static void Cmd_typecalc(void)\n{', 'gBattlerAttacker', 'gCurrentMove', '    if (gBattleMons[gBattlerTarget].ability'),
            ('u8 TypeCalc(u16 move, u8 attacker, u8 defender)\n{', 'attacker', 'move', '    if (gBattleMons[defender].ability'),
        ):
            start = text.index(signature)
            prefix = text[start:text.index(end, start)]
            active = 'ExpandedAbilities_ApplyStab' in prefix
            wired = wired and active
            if not active:
                original = f'''    if (IS_BATTLER_OF_TYPE({attacker}, moveType))
    {{
        gBattleMoveDamage = gBattleMoveDamage * 15;
        gBattleMoveDamage = gBattleMoveDamage / 10;
    }}'''
                replacement = f'''    gBattleMoveDamage = ExpandedAbilities_ApplyStab(gBattleMoveDamage,
        gBattleMons[{attacker}].ability, {move}, moveType,
        gBattleMons[{attacker}].types[0], gBattleMons[{attacker}].types[1]);'''
                self.assertIn(original, prefix)
                prefix = prefix.replace(original, replacement)
            prefix = prefix.replace('    s32 i = 0;\n', '').replace('    u8 flags = 0;\n', '')
            # Stop at the real type-effectiveness boundary, after the STAB hook.
            prefix += '\n}' if attacker == 'gBattlerAttacker' else '\n(void)defender; return 0;\n}'
            funcs.append(prefix)
        self.compile_run('production_stab_prefixes', r'''
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "constants/abilities.h"
#include "constants/moves.h"
#include "platform/expanded_abilities.h"
#include <assert.h>
u32 gBattleTypeFlags;
static bool8 modern;
bool8 WorldRules_Enabled(u32 rule) {assert(rule==4);return modern;}
int NativeLink_IsActive(void) {return 0;}
const struct BattleMove gBattleMoves[MOVES_COUNT] = {
 [MOVE_FIRE_PUNCH]={.power=75,.type=TYPE_FIRE,.flags=1}
};
struct {u8 ability,types[2];} gBattleMons[4];
u8 gBattlerAttacker;
u16 gCurrentMove;
s32 gBattleMoveDamage;
u8 script[2],*gBattlescriptCurrInstr=script;
#define GET_MOVE_TYPE(m,t) ((t)=gBattleMoves[(m)].type)
#define IS_BATTLER_OF_TYPE(b,t) (gBattleMons[b].types[0]==(t)||gBattleMons[b].types[1]==(t))
''' + '\n'.join(funcs) + r'''
int main(void) {
 gCurrentMove=MOVE_FIRE_PUNCH;
 gBattleMons[0].ability=ABILITY_ADAPTABILITY;
 gBattleMons[0].types[0]=TYPE_FIRE;gBattleMons[0].types[1]=TYPE_FLYING;
 gBattleMoveDamage=31;Cmd_typecalc();assert(gBattleMoveDamage==46);
 modern=1;
 gBattleMoveDamage=31;Cmd_typecalc();assert(gBattleMoveDamage==62);
 /* The caller's next type-effectiveness operation follows STAB. */
 gBattleMoveDamage/=2;assert(gBattleMoveDamage==31);
 gBattleMoveDamage=31;TypeCalc(MOVE_FIRE_PUNCH,0,1);assert(gBattleMoveDamage==62);
 gBattleMons[0].types[0]=TYPE_WATER;
 gBattleMoveDamage=31;TypeCalc(MOVE_FIRE_PUNCH,0,1);assert(gBattleMoveDamage==31);
 return 0;
}
''')
        self.assertTrue(wired, 'Owner must install both live and AI STAB hooks from production-hooks.patch')
        ai = (ROOT / 'src/battle_ai_script_commands.c').read_text()
        for name in ('static void Cmd_get_highest_type_effectiveness(void)\n{', 'static void Cmd_if_type_effectiveness(void)\n{'):
            body = ai.split(name, 1)[1].split('\n}', 1)[0]
            self.assertIn('ExpandedAbilities_NormalizeAiEffectiveness', body, 'Modern moves owner must normalize Adaptability in both 40-damage effectiveness probes')
            self.assertLess(body.index('ExpandedAbilities_NormalizeAiEffectiveness'), body.index('if (gBattleMoveDamage == 120)'))

    def test_native_display_tables_cover_appended_ids(self):
        text = (ROOT / 'src/data/text/abilities.h').read_text()
        for name, description in (
            ('TECHNICIAN', 'Powers up weak moves.'),
            ('ADAPTABILITY', 'Powers up same-type moves.'),
            ('TOUGH_CLAWS', 'Powers up contact moves.'),
        ):
            self.assertIn(f'[ABILITY_{name}] = _("{name.replace("_", " ")}")', text)
            self.assertIn(description, text)
            self.assertEqual(text.count(f'[ABILITY_{name}]'), 2)

    def test_contact_stab_and_explicit_donor_mapping(self):
        self.compile_run('contact_stab_mapping', r'''
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "constants/abilities.h"
#include "constants/moves.h"
#include "platform/expanded_abilities.h"
#include <assert.h>
u32 gBattleTypeFlags;
static bool8 modern;
bool8 WorldRules_Enabled(u32 rule) { assert(rule == 4); return modern; }
int NativeLink_IsActive(void) { return FALSE; }
const struct BattleMove gBattleMoves[MOVES_COUNT] = {
    [MOVE_FIRE_PUNCH] = {.power=75, .type=TYPE_FIRE, .flags=FLAG_MAKES_CONTACT},
    [MOVE_EARTHQUAKE] = {.power=100, .type=TYPE_GROUND},
    [MOVE_PETAL_DANCE] = {.power=70, .type=TYPE_GRASS, .flags=FLAG_MAKES_CONTACT},
    [MOVE_GROWL] = {.type=TYPE_NORMAL, .flags=FLAG_MAKES_CONTACT},
};
int main(void) {
    u8 native=255;
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TOUGH_CLAWS, MOVE_FIRE_PUNCH, 75) == 75);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 46);
    modern=TRUE;
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TOUGH_CLAWS, MOVE_FIRE_PUNCH, 75) == 98);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TOUGH_CLAWS, MOVE_EARTHQUAKE, 100) == 100);
    /* Contact is independent of physical/special category. */
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TOUGH_CLAWS, MOVE_PETAL_DANCE, 70) == 91);
    assert(ExpandedAbilities_ModifyBasePower(ABILITY_TOUGH_CLAWS, MOVE_GROWL, 70) == 70);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 62);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_WATER, TYPE_FIRE) == 62);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_WATER, TYPE_FLYING) == 31);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_NONE, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FIRE) == 46);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_STRUGGLE, TYPE_NORMAL, TYPE_NORMAL, TYPE_NORMAL) == 31);
    assert(ExpandedAbilities_ApplyStab(31, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_MYSTERY, TYPE_MYSTERY, TYPE_MYSTERY) == 31);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(80, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 40);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(160, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 80);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(320, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 160);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(40, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 20);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(20, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 10);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(0, ABILITY_ADAPTABILITY, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 0);
    assert(ExpandedAbilities_NormalizeAiEffectiveness(120, ABILITY_NONE, MOVE_FIRE_PUNCH, TYPE_FIRE, TYPE_FIRE, TYPE_FLYING) == 120);
    assert(ExpandedAbilities_FromExpansion(101, &native) && native == ABILITY_TECHNICIAN);
    assert(ExpandedAbilities_FromExpansion(91, &native) && native == ABILITY_ADAPTABILITY);
    assert(ExpandedAbilities_FromExpansion(181, &native) && native == ABILITY_TOUGH_CLAWS);
    assert(ExpandedAbilities_FromExpansion(76, &native) && native == ABILITY_AIR_LOCK);
    assert(ExpandedAbilities_FromExpansion(75, &native) && native == ABILITY_SHELL_ARMOR);
    assert(!ExpandedAbilities_FromExpansion(77, &native) && native == ABILITY_SHELL_ARMOR);
    assert(!ExpandedAbilities_FromExpansion(357, &native) && native == ABILITY_SHELL_ARMOR);
    assert(!ExpandedAbilities_FromExpansion(101, 0));
    assert(ABILITY_CACOPHONY == 76 && ABILITY_AIR_LOCK == 77 && ABILITIES_COUNT <= 256);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
