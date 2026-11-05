"""Contract checks only; these do not run or verify a native game."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('generated_cave_playthrough',ROOT/'test/headless/generated_cave_playthrough.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class State:
    free=True
    battle=False
    party=[{'species': 252}]
    def __init__(self,name,map_id,pos): self.map_name=name;self.map=map_id;self.pos=pos

class FakeGame:
    last=None
    def __init__(self,binary,out_dir,save,max_frames):
        self.save_path=str(Path(out_dir)/'game.sav');shutil.copyfile(save,self.save_path)
        self.state=State('LittlerootTown_ProfessorBirchsLab',(1,4),(6,5));self.actions=[];self.a=0
        FakeGame.last=self
    def tap(self,button,times=1,**kwargs):
        self.actions.append((button,times))
        if button=='A':
            self.a+=1
            if self.a==2:self.state=State('GeneratedWorld_Cave',(32,0),(1,1))
            if self.a==4:self.state=State('LittlerootTown',(0,9),(7,16))
    def press(self,button,frames):
        self.actions.append((button,frames))
        if button=='RIGHT': self.state.pos=(2,1)
    def wait(self,frames):pass
    def finish(self):return 0

class CaveHarnessContract(unittest.TestCase):
    def test_script_attempts_entry_walk_and_return_without_mutating_save(self):
        def leave(game,direction): game.state=State('LittlerootTown',(0,9),(7,16))
        def wait(game,condition,*args,**kwargs):
            if not condition(game.state):raise AssertionError('unexpected test state')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);seed=root/'seed';seed.write_bytes(b'disposable');out=root/'out'
            with patch.object(module.driver,'Game',FakeGame),patch.object(module.driver,'continue_game'), \
                 patch.object(module.driver,'walk_to'),patch.object(module.driver,'leave_map',leave), \
                 patch.object(module.driver,'wait_until',wait),patch('builtins.print'):
                module.run('/bin/true',seed,out)
            self.assertIn(('RIGHT',16),FakeGame.last.actions)
            self.assertEqual(FakeGame.last.a,4)
            self.assertEqual((out/'game.sav').read_bytes(),b'disposable')

    def test_encounter_mode_requires_a_visible_expected_opponent(self):
        class EncounterGame(FakeGame):
            def tap(self,button,times=1,**kwargs):
                if self.state.battle and button=='A':
                    self.actions.append((button,times));self.state.battle=False
                else:
                    super().tap(button,times,**kwargs)
            def press(self,button,frames):
                super().press(button,frames)
                if len([a for a in self.actions if a[0] in ('LEFT','RIGHT')]) >= 2:
                    self.state.battle=True
                    self.state.battle_state={'battlers':[{'side':1,'species':41,'level':7}]}
        def leave(game,direction): game.state=State('LittlerootTown',(0,9),(7,16))
        def wait(game,condition,*args,**kwargs):
            if not condition(game.state):raise AssertionError('unexpected test state')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);seed=root/'seed';seed.write_bytes(b'disposable');out=root/'out'
            with patch.object(module.driver,'Game',EncounterGame),patch.object(module.driver,'continue_game'), \
                 patch.object(module.driver,'walk_to'),patch.object(module.driver,'leave_map',leave), \
                 patch.object(module.driver,'wait_until',wait),patch('builtins.print'):
                module.run('/bin/true',seed,out,encounter=True)
            self.assertEqual(FakeGame.last.a,4)
            self.assertIn(('DOWN',1), FakeGame.last.actions)
            self.assertIn(('RIGHT',1), FakeGame.last.actions)
            self.assertEqual((out/'game.sav').read_bytes(),b'disposable')

    def test_offline_profile_observes_matching_meteor_encounter(self):
        class MeteorGame(FakeGame):
            def press(self,button,frames):
                super().press(button,frames)
                if len([a for a in self.actions if a[0] in ('LEFT','RIGHT')]) >= 2:
                    self.state.battle=True
                    self.state.battle_state={'battlers':[{'side':1,'species':41,'level':16}]}
        def leave(game,direction): game.state=State('LittlerootTown',(0,9),(7,16))
        def wait(game,condition,*args,**kwargs):
            if not condition(game.state):raise AssertionError('unexpected test state')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);seed=root/'seed';seed.write_bytes(b'disposable');out=root/'out'
            with patch.object(module.driver,'Game',MeteorGame),patch.object(module.driver,'continue_game'), \
                 patch.object(module.driver,'walk_to'),patch.object(module.driver,'leave_map',leave), \
                 patch.object(module.driver,'wait_until',wait),patch('builtins.print'), \
                 patch.object(module,'encode',wraps=module.encode) as encode:
                module.run('/bin/true',seed,out,encounter=True,profile='meteor',observe_only=True)
            self.assertEqual(encode.call_args.kwargs['encounter_profile'],'meteor')
            self.assertEqual(FakeGame.last.a,2)
            self.assertEqual((out/'game.sav').read_bytes(),b'disposable')

    def test_native_startup_failure_exposes_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);seed=root/'seed';seed.write_bytes(b'disposable');out=root/'out'
            def fail(binary,out_dir,save,max_frames):
                (Path(out_dir)/'stderr.txt').write_text('native diagnostic')
                raise RuntimeError('exited')
            with patch.object(module.driver,'Game',side_effect=fail):
                with self.assertRaisesRegex(RuntimeError,'native diagnostic'):
                    module.run('/bin/true',seed,out)

if __name__=='__main__':unittest.main()
