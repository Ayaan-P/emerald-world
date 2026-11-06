"""Compile the production adapter with disposable modern form-table variants."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class MegaCrossRuleTests(unittest.TestCase):
    def test_actual_adapter_form_policy(self):
        # Reuse only the existing adapter fixture's header declarations. No
        # adapter logic is replaced, and variant tables live outside the tree.
        import ast
        fixture = ast.parse((ROOT / 'test/world/test_mega_game_adapter.py').read_text())
        headers = {}
        for node in ast.walk(fixture):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('globalh', 'battleh', 'pokemonh'):
                        headers[target.id] = node.value.value
        main = r'''
#include "global.h"
#include "battle.h"
#include "pokemon.h"
#include "battle_controllers.h"
#include "constants/species.h"
#include "constants/items.h"
#include "platform/mega_game.h"
#include "platform/mega_forms.h"
#include <assert.h>
struct Pokemon gPlayerParty[6], gEnemyParty[6];
struct BattlePokemon gBattleMons[4];
u8 gBattlersCount = 2, gBattleBufferA[4][32];
u16 gBattlerPartyIndexes[4], gSpecialVar_Result;
u32 gBattleTypeFlags, rules;
int FlagGet(int x) { (void)x; return 1; }
bool8 WorldRules_Enabled(u32 rule) { return (rules & rule) != 0; }
int NativeLink_IsActive(void) { return 1; }
int CheckBagHasItem(u16 x, u16 y) { (void)x; (void)y; return 1; }
u8 GetBattlerPosition(u8 x) { return x; }
u8 GetBattlerSide(u8 x) { return x & 1; }
u8 GetNature(struct Pokemon *p) { (void)p; return 0; }
u16 ModifyStatByNature(u8 n, u16 s, u8 i) { (void)n; (void)i; return s; }
u32 GetMonData(struct Pokemon *p, int field) { return field == MON_DATA_SPECIES ? p->species : 0; }
int main(void) {
    gPlayerParty[0].species = gBattleMons[0].species = SPECIES_VENUSAUR;
    gBattleMons[0].item = ITEM_VENUSAURITE;
    gBattleMons[0].hp = 30;
    gBattleMons[0].level = 50;
    if (!MEGA_FEATURE_READY) {
        rules = 12;
        MegaGame_Reset();
        gBattleBufferA[0][0] = CONTROLLER_CHOOSEMOVE;
        gBattleBufferA[0][3] = MEGA_MOVE_CAN_SELECT_BIT;
        assert(!MegaGame_CanQueue(0));
        assert(!MegaGame_CanSelect(0));
        assert(!MegaGame_ToggleSelection(0));
        assert(!MegaGame_ChoiceBit(0));
        assert(!MegaGame_ValidateMoveChoice(0, MEGA_MOVE_CHOICE_BIT, 1));
        assert(!MegaGame_Queue(0));
        assert(!MegaGame_Apply(0));
        assert(!MegaGame_OnSwitchIn(0));
        assert(!MegaGame_ObserveForm(0, MEGA_FORM_VENUSAUR_MEGA, 0));
        assert(!MegaGame_ActiveForm(0));
        return 0;
    }
    for (rules = 0; rules <= 12; rules += 4) {
        int allowed = (rules & 8) && (!REQUIRES_MODERN || (rules & 4));
        MegaGame_Reset();
        assert(MegaGame_CanQueue(0) == allowed);
        /* The owner controller consumes the authority's eligibility bit,
         * not its potentially stale local battle-mon data. */
        gBattleBufferA[0][0] = CONTROLLER_CHOOSEMOVE;
        gBattleBufferA[0][3] = MegaGame_CanQueue(0) ? MEGA_MOVE_CAN_SELECT_BIT : 0;
        assert(MegaGame_CanSelect(0) == allowed);
        assert(MegaGame_ToggleSelection(0) == allowed);
        assert(MegaGame_ChoiceBit(0) == (allowed ? MEGA_MOVE_CHOICE_BIT : 0));
        assert(MegaGame_ValidateMoveChoice(0, MEGA_MOVE_CHOICE_BIT, 1) == allowed);
        assert(MegaGame_Queue(0) == allowed);
        assert(MegaGame_Apply(0) == allowed);
        assert(MegaGame_OnSwitchIn(0) == allowed);
        MegaGame_Reset();
        assert(MegaGame_ObserveForm(0, MEGA_FORM_VENUSAUR_MEGA, 0) == allowed);
        assert(MegaGame_ActiveForm(0) == (allowed ? MEGA_FORM_VENUSAUR_MEGA : 0));
    }
    /* Recheck at consumption: a previously eligible queued/observed form
     * must not bypass the policy when restored under a different mask. */
    MegaGame_Reset(); rules = 12;
    assert(MegaGame_Queue(0)); rules = 8;
    assert(MegaGame_Apply(0) == !REQUIRES_MODERN);
    MegaGame_Reset(); rules = 12;
    assert(MegaGame_ObserveForm(0, MEGA_FORM_VENUSAUR_MEGA, 0)); rules = 8;
    gBattleMons[0].attack = 1;
    assert(MegaGame_OnSwitchIn(0) == !REQUIRES_MODERN);
    MegaGame_Restore(0);
    assert((gBattleMons[0].attack == 1) == REQUIRES_MODERN);
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='mega-cross-rule-') as directory:
            root = Path(directory)
            (root / 'platform').mkdir()
            (root / 'constants').mkdir()
            (root / 'global.h').write_text('#ifndef GLOB\n#define GLOB\n' + headers['globalh'] + '#endif\n')
            (root / 'battle.h').write_text(headers['battleh'] + '\n#define BATTLE_TYPE_IS_MASTER 256\n')
            (root / 'pokemon.h').write_text(headers['pokemonh'])
            (root / 'battle_controllers.h').write_text('#define CONTROLLER_CHOOSEMOVE 10\nextern u8 gBattleBufferA[4][32];\n')
            (root / 'battle_anim.h').write_text('')
            (root / 'item.h').write_text('int CheckBagHasItem(u16,u16);\n')
            (root / 'event_data.h').write_text('int FlagGet(int);extern u16 gSpecialVar_Result;\n')
            (root / 'constants/flags.h').write_text('#define FLAG_BADGE07_GET 1\n')
            (root / 'platform/native_link.h').write_text('int NativeLink_IsActive(void);\n')
            (root / 'main.c').write_text(main)
            forms = (ROOT / 'src/platform/mega_forms.c').read_text()
            for variant, replacement in (
                ('legacy', 'TYPE_GRASS, TYPE_POISON, ABILITY_THICK_FAT'),
                ('technician', 'TYPE_GRASS, TYPE_POISON, ABILITY_TECHNICIAN'),
                ('adaptability', 'TYPE_GRASS, TYPE_POISON, ABILITY_ADAPTABILITY'),
                ('tough_claws', 'TYPE_GRASS, TYPE_POISON, ABILITY_TOUGH_CLAWS'),
                ('fairy_primary', 'TYPE_FAIRY, TYPE_POISON, ABILITY_THICK_FAT'),
                ('fairy_secondary', 'TYPE_GRASS, TYPE_FAIRY, ABILITY_THICK_FAT'),
            ):
                with self.subTest(variant=variant):
                    (root / 'forms.c').write_text(forms.replace('TYPE_GRASS, TYPE_POISON, ABILITY_THICK_FAT', replacement, 1))
                    executable = root / variant
                    command = ['cc', '-std=c99', '-DPORTABLE',
                               f'-DREQUIRES_MODERN={int(variant != "legacy")}',
                               '-Wall', '-Wextra', '-Werror', '-iquote', str(root),
                               '-iquote', str(ROOT / 'include'), str(root / 'forms.c'),
                               str(ROOT / 'src/platform/mega_battle.c'),
                               str(ROOT / 'src/platform/mega_game.c'), str(root / 'main.c'),
                               '-o', str(executable)]
                    result = subprocess.run(command, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(executable)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    unsupported = command[:-2] + ['-DMEGA_FEATURE_READY=0', '-o', str(executable) + '-unsupported']
                    result = subprocess.run(unsupported, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    result = subprocess.run([str(executable) + '-unsupported'], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
