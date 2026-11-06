"""Generate fail-closed, opt-in overlays for the pinned donor DexNav."""
from pathlib import Path
import sys

def once(source, old, new):
    if source.count(old)!=1:raise ValueError('pinned DexNav anchor changed: '+old[:70])
    return source.replace(old,new,1)

def patch_config(source):
    replacements={
        '#define DEXNAV_ENABLED                FALSE': '#define DEXNAV_ENABLED                TRUE',
        '#define DN_FLAG_SEARCHING             0': '#define DN_FLAG_SEARCHING             0x4003',
        '#define DN_FLAG_DEXNAV_GET            0': '#define DN_FLAG_DEXNAV_GET            0x4007',
        '#define DN_FLAG_DETECTOR_MODE         0': '#define DN_FLAG_DETECTOR_MODE         0x4006',
        '#define DN_VAR_SPECIES                0': '#define DN_VAR_SPECIES                0x40F7',
        '#define DN_VAR_STEP_COUNTER           0': '#define DN_VAR_STEP_COUNTER           0x40F8',
    }
    for old,new in replacements.items():source=once(source,old,new)
    return source

def patch_source(source):
    source=once(source,'#include "global.h"','#include "global.h"\nextern bool8 ExpansionDexNav_Enabled(void);')
    for declaration in ('bool32 TryStartDexNavSearch(void)', 'bool32 TryFindHiddenPokemon(void)',
                        'bool32 OnStep_DexNavSearch(void)'):
        source=once(source,declaration+'\n{',declaration+'\n{\n    if (!ExpansionDexNav_Enabled()) return FALSE;')
    source=once(source,'u32 CalculateDexNavShinyRolls(void)\n{','u32 CalculateDexNavShinyRolls(void)\n{\n    if (!ExpansionDexNav_Enabled()) return 0;')
    for declaration in ('void ResetDexNavSearch(void)', 'void IncrementDexNavChain(void)', 'void TryIncrementSpeciesSearchLevel()'):
        source=once(source,declaration+'\n{',declaration+'\n{\n    if (!ExpansionDexNav_Enabled()) return;')
    return source

if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('usage: patch_expansion_dexnav.py config|source INPUT OUTPUT')
    mode,path,dest=sys.argv[1:]
    text=Path(path).read_text()
    result=patch_config(text) if mode=='config' else patch_source(text) if mode=='source' else None
    if result is None:raise SystemExit('unknown DexNav overlay mode')
    Path(dest).write_text(result)
