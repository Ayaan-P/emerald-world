"""Replace an offline agent map while game is running and re-enter it."""
import argparse,hashlib,shlex,tempfile
from pathlib import Path
import driver
from world.xl_wilds import encode as encode_plain
from world.xl_wilds_cast import encode as encode_cast
from world.map_store import write_map

def run(binary,seed,out):
 binary,seed,out=map(lambda p:Path(p).resolve(),(binary,seed,out));out.mkdir(parents=True,exist_ok=True)
 rows=['#'*127]+['#'+'.'*125+'#']*125+['#'*127];proposal={'rows':rows,'spawn':[1,1],'exit':[125,125]}
 with tempfile.TemporaryDirectory(prefix='xl-refresh-') as t:
  root=Path(t);area=root/'area.bin';write_map(area,encode_plain(proposal))
  wrapper=root/'run';wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --generated-map '+shlex.quote(str(area))+' "$@"\n');wrapper.chmod(0o700)
  game=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=80000);before=hashlib.sha256(Path(game.save_path).read_bytes()).digest()
  try:
   driver.continue_game(game);driver.walk_to(game,6,11);driver.leave_map(game,'DOWN');driver.wait_until(game,lambda s:s.free);origin=(tuple(game.state.map),game.state.pos)
   def enter():
    game.tap('START',gap=30);game.tap('DOWN',times=5);game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90);driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Wilds' and s.free)
   def leave():
    game.tap('START',gap=30);game.tap('UP');game.tap('A',gap=60);game.tap('UP');game.tap('A',gap=90);driver.wait_until(game,lambda s:tuple(s.map)==origin[0] and s.free)
    if game.state.pos!=origin[1]:raise RuntimeError('returned to wrong position')
   enter()
   if (2,1) in game.state.objects:raise RuntimeError('initial world unexpectedly contains the replacement character')
   leave()
   write_map(area,encode_cast(proposal,[{'gfx':7,'x':2,'y':1,'text':'A new visitor!'}]),replace=True)
   enter()
   if (2,1) not in game.state.objects:raise RuntimeError('replacement character did not load on re-entry')
   game.press('RIGHT',1);game.wait(12);game.press('A',2);game.wait(20)
   if not game.state.script and not game.state.locked:raise RuntimeError('replacement character did not open dialogue')
   driver.finish_dialog(game);driver.wait_until(game,lambda s:s.free);leave()
  finally:code=game.finish()
  if code:raise RuntimeError(f'native client exited {code}')
  if hashlib.sha256(Path(game.save_path).read_bytes()).digest()!=before:raise RuntimeError('disposable save changed')
 print('PASS: running game reloaded an atomically replaced offline world and spoke to its new character without writing the save')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--seed-save',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.binary,a.seed_save,a.out)
