"""Two real candidate games with a file relay and in-memory link broker.

No socket is opened. Test-only hooks pre-consent, enter a shared wild battle
and bypass the World UI. This does not test real transport or shared-world UI.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

binary=Path(sys.argv[1]).resolve(strict=True)
save=Path(sys.argv[2]).resolve(strict=True)
root=Path(sys.argv[3]).resolve();root.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from world.link_protocol import LinkProtocol

broker=LinkProtocol(id_factory=lambda: 777)
presence={'Alice':(0,9,5,5,1,0,1),'Bob':(0,9,6,5,1,0,1)}
offer=broker.process('Alice',b'T OFFER Bob',presence)
line=next(line for recipient,line in offer if recipient=='Bob')
tag=line.split()[2]
broker.process('Bob',f'T ACCEPT {tag}'.encode(),presence)
startup='''wait-until callback2=MainCB2_Intro max 1000
wait-until callback2=MainCB2 max 20000
wait-until task_first=Task_TitleScreenPhase3 max 600
press START
wait-until task_first=Task_HandleMainMenuInput max 600
press A
wait-until callback2=CB2_Overworld max 1200
wait-until controls_locked=0 max 600
wait-until in_battle=1 max 18000
dump coop_entered
mash A until in_battle=0 max 36000
wait 180
dump coop_returned
'''
players={};procs={};logs={};offsets={}
for name in ('Alice','Bob'):
 p=root/name;p.mkdir(exist_ok=True);(p/'out').mkdir(exist_ok=True)
 shutil.copyfile(save,p/'player.sav');(p/'in').write_text('');(p/'events').write_text('');(p/'replay').write_text(startup)
 env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',EW_FAKE_LINK_IN=str(p/'in'),
          EW_FAKE_LINK_OUT=str(p/'events'),EW_TEST_REPORT=str(p/'report'))
 if name=='Alice':env['EW_TEST_COOP_OWNER']='1'
 logs[name]=(p/'stderr.log').open('w');players[name]=p;offsets[name]=0
 procs[name]=subprocess.Popen([str(binary),'--headless','--silent','--replay',str(p/'replay'),
  '--out',str(p/'out'),'--save',str(p/'player.sav'),'--rtc-offset',str(p/'clock.rtc'),
  '--rtc-fixed','1700000000'],env=env,stdout=subprocess.DEVNULL,stderr=logs[name])
try:
 deadline=time.monotonic()+420
 while time.monotonic()<deadline:
  for name,p in players.items():
   with (p/'events').open() as f:
    f.seek(offsets[name]); lines=f.readlines(); offsets[name]=f.tell()
   for line in lines:
    if not line.endswith('\n'): raise AssertionError('partial relay record')
    messages=broker.process(name,line.rstrip('\n').encode(),presence)
    for target,out in messages:
     if out.startswith('T '):continue
     if ' ERROR ' in out:raise AssertionError(f'{target}: {out.strip()}')
     with (players[target]/'in').open('a') as dest:dest.write(out)
  if all((p/'report').exists() and (p/'out'/'coop_returned.txt').exists() for p in players.values()):
   for p in players.values():
    report=(p/'report').read_text()
    if 'committed=1\n' not in report or 'party_count=1\n' not in report or 'species=252\n' not in report:
     raise AssertionError('private-party report unexpected: '+report)
   print('Two game processes completed a co-op battle via file relay and restored their own parties.')
   break
  if any(proc.poll() is not None for proc in procs.values()):
   raise AssertionError('game exited before both committed and returned')
  time.sleep(.005)
 else:raise AssertionError('two-game co-op replay timed out')
except BaseException:
 for log in logs.values():log.flush()
 for name,p in players.items():
  print(name+' stderr:\n'+(p/'stderr.log').read_text()[-6000:],file=sys.stderr)
  print(name+' relay:\n'+(p/'events').read_text()[-3000:],file=sys.stderr)
 raise
finally:
 for proc in procs.values():
  if proc.poll() is None:proc.terminate()
 for proc in procs.values():
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
 for log in logs.values():log.close()
