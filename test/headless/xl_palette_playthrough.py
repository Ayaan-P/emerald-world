"""Enter a 127x127 outdoor area and walk beyond the old boundary in a disposable save."""
import argparse
import hashlib
from pathlib import Path
import shlex
import tempfile
import driver
from world.xl_wilds_palette import encode


def check_green_frame(directory,after_frame):
    shots=[]
    for path in Path(directory).glob('frame_*.ppm'):
        try:frame=int(path.stem.split('_',1)[1])
        except (ValueError,IndexError):continue
        if frame>=after_frame:shots.append((frame,path))
    if not shots:raise RuntimeError('no outdoor frame captured')
    data=max(shots)[1].read_bytes();header=b'P6\n240 160\n255\n'
    if not data.startswith(header) or len(data)!=len(header)+240*160*3:raise RuntimeError('invalid outdoor frame')
    pixels=data[len(header):]
    green=sum(1 for i in range(0,len(pixels),3) if pixels[i+1]>pixels[i]+5 and pixels[i+1]>pixels[i+2]+5 and pixels[i+1]>60)
    if green<200:raise RuntimeError(f'outdoor frame did not contain enough green pixels: {green}')


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
    rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127]
    cave_data=encode({'rows':rows,'spawn':[1,1],'exit':[125,125]},[{'x':10,'y':1,'width':30,'height':1,'terrain':'tall_grass'},{'x':80,'y':20,'width':8,'height':8,'terrain':'water'}])
    with tempfile.TemporaryDirectory(prefix='xl-wilds-') as t:
        root=Path(t);cave=root/'cave.bin';cave.write_bytes(cave_data)
        wrapper=root/'run';wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --generated-map '+shlex.quote(str(cave))+' "$@"\n');wrapper.chmod(0o700)
        game=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=50000,shot_every=30)
        before=hashlib.sha256(Path(game.save_path).read_bytes()).digest()
        try:
            driver.continue_game(game);driver.walk_to(game,6,11);driver.leave_map(game,'DOWN');driver.wait_until(game,lambda s:s.free)
            origin=(tuple(game.state.map),game.state.pos)
            game.tap('START',gap=30);game.tap('DOWN',times=5);game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90)
            driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Wilds' and s.free)
            entered_frame=game.state.frame;game.wait(90)
            check_green_frame(out,entered_frame)
            for _ in range(300):
                if game.state.battle:flee(game)
                driver.wait_until(game,lambda s:s.free or s.battle)
                if game.state.battle:continue
                if game.state.pos[0]>=75:break
                if game.state.pos[1]!=1:raise RuntimeError(f'unexpected generated-wilds route: {game.state}')
                game.press('RIGHT',16);game.wait(15)
            if game.state.pos[0]<75:raise RuntimeError(f'failed to walk past 63-tile boundary: {game.state}')
            if game.state.battle:flee(game)
            driver.wait_until(game,lambda s:s.free)
            game.tap('START',gap=30);game.tap('UP');game.tap('A',gap=60);game.tap('UP');game.tap('A',gap=90)
            driver.wait_until(game,lambda s:tuple(s.map)==origin[0] and s.free)
            if game.state.pos!=origin[1]:raise RuntimeError('generated wilds returned to wrong position')
        finally:code=game.finish()
        if code:raise RuntimeError(f'native client exited {code}')
        if hashlib.sha256(Path(game.save_path).read_bytes()).digest()!=before:raise RuntimeError('disposable save changed')
    print('PASS: walked beyond 63 tiles in an agent-painted 127x127 outdoor area and returned without writing the save')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--seed-save',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.binary,a.seed_save,a.out)
