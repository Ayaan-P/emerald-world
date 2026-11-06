"""Open and close the opt-in donor DexNav with a disposable save; no sockets."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
binary=Path(sys.argv[1]).resolve(strict=True);fixture=Path(sys.argv[2]).resolve(strict=True)
with tempfile.TemporaryDirectory(prefix='expansion-dexnav-') as d:
 root=Path(d);shutil.copyfile(fixture,root/'game.sav');(root/'out').mkdir()
 script=root/'dexnav.replay';script.write_text('''wait-until callback2=MainCB2_Intro max 1000
wait-until callback2=MainCB2 max 20000
wait-until task_first=Task_TitleScreenPhase3 max 600
press START
wait-until task_first=Task_HandleMainMenuInput max 600
press A
wait-until callback2=CB2_Overworld max 1200
wait-until controls_locked=0 max 600
wait 20
expect flag:2145=0
press START
wait-until task_last=Task_ShowStartMenu max 120
wait 30
mash A until callback2=DexNav_RunSetup max 1200
wait-until task_last=Task_DexNavMain max 1200
wait 20
press B
wait-until callback2=CB2_Overworld max 1200
wait 30
''')
 env=dict(os.environ,EW_EXPERIMENTAL_EXPANSION_DEXNAV='1',EW_EXPANSION_DEXNAV_AUDIT='1',EW_EXPANSION_PRESENCE=str(root/'presence.json'))
 p=subprocess.run([str(binary),'--headless','--silent','--unthrottled','--replay',str(script),'--out',str(root/'out'),'--save',str(root/'game.sav'),'--rtc-offset',str(root/'clock.rtc'),'--rtc-fixed','1700000000'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
 if p.returncode:
  state=(root/'presence.json').read_text() if (root/'presence.json').exists() else 'missing'
  raise AssertionError('DexNav replay failed: '+p.stderr[-5000:]+' presence='+state)
 print('Opened and closed the opt-in donor DexNav.')
