import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('patch_cave', Path(__file__).resolve().parents[2] / 'scripts/patch_expansion_cave.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CaveOverlay(unittest.TestCase):
    def test_reservation_fails_closed_when_catalog_changes(self):
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            mod.patch_overworld('', json.dumps({'group_order': list(range(76))}))
    def test_overworld_anchor_requires_single_matches(self):
        source = '#include "overworld.h"\n    return gMapGroups[mapGroup][mapNum];\n    return gMapLayouts[mapLayoutId - 1];'
        groups = json.dumps({'group_order': list(range(75))})
        result = mod.patch_overworld(source, groups)
        self.assertIn('mapGroup == 75 && mapNum == 0', result)
        self.assertIn('ExpansionCave_ResolveLayout', result)
        with self.assertRaises(ValueError): mod.patch_overworld(source + '\n' + source, groups)
    def test_all_save_entrypoints_are_guarded(self):
        source = '#include "save.h"\n' + '\n'.join([
            'u8 HandleSavingData(u8 saveType)\n{', 'u8 TrySavingData(u8 saveType)\n{',
            'bool8 LinkFullSave_Init(void)\n{', 'bool8 LinkFullSave_WriteSector(void)\n{',
            'bool8 LinkFullSave_ReplaceLastSector(void)\n{', 'bool8 LinkFullSave_SetLastSectorSignature(void)\n{', 'bool8 WriteSaveBlock2(void)\n{',
            'bool8 WriteSaveBlock1Sector(void)\n{'])
        patched = mod.patch_save(source)
        self.assertEqual(patched.count('if (ExpansionCave_IsInside())'), 8)
        with self.assertRaises(ValueError): mod.patch_save(source.replace('bool8 WriteSaveBlock2(void)', 'bool8 renamed(void)'))
