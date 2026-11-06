"""Disposable Expansion cave return, save, and reload; no sockets."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

binary=Path(sys.argv[1]).resolve(strict=True)
fixture=Path(sys.argv[2]).resolve(strict=True)
startup='''wait-until callback2=MainCB2_Intro max 1000
wait-until callback2=MainCB2 max 20000
wait-until task_first=Task_TitleScreenPhase3 max 600
press START
wait-until task_first=Task_HandleMainMenuInput max 600
press A
wait-until callback2=CB2_Overworld max 1200
wait-until controls_locked=0 max 600
wait 30
'''
with tempfile.TemporaryDirectory(prefix='expansion-cave-save-') as directory:
 root=Path(directory);save=root/'game.sav';shutil.copyfile(fixture,save)
 cells=bytearray(b'#'*(31*31))
 for y in range(1,30):cells[y*31+1]=ord('.')
 for x in range(1,30):cells[28*31+x]=ord('.')
 cells[29*31+29]=ord('.')
 template=root/'cave.bin';template.write_bytes(b'EWGMAP01'+cells)
 first=startup+'''mash SELECT,R until map=75.0 max 3000
wait-until callback2=CB2_Overworld max 900
mash A until controls_locked=0 max 3000
mash SELECT,R until map=0.9 max 3000
wait-until callback2=CB2_Overworld max 900
mash A until controls_locked=0 max 3000
wait 30
press START
wait-until task_last=Task_ShowStartMenu max 120
wait 10
press DOWN times 3
press A
mash A until controls_locked=0 max 3000
wait 30
expect save_counter=2
expect map=0.9
'''
 second=startup+'''expect map=0.9
expect party_species=387,495,650,722,810,1289
'''
 for name,text in [('save',first),('reload',second)]:
  script=root/(name+'.replay');script.write_text(text);out=root/name;out.mkdir()
  env=dict(os.environ)
  if name=='save':env.update(EW_EXPERIMENTAL_EXPANSION_CAVE='1',EW_EXPANSION_OFFLINE='1',EW_EXPANSION_CAVE_TEMPLATE=str(template))
  p=subprocess.run([str(binary),'--headless','--silent','--unthrottled','--replay',str(script),'--out',str(out),'--save',str(save),'--rtc-offset',str(root/'clock.rtc'),'--rtc-fixed','1700000000'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
  if p.returncode:raise AssertionError(name+' replay failed: '+p.stderr[-5000:])
 print('Saved after leaving an Expansion cave and reloaded the original map and party.')
