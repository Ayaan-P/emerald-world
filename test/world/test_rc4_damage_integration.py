"""Integration seam: compile real native damage with an observed ability boundary."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_move_split_damage import PRELUDE

ROOT = Path(__file__).resolve().parents[2]

class Rc4DamageIntegration(unittest.TestCase):
    def test_resolved_power_reaches_ability_hook_but_confusion_does_not(self):
        source = (ROOT/'src/pokemon.c').read_text()
        fn = 's32 CalculateBaseDamage(' + source.split('s32 CalculateBaseDamage(',1)[1].split('\n}',1)[0] + '\n}'
        fixture = (ROOT/'test/world/test_move_split_damage.py').read_text()
        stubs = re.search(r"stubs=r'''(.*?)'''",fixture,re.S).group(1)
        prefixes = ('ABILITY_','HOLD_EFFECT_','SPECIES_','FLAG_BADGE','ABILITYEFFECT_')
        names = sorted({n for n in re.findall(r'\b[A-Z][A-Z0-9_]+\b',fn) if n.startswith(prefixes) and n != 'ABILITY_ON_FIELD2'})
        defines = '\n'.join(f'#define {n} {100+i}' for i,n in enumerate(names))+'\n'
        boundary = r'''
static unsigned calls, seenAbility, seenMove, seenPower;
u32 ExpandedAbilities_ModifyBasePower(u8 ability,u16 move,u32 power) {
 calls++;seenAbility=ability;seenMove=move;seenPower=power;return power+10;
}
u8 ExpandedMoves_Category(u16 move) {(void)move;return 255;}
'''
        main = r'''
int main(void) {
 struct BattlePokemon a={0},d={0};
 a.attack=a.defense=a.spAttack=a.spDefense=100;a.level=50;a.hp=a.maxHP=100;a.ability=42;
 d.defense=d.spDefense=100;flag=1;gCurrentMove=MOVE_POUND;
 gBattleMoves[MOVE_POUND]=(struct BattleMove){40,TYPE_NORMAL,0,0};
 CalculateBaseDamage(&a,&d,MOVE_POUND,0,0,0,0,1);
 assert(calls==1 && seenAbility==42 && seenMove==MOVE_POUND && seenPower==40 && gBattleMovePower==50);
 calls=0;CalculateBaseDamage(&a,&d,MOVE_POUND,0,30,0,0,1);
 assert(calls==1 && seenPower==30 && gBattleMovePower==40);
 calls=0;gCurrentMove=MOVE_SOLAR_BEAM;
 CalculateBaseDamage(&a,&a,MOVE_POUND,0,40,0,0,0);
 assert(calls==0 && gBattleMovePower==40);
 return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='rc4-damage-integration-') as directory:
            root=Path(directory)
            for sub in ('constants','platform','gba'):(root/sub).mkdir()
            (root/'event_data.h').write_text('int FlagGet(int);\n')
            (root/'gba/types.h').write_text('/* Types provided by controlled fixture. */\n')
            (root/'constants/flags.h').write_text('#define FLAG_MODERN_MOVE_SPLIT 1\n')
            (root/'constants/moves.h').write_text((ROOT/'include/constants/moves.h').read_text())
            (root/'platform/native_link.h').write_text('int NativeLink_IsActive(void);\n')
            (root/'platform/world_rules.h').write_text('#define WORLD_RULE_MODERN_SPLIT 4\nint WorldRules_Enabled(unsigned);\n')
            (root/'platform/expanded_moves.h').write_text((ROOT/'include/platform/expanded_moves.h').read_text())
            (root/'battle_move_split.h').write_text((ROOT/'include/battle_move_split.h').read_text())
            c=root/'damage.c';exe=root/'damage'
            c.write_text(PRELUDE+'#include "constants/moves.h"\n'+defines+stubs+boundary+fn+main)
            result=subprocess.run(['cc','-std=c99','-DPORTABLE','-I',str(root),str(c),'-o',str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()
