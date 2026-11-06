from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/'port/resolved'
class InitialResolutions(unittest.TestCase):
 def read(self,name):
  text=(ROOT/name).read_text();self.assertNotIn('<<<<<<<',text);self.assertNotIn('>>>>>>>',text);return text
 def test_world_and_dexnav_menu_fit(self):
  s=self.read('src/start_menu.c');m=self.read('src/menu.c')
  self.assertIn('sCurrentStartMenuActions[10]',s)
  self.assertIn('[MENU_ACTION_DEXNAV]',s);self.assertIn('[MENU_ACTION_WORLD]',s)
  self.assertIn('sNumStartMenuActions >= 10 ? 13',s);self.assertIn('numActions >= 9 ? 18',m)
 def test_generated_map_hooks_and_donor_warps(self):
  s=self.read('src/overworld.c');f=self.read('src/field_control_avatar.c')
  self.assertIn('GetMapLayout(u16 mapLayoutId)',s);self.assertIn('GeneratedMap_ResolveLayout(gMapLayouts[mapLayoutId - 1])',s)
  self.assertIn('GeneratedMap_Leave()',f);self.assertIn('StorePlayerStateAndSetupWarp(position, warpEventId)',f)
 def test_donor_save_flush_and_world_guard(self):
  s=self.read('src/save.c');self.assertIn('GeneratedMap_IsInside()',s);self.assertIn('frame_flush_save()',s);self.assertNotIn('Platform_StoreSaveFile()',s)
 def test_world_virtual_cable_alias(self):
  s=self.read('src/link.c');self.assertIn('NativeLink_Main1(',s);self.assertIn('GetBlockReceivedSize(u8 who)',s)
 def test_script_special_order_and_unique_dexnav(self):
  e=self.read('data/event_scripts.s');sp=self.read('data/specials.inc')
  self.assertEqual(e.count('.include "data/scripts/dexnav.inc"'),1);self.assertIn('WorldActivity_EventScript_StoragePC::',e);self.assertIn('def_special GeneratedMap_RunEvent',sp)
 def test_bulk_module_provenance_matches_carried_sources(self):
  import hashlib,json
  data=json.loads((ROOT.parent/'world-port-provenance.json').read_text())
  self.assertEqual(len(data['files']),37)
  for item in data['files']:
   self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['merged_sha256'],item['path'])

 def test_carried_engine_hooks(self):
  import hashlib,json
  self.assertIn('WorldBridge_PrepareSave()',self.read('src/fieldmap.c'))
  self.assertIn('ScriptMenu_DrawRepelChoice(',self.read('src/script_menu.c'))
  self.assertIn('GetTaskCount(void)',self.read('src/task.c'))
  data=json.loads((ROOT.parent/'prior-hooks-provenance.json').read_text())
  for item in data['files']:
   self.assertEqual(hashlib.sha256((ROOT/item['path']).read_bytes()).hexdigest(),item['merged_sha256'])

 def test_additional_carried_hooks(self):
  battle=self.read('src/battle_setup.c');objects=self.read('src/event_object_movement.c');fly=self.read('src/field_effect.c')
  self.assertEqual(battle.count('WorldActivity_TryCoopTrainerBattle()'),2)
  self.assertEqual(self.read('src/field_control_avatar.c').count('if (OnStep_DexNavSearch())'),1)
  self.assertIn('WorldBridge_IsRemoteObject(curObject)',objects)
  self.assertIn('WorldTravel_ArrivalFallback()',fly)

 def test_use_expansion_field_mechanics(self):
  field=self.read('src/field_control_avatar.c');dex=self.read('src/dexnav.c');make=self.read('Makefile.native')
  self.assertNotIn('DexNavNative_HandleInput()',field)
  self.assertIn('TryStartDexNavSearch()',field)
  self.assertIn('DexNav_OpenFromField(void)',dex)
  self.assertIn('$(C_SUBDIR)/platform/repeat_repel.c',make)

 def test_carried_sprite_hooks(self):
  s=self.read('src/sprite.c')
  self.assertIn('NativeSpriteTileClone(',s);self.assertIn('NativeSpriteTileScope(',s)
  self.assertIn('#elif defined(PORTABLE) && WORLD_EXTENDED_SPRITES',s)

 def test_renderer_flags_reach_platform_library(self):
  flags=(ROOT.parent/'expansion-world.mk').read_text()
  make=self.read('platform/Makefile');ppu=self.read('platform/ppu_obj.c');memory=self.read('platform/gba_memmap.h');defs=self.read('include/gba/defines.h')
  self.assertIn('export WORLD_NATIVE_CPPFLAGS := -DWORLD_NATIVE_OAM=1 -DWORLD_NATIVE_TILEBANK=1 -DWORLD_NATIVE_EWRAM=1',flags)
  self.assertIn('CFLAGS_ALL += $(WORLD_NATIVE_CPPFLAGS)',make)
  self.assertIn('world_oam_order(',ppu);self.assertIn('0x00020000',memory);self.assertIn('OAM_ENTRY_COUNT 192',defs)

 def test_native_ewram_is_consistently_expanded_and_bounded(self):
  flags=(ROOT.parent/'expansion-world.mk').read_text(); mem=self.read('platform/gba_memmap.h'); defs=self.read('include/gba/defines.h'); link=self.read('platform/gba_regions.ld')
  self.assertIn('-DWORLD_NATIVE_EWRAM=1',flags);self.assertIn('gba_native_ewram_size=0x80000',flags)
  self.assertIn('GBA_EWRAM_SIZE UINT32_C(0x00080000)',mem);self.assertIn('EWRAM_START + 0x80000',defs)
  self.assertIn('ASSERT(gba_ewram_data_end <= gba_linked_ewram_start + gba_native_ewram_size',link)

 def test_expanded_movement_storage_matches_object_capacity(self):
  s=self.read('src/script_movement.c')
  self.assertIn('sWorldMovementObjectIds[OBJECT_EVENTS_COUNT]',s)
  self.assertIn('_Static_assert(OBJECT_EVENTS_COUNT <= 64',s)
  self.assertIn('sWorldMovementFinished |= (1ULL << moveScrId)',s)
  self.assertIn('sWorldMovementObjectIds[i] = 0xFF',s)
  self.assertIn('pObjEventId = sWorldMovementObjectIds',s)

 def test_coop_battle_source_is_carried_but_not_certified(self):
  import hashlib,json
  s=self.read('src/battle_controllers.c');data=json.loads((ROOT.parent/'battle-controller-provenance.json').read_text())
  self.assertEqual(hashlib.sha256((ROOT/'src/battle_controllers.c').read_bytes()).hexdigest(),data['candidate_sha256'])
  for symbol in ('WorldCoop_InitControllers()', 'NativeBattleHeaderValid(', 'NativeBattleSourceValid(', 'NativeBattleReplyValid(', 'WorldCoop_ReceiveCompletion(', 'WorldCoop_ObserveController(', 'WorldCoop_ObserveMonData('):
   self.assertIn(symbol,s)
  self.assertNotIn('gBattleBufferA',s);self.assertNotIn('gBattleBufferB',s);self.assertNotIn('gActiveBattler',s)

 def test_reviewed_start_menu_fixture_only(self):
  fixture=self.read('tests/smoke/expected/screenshots.md5')
  self.assertIn('72868519c964cc9a90990c55d19d2f2e  24_start_menu.ppm',fixture)
  self.assertEqual(len(fixture.splitlines()),26)

 def test_coop_player_controller_hooks_present(self):
  s=self.read('src/battle_controller_player.c')
  for x in ('WorldCoop_SelectBattleItem(', 'WorldCoop_SetMenuConfusion(', 'WorldCoop_ApplyRosterRequest(', 'WorldCoop_ApplyRosterMirror(', 'WorldCoop_ConsumeMedicine(', 'WorldCoop_RecordCatchEvent(', 'WorldCoop_RecordDefeat('):
   self.assertIn(x,s)
  self.assertNotIn('gActiveBattler',s)

 def test_coop_battle_entry_wiring_exists(self):
  s=self.read('src/battle_main.c')
  self.assertIn('if (WorldCoop_IsBattle())\n    {\n        CB2_InitBattleInternal();',s)
  self.assertIn('SetMainCallback2(CB2_HandleStartCoopBattle)',s)
  self.assertIn('gBattleEnvironment = WorldCoop_Environment()',s)
  self.assertIn('WorldCoop_Abort()',s)

 def test_coop_intro_skips_absent_opponent(self):
  s=self.read('src/battle_main.c')
  self.assertGreaterEqual(s.count('WorldCoop_IsBattle() && (gAbsentBattlerFlags & (1u << battler))'),2)
  self.assertIn('WorldCoop_FullPartyMenuActive()',s)

 def test_coop_switch_and_trainer_flee_hooks_present(self):
  s=self.read('src/battle_main.c')
  self.assertIn('WorldCoop_BeginRosterAction(battler',s)
  self.assertIn('WorldCoop_AdvanceRosterAction(battler)',s)
  self.assertIn('|| WorldCoop_IsBattle()',s)

 def test_coop_escape_uses_wild_battle_path(self):
  s=self.read('src/battle_util.c');m=self.read('src/battle_main.c')
  self.assertIn('&& !WorldCoop_IsBattle()',s)
  self.assertIn('&& !WorldCoop_IsBattle()',m)

 def test_coop_opponent_intro_hooks_present(self):
  s=self.read('src/battle_controller_link_opponent.c')
  self.assertIn('WorldCoop_IsBattle() && (gAbsentBattlerFlags',s)
  self.assertIn('GetTrainerPicFromId(TRAINER_BATTLE_PARAM.opponentA)',s)

 def test_coop_completion_and_private_reward_wiring(self):
  main=self.read('src/battle_main.c');player=self.read('src/battle_controller_player.c');script=self.read('data/battle_scripts_2.s')
  for x in ('WorldCoop_CompletionCommitted()', 'WorldCoop_BeginPrivateRewards(void)', 'WorldCoop_PreparePrivateRewards()', 'WorldCoop_NextReward()'):
   self.assertIn(x,main)
  self.assertIn('WorldCoop_ReadyForPrivateRewards()',player)
  self.assertIn('BattleScript_CoopPrivateCatch::',script)

 def test_coop_defeat_is_recorded_before_private_exp(self):
  s=self.read('src/battle_script_commands.c')
  self.assertIn('WorldCoop_EmitDefeat()',s)
  self.assertIn('gBattlescriptCurrInstr = cmd->nextInstr',s)

 def test_save_object_copy_respects_persistent_slots(self):
  s=self.read('src/load_save.c')
  self.assertGreaterEqual(s.count('i < SAVED_OBJECT_EVENTS_COUNT'),2)
  self.assertIn('gObjectEvents[i] = (struct ObjectEvent){0}',s)
  self.assertIn('WorldBridge_PrepareSave()',s)
