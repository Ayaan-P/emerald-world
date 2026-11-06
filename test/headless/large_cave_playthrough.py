"""Enter a 63x63 cave and walk beyond the old boundary in a disposable save."""
import argparse
import hashlib
from pathlib import Path
import shlex
import tempfile
import driver
from world.large_cave import encode


def flee(game):
    for _ in range(16):
        if not game.state.battle:
            break
        game.tap('B',times=6,gap=12)
        if not game.state.battle:
            break
        game.tap('DOWN');game.tap('RIGHT');game.tap('A',gap=60)
    if game.state.battle:
        raise RuntimeError('could not flee encounter in large cave')
    driver.wait_until(game,lambda state:state.free)


def run(binary,seed,out):
    binary,seed,out=map(lambda p:Path(p).resolve(),(binary,seed,out));out.mkdir(parents=True,exist_ok=True)
    rows=['#'*63]+['#'+'.'*61+'#']*61+['#'*63]
    cave_data=encode({'rows':rows,'spawn':[1,1],'exit':[61,61]})
    with tempfile.TemporaryDirectory(prefix='large-cave-') as t:
        root=Path(t);cave=root/'cave.bin';cave.write_bytes(cave_data)
        wrapper=root/'run';wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --generated-map '+shlex.quote(str(cave))+' "$@"\n');wrapper.chmod(0o700)
        game=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=50000)
        before=hashlib.sha256(Path(game.save_path).read_bytes()).digest()
        try:
            driver.continue_game(game);driver.walk_to(game,6,11);driver.leave_map(game,'DOWN');driver.wait_until(game,lambda s:s.free)
            origin=(tuple(game.state.map),game.state.pos)
            game.tap('START',gap=30);game.tap('DOWN',times=5);game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90)
            driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Cave' and s.free)
            for _ in range(200):
                if game.state.battle:flee(game)
                driver.wait_until(game,lambda s:s.free or s.battle)
                if game.state.battle:continue
                if game.state.pos[0]>=35:break
                if game.state.pos[1]!=1:raise RuntimeError(f'unexpected large-cave route: {game.state}')
                game.press('RIGHT',16);game.wait(15)
            if game.state.pos[0]<35:raise RuntimeError(f'failed to walk past old map boundary: {game.state}')
            if game.state.battle:flee(game)
            driver.wait_until(game,lambda s:s.free)
            game.tap('START',gap=30);game.tap('UP');game.tap('A',gap=60);game.tap('UP');game.tap('A',gap=90)
            driver.wait_until(game,lambda s:tuple(s.map)==origin[0] and s.free)
            if game.state.pos!=origin[1]:raise RuntimeError('large cave returned to wrong position')
        finally:code=game.finish()
        if code:raise RuntimeError(f'native client exited {code}')
        if hashlib.sha256(Path(game.save_path).read_bytes()).digest()!=before:raise RuntimeError('disposable save changed')
    print('PASS: walked beyond 31 tiles in a native 63x63 cave and returned without writing the save')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--seed-save',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.binary,a.seed_save,a.out)
