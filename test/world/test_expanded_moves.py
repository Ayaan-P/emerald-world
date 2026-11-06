"""Focused host execution of production expanded move data and type chart."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/rc4-modern-moves'

class ExpandedMoveTests(unittest.TestCase):
    def test_production_chart_and_move_effects(self):
        OUT.mkdir(parents=True, exist_ok=True)
        source = r'''
#include "gba/types.h"
#include "constants/global.h"
#include "constants/pokemon.h"
#include "constants/battle.h"
#include "battle_main.h"
#include "constants/moves.h"
#include "constants/battle_move_effects.h"
#include "platform/expanded_moves.h"
#include "platform/world_rules.h"
#include <assert.h>
u32 gBattleTypeFlags;
static int modern, linked;
bool8 WorldRules_Enabled(u32 rule) { assert(rule == WORLD_RULE_MODERN_SPLIT); return modern; }
int NativeLink_IsActive(void) { return linked; }
#include "src/data/battle_moves.h"
#define _(x) x
#include "src/data/text/move_names.h"
#include "src/data/text/move_descriptions.h"
static unsigned multiplier(unsigned atk, unsigned def) {
 const u8 *t = ExpandedMoves_TypeTable();
 for (unsigned i=0;t[i]!=TYPE_ENDTABLE;i+=3)
  if(t[i]==atk && t[i+1]==def) return t[i+2];
 return 10;
}
int main(void) {
 assert(MOVE_POUND==1 && MOVE_PSYCHO_BOOST==354);
 assert(MOVES_COUNT<512);
 modern=0;
 assert(multiplier(TYPE_GHOST,TYPE_STEEL)==5);
 assert(multiplier(TYPE_DRAGON,TYPE_FAIRY)==10);
 modern=1;
 assert(multiplier(TYPE_DRAGON,TYPE_FAIRY)==0);
 assert(multiplier(TYPE_FAIRY,TYPE_DRAGON)==20);
 assert(multiplier(TYPE_FAIRY,TYPE_FIGHTING)==20);
 assert(multiplier(TYPE_FAIRY,TYPE_DARK)==20);
 assert(multiplier(TYPE_FAIRY,TYPE_POISON)==5);
 assert(multiplier(TYPE_FAIRY,TYPE_FIRE)==5);
 assert(multiplier(TYPE_FAIRY,TYPE_STEEL)==5);
 assert(multiplier(TYPE_POISON,TYPE_FAIRY)==20);
 assert(multiplier(TYPE_STEEL,TYPE_FAIRY)==20);
 assert(multiplier(TYPE_FIGHTING,TYPE_FAIRY)==5);
 assert(multiplier(TYPE_BUG,TYPE_FAIRY)==5);
 assert(multiplier(TYPE_DARK,TYPE_FAIRY)==5);
 assert(multiplier(TYPE_GHOST,TYPE_STEEL)==10);
 assert(multiplier(TYPE_DARK,TYPE_STEEL)==10);
 assert(multiplier(TYPE_NORMAL,TYPE_GHOST)==0);
 assert(multiplier(TYPE_ELECTRIC,TYPE_GROUND)==0);
 gBattleTypeFlags=BATTLE_TYPE_LINK;
 assert(multiplier(TYPE_DRAGON,TYPE_FAIRY)==10);
 linked=1; assert(multiplier(TYPE_DRAGON,TYPE_FAIRY)==0);
 gBattleTypeFlags=BATTLE_TYPE_RECORDED;
 assert(multiplier(TYPE_DRAGON,TYPE_FAIRY)==10);
 gBattleTypeFlags=0;
 assert(ExpandedMoves_Category(MOVE_MOONBLAST)==EXPANDED_CATEGORY_SPECIAL);
 assert(ExpandedMoves_Category(MOVE_PLAY_ROUGH)==EXPANDED_CATEGORY_PHYSICAL);
 assert(ExpandedMoves_Category(MOVE_NASTY_PLOT)==EXPANDED_CATEGORY_STATUS);
 assert(ExpandedMoves_Category(MOVES_COUNT)==EXPANDED_CATEGORY_INVALID);
 assert(!ExpandedMoves_IsSupported(MOVES_COUNT));
 assert(ExpandedMoves_Category(MOVE_POUND)==EXPANDED_CATEGORY_INVALID);
 assert(ExpandedMoves_TypeTableSize()%3==0);
 modern=0; assert(ExpandedMoves_TypeTable()==gTypeEffectiveness);
 assert(ExpandedMoves_PlayableCount()==355);
 modern=1; assert(ExpandedMoves_PlayableCount()==MOVES_COUNT);
 assert(gBattleMoves[MOVE_MOONBLAST].effect==EFFECT_SPECIAL_ATTACK_DOWN_HIT);
 assert(gBattleMoves[MOVE_MOONBLAST].secondaryEffectChance==30);
 assert(gBattleMoves[MOVE_PLAY_ROUGH].effect==EFFECT_ATTACK_DOWN_HIT);
 assert(gBattleMoves[MOVE_PLAY_ROUGH].secondaryEffectChance==10);
 assert(gBattleMoves[MOVE_AURA_SPHERE].effect==EFFECT_ALWAYS_HIT);
 assert(gBattleMoves[MOVE_DAZZLING_GLEAM].target==MOVE_TARGET_BOTH);
 assert(gBattleMoves[MOVE_NASTY_PLOT].effect==EFFECT_SPECIAL_ATTACK_UP_2);
 assert(gBattleMoves[MOVE_BRAVE_BIRD].effect==EFFECT_DOUBLE_EDGE);
 assert(gBattleMoves[MOVE_DRACO_METEOR].effect==EFFECT_OVERHEAT);
 assert(gBattleMoves[MOVE_VACUUM_WAVE].priority==1);
 assert(gBattleMoves[MOVE_DRAIN_PUNCH].effect==EFFECT_ABSORB);
 assert(ExpandedMoves_Category(MOVE_DRAIN_PUNCH)==EXPANDED_CATEGORY_PHYSICAL);
 assert(gBattleMoves[MOVE_FORCE_PALM].secondaryEffectChance==30);
 assert(gBattleMoves[MOVE_CROSS_POISON].effect==EFFECT_POISON_TAIL);
 assert(gBattleMoves[MOVE_ROCK_POLISH].effect==EFFECT_SPEED_UP_2);
 for(unsigned m=355;m<MOVES_COUNT;m++) {
  assert(ExpandedMoves_IsSupported(m));
  assert(gBattleMoves[m].pp>0);
  assert(gMoveNames[m][0]);
  assert(gMoveDescriptionPointers[m-1] && gMoveDescriptionPointers[m-1][0]);
  struct LevelUpMove learned = {.move=m,.level=100};
  assert(learned.move==m && learned.level==100);
  assert(gBattleMoves[m].effect<NUM_BATTLE_MOVE_EFFECTS);
  assert(ExpandedMoves_Category(m)<=EXPANDED_CATEGORY_STATUS);
 }
 return 0;
}'''
        pokemon = (ROOT/'include/pokemon.h').read_text()
        struct = pokemon[pokemon.index('struct BattleMove\n'):]
        struct = struct[:struct.index('};')+2]
        learned = pokemon[pokemon.index('struct __attribute__((packed)) LevelUpMove'):]
        struct += '\n' + learned[:learned.index('};')+2]
        targets = '\n'.join(line for line in (ROOT/'include/battle.h').read_text().splitlines() if line.startswith('#define MOVE_TARGET'))
        source = source.replace('#include "src/data/battle_moves.h"',targets+'\n'+struct+'\n#include "src/data/battle_moves.h"')
        source = source.replace('#include "battle_main.h"','struct Sprite;\n#include "battle_main.h"')
        c = OUT / 'production_cases.c'
        c.write_text(source)
        # Native chart remains the original production table, not a test fixture.
        battle = (ROOT/'src/battle_main.c').read_text()
        chart = battle[battle.index('const u8 gTypeEffectiveness[336] ='):]
        chart = chart[:chart.index('};')+2]
        c.write_text(source + '\n' + chart + '\n')
        command = ['cc','-std=gnu99','-Wall','-Wextra','-Werror','-DPORTABLE','-DVER_64BIT','-Iinclude','-I.',str(c),
                   'src/platform/expanded_moves.c','-o',str(OUT/'production_cases')]
        built = subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(built.returncode,0,built.stderr)
        ran = subprocess.run([str(OUT/'production_cases')],cwd=ROOT,text=True,capture_output=True)
        self.assertEqual(ran.returncode,0,ran.stderr)

    def test_manifest_matches_every_playable_row_and_native_ids(self):
        import json
        import re
        coverage = json.loads((ROOT/'tools/expanded_moves/coverage.json').read_text())
        self.assertEqual(coverage['donor_pin'], 'bb3fd057061cdd7e6a9e79b76abb41924ee44ecc')
        supported = coverage['effect_supported']
        rows = (ROOT/'src/data/expanded_moves/battle_moves.h').read_text()
        names = re.findall(r'\[(MOVE_\w+)\]',rows)
        self.assertEqual(set(names),{row['name'] for row in supported})
        self.assertEqual(len(names),55)
        self.assertEqual([row['native_id'] for row in supported],list(range(355,410)))
        ids = (ROOT/'include/constants/moves.h').read_text()
        base = subprocess.check_output(['git','show','HEAD:include/constants/moves.h'],cwd=ROOT,text=True)
        native = lambda s: {n:int(v) for n,v in re.findall(r'^#define (MOVE_\w+) (\d+)$',s,re.M) if int(v)<=354}
        self.assertEqual(native(ids),native(base))
        defined = set(re.findall(r'^#define (MOVE_\w+)\b',ids,re.M))
        for name in coverage['recognized_but_not_ported']:
            self.assertNotIn(name,defined)
        for path in ['src/data/battle_moves.h','src/data/text/move_names.h','src/data/contest_moves.h']:
            before = subprocess.check_output(['git','show','HEAD:'+path],cwd=ROOT,text=True)
            current=(ROOT/path).read_text()
            current=re.sub(r'\n#ifdef PORTABLE\n#include "[^"\n]*expanded_moves/[^"\n]+"\n#endif','',current)
            self.assertEqual(current,before,path)
        scripts=(ROOT/'data/battle_scripts_1.s').read_text()
        constants=(ROOT/'include/constants/battle_move_effects.h').read_text()
        for row in supported:
            self.assertIn(row['effect'],constants)
            self.assertRegex(scripts,r'ptrvalue\s+BattleScript_\w+\s*/\*\s*'+row['effect']+r'\s*\*/')
        animations=(ROOT/'data/battle_anim_scripts.s').read_text()
        for row in supported:
            self.assertIn(row['animation_reuse']+':',animations)

if __name__ == '__main__':
    unittest.main()
