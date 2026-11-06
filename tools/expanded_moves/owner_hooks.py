"""Produce owner handoff hunks without editing another worker's files."""
from pathlib import Path
import difflib
ROOT=Path(__file__).resolve().parents[2]
patches=[]
def change(path, pairs):
    before=(ROOT/path).read_text(); after=before
    for old,new in pairs:
        if old not in after:
            if new in after: continue
            raise ValueError((path,old))
        after=after.replace(old,new,1)
    patches.extend(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+path,tofile='b/'+path))

change('include/battle_move_split.h',[
 ('#include "platform/world_rules.h"','#include "platform/world_rules.h"\n#include "platform/expanded_moves.h"'),
 ('sModernMoveCategory[move] == MOVE_SPLIT_PHYSICAL','(move >= EXPANDED_MOVES_START ? ExpandedMoves_Category(move) : sModernMoveCategory[move]) == MOVE_SPLIT_PHYSICAL'),
 ('sModernMoveCategory[move] == MOVE_SPLIT_SPECIAL','(move >= EXPANDED_MOVES_START ? ExpandedMoves_Category(move) : sModernMoveCategory[move]) == MOVE_SPLIT_SPECIAL'),
])
change('src/battle_script_commands.c',[
 ('if (gCurrentMove >= MOVES_COUNT)','#ifdef PORTABLE\n        if (gCurrentMove >= ExpandedMoves_PlayableCount())\n#else\n        if (gCurrentMove >= MOVES_COUNT)\n#endif'),
 ('((NUMBER_OF_MON_TYPES - 3) * typeBits) / 63 + 1','((TYPE_DARK - 2) * typeBits) / 63 + 1'),
 ('while (((i = Random() % 128) > sizeof(gTypeEffectiveness) / 3));','#ifdef PORTABLE\n            if (ExpandedMoves_UseModernTypes())\n            {\n                do { i = Random() % 128; } while (i >= ExpandedMoves_TypeTableSize() / 3);\n            }\n            else\n#endif\n            while (((i = Random() % 128) > sizeof(gTypeEffectiveness) / 3));'),
 ('for (j = 0, rands = 0; rands < sizeof(gTypeEffectiveness); j += 3, rands += 3)','#ifdef PORTABLE\n        for (j = 0, rands = 0; rands < ExpandedMoves_TypeTableSize(); j += 3, rands += 3)\n#else\n        for (j = 0, rands = 0; rands < sizeof(gTypeEffectiveness); j += 3, rands += 3)\n#endif'),
 # Keep native quirks when rule off. Modern fallback must index its own row.
 ('&& !IS_BATTLER_OF_TYPE(gBattlerAttacker, TYPE_EFFECT_DEF_TYPE(i)))\n                {','&& !IS_BATTLER_OF_TYPE(gBattlerAttacker, TYPE_EFFECT_DEF_TYPE(\n#ifdef PORTABLE\n                    ExpandedMoves_UseModernTypes() ? j :\n#endif\n                    i)))\n                {'),
])
change('src/battle_main.c',[
 ('    [TYPE_DARK] = _("DARK"),','    [TYPE_DARK] = _("DARK"),\n#ifdef PORTABLE\n    [TYPE_FAIRY] = _("FAIRY"),\n#endif'),
])
change('src/graphics.c',[
 ('const u32 gMoveTypes_Gfx[] = INCGFX_U32("graphics/types/move_types.4bpp", ".lz");','#ifdef PORTABLE\nconst u32 gMoveTypes_Gfx[] = INCGFX_U32("graphics/types/move_types_expanded.4bpp", ".lz");\n#else\nconst u32 gMoveTypes_Gfx[] = INCGFX_U32("graphics/types/move_types.4bpp", ".lz");\n#endif'),
])
change('src/pokemon_summary_screen.c',[
 ('static const union AnimCmd sSpriteAnim_CategoryCool[] = {','#ifdef PORTABLE\nstatic const union AnimCmd sSpriteAnim_TypeFairy[] = {\n    ANIMCMD_FRAME(TYPE_FAIRY * 8, 0, FALSE, FALSE),\n    ANIMCMD_END\n};\n#endif\nstatic const union AnimCmd sSpriteAnim_CategoryCool[] = {'),
 ('    sSpriteAnim_TypeDark,','    sSpriteAnim_TypeDark,\n#ifdef PORTABLE\n    sSpriteAnim_TypeFairy,\n#endif'),
 ('    [TYPE_DARK] = 13,','    [TYPE_DARK] = 13,\n#ifdef PORTABLE\n    [TYPE_FAIRY] = 14,\n#endif'),
])
change('src/dexnav.c',[
 ('    [TYPE_DARK] = TYPE_ICON_PAL_NUM_0,','    [TYPE_DARK] = TYPE_ICON_PAL_NUM_0,\n#ifdef PORTABLE\n    [TYPE_FAIRY] = TYPE_ICON_PAL_NUM_1,\n#endif'),
])
change('src/platform/dexnav_native.c',[
 ('TYPE_ANIM(12); TYPE_ANIM(13); TYPE_ANIM(14); TYPE_ANIM(15); TYPE_ANIM(16); TYPE_ANIM(17);','TYPE_ANIM(12); TYPE_ANIM(13); TYPE_ANIM(14); TYPE_ANIM(15); TYPE_ANIM(16); TYPE_ANIM(17); TYPE_ANIM(18);'),
 ('    sType9, sType10, sType11, sType12, sType13, sType14, sType15, sType16, sType17,','    sType9, sType10, sType11, sType12, sType13, sType14, sType15, sType16, sType17, sType18,'),
])
change('src/pokedex.c',[
 ('    {gText_DexEmptyString, gTypeNames[TYPE_DARK]},','    {gText_DexEmptyString, gTypeNames[TYPE_DARK]},\n#ifdef PORTABLE\n    {gText_DexEmptyString, gTypeNames[TYPE_FAIRY]},\n#endif'),
 ('    TYPE_DARK,\n};','    TYPE_DARK,\n#ifdef PORTABLE\n    TYPE_FAIRY,\n#endif\n};'),
])
change('src/data/union_room.h',[
 ('    { sText_Exit,                NUMBER_OF_MON_TYPES }','#ifdef PORTABLE\n    { gTypeNames[TYPE_FAIRY],    TYPE_FAIRY          },\n#endif\n    { sText_Exit,                NUMBER_OF_MON_TYPES }'),
])
change('src/battle_message.c',[
 ('    [TYPE_DARK]     = _("a DARK move")','    [TYPE_DARK]     = _("a DARK move"),\n#ifdef PORTABLE\n    [TYPE_FAIRY]    = _("a FAIRY move"),\n#endif'),
])
out=ROOT/'build/rc4-modern-moves/owner-hooks.patch'
out.write_text(''.join(patches))
print(out)
