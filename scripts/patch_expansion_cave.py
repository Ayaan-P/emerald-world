"""Prototype overlays only. Refuse unknown donor source or map-group layout."""
import json
from pathlib import Path

def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('donor anchor missing or ambiguous: ' + old[:65])
    return s.replace(old, new, 1)

def patch_overworld(source, groups):
    group_order = json.loads(groups)['group_order']
    if len(group_order) != 75:
        raise ValueError('reserved generated group conflicts with donor map catalog')
    source = once(source, '#include "overworld.h"', '#include "overworld.h"\nextern const struct MapHeader *ExpansionCave_Header(void);\nextern const struct MapLayout *ExpansionCave_ResolveLayout(const struct MapLayout *);')
    source = once(source, '    return gMapGroups[mapGroup][mapNum];',
                  '    if (mapGroup == 75 && mapNum == 0) return ExpansionCave_Header();\n    return gMapGroups[mapGroup][mapNum];')
    source = once(source, '    return gMapLayouts[mapLayoutId - 1];',
                  '    return ExpansionCave_ResolveLayout(gMapLayouts[mapLayoutId - 1]);')
    return source

def patch_save(source):
    source = once(source, '#include "save.h"', '#include "save.h"\nextern bool8 ExpansionCave_IsInside(void);')
    source = once(source, 'u8 HandleSavingData(u8 saveType)\n{', 'u8 HandleSavingData(u8 saveType)\n{\n    if (ExpansionCave_IsInside()) return SAVE_STATUS_ERROR;')
    source = once(source, 'u8 TrySavingData(u8 saveType)\n{', 'u8 TrySavingData(u8 saveType)\n{\n    if (ExpansionCave_IsInside()) { gSaveAttemptStatus = SAVE_STATUS_ERROR; return SAVE_STATUS_ERROR; }')
    for fn in ('LinkFullSave_Init', 'LinkFullSave_WriteSector', 'LinkFullSave_ReplaceLastSector', 'LinkFullSave_SetLastSectorSignature', 'WriteSaveBlock2', 'WriteSaveBlock1Sector'):
        source = once(source, 'bool8 ' + fn + '(void)\n{', 'bool8 ' + fn + '(void)\n{\n    if (ExpansionCave_IsInside()) return TRUE;')
    return source

if __name__ == '__main__':
    import sys
    if len(sys.argv) != 5:
        raise SystemExit('usage: patch_cave.py MODE INPUT GROUPS OUTPUT')
    mode, path, groups, dest = sys.argv[1:]
    source = Path(path).read_text()
    result = patch_overworld(source, Path(groups).read_text()) if mode == 'overworld' else patch_save(source) if mode == 'save' else None
    if result is None:
        raise SystemExit('unknown overlay mode')
    Path(dest).write_text(result)
