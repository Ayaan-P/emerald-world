"""Observe custom wildlife in a 63x63 native cave with a disposable save."""
import argparse
import hashlib
from pathlib import Path
import shlex
import tempfile
import driver
from world.large_cave import encode_wildlife


def run(binary,seed,out):
    binary,seed,out=map(lambda p:Path(p).resolve(),(binary,seed,out));out.mkdir(parents=True,exist_ok=True)
    rows=['#'*63]+['#'+'.'*61+'#']*61+['#'*63]
    blob=encode_wildlife({'rows':rows,'spawn':[1,1],'exit':[61,61]},'ice',100,[{'species':'MAGIKARP','level':5}]*12)
    with tempfile.TemporaryDirectory(prefix='large-wildlife-') as t:
        root=Path(t);cave=root/'cave.bin';cave.write_bytes(blob)
        wrapper=root/'run';wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --generated-map '+shlex.quote(str(cave))+' "$@"\n');wrapper.chmod(0o700)
        game=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=30000)
        before=hashlib.sha256(Path(game.save_path).read_bytes()).digest()
        try:
            driver.continue_game(game);driver.walk_to(game,6,11);driver.leave_map(game,'DOWN');driver.wait_until(game,lambda s:s.free)
            game.tap('START',gap=30);game.tap('DOWN',times=5);game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90)
            driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Cave' and s.free)
            for _ in range(150):
                driver.wait_until(game,lambda s:s.free or s.battle)
                if game.state.battle:break
                if game.state.pos not in ((1,1),(2,1)):raise RuntimeError(f'unexpected route: {game.state}')
                game.press('RIGHT' if game.state.pos==(1,1) else 'LEFT',16);game.wait(20)
            if not game.state.battle:raise RuntimeError('no custom large-cave encounter')
            driver.wait_until(game,lambda s:s.battle and s.battle_state and any(m['side']==1 for m in s.battle_state['battlers']),step=10,limit=3000)
            enemies=[m for m in game.state.battle_state['battlers'] if m['side']==1]
            if len(enemies)!=1 or (enemies[0]['species'],enemies[0]['level'])!=(129,5):raise RuntimeError(f'wrong large-cave encounter: {enemies}')
        finally:code=game.finish()
        if code:raise RuntimeError(f'native client exited {code}')
        if hashlib.sha256(Path(game.save_path).read_bytes()).digest()!=before:raise RuntimeError('disposable save changed')
    print('PASS: native 63x63 cave encountered custom level-5 Magikarp without writing the save')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--seed-save',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.binary,a.seed_save,a.out)
