"""Offline integrated generated-area entry smoke; no server or sockets.

Runs the donor opening, saves and cold-restarts using disposable files, then
uses the real World menu to enter a generated cave. The two-client
shared-world path and real transport are not tested here.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

binary=Path(sys.argv[1]).resolve(strict=True)
donor=Path(sys.argv[2]).resolve(strict=True)
root=Path(sys.argv[3]).resolve()
root.mkdir(parents=True,exist_ok=True)
output=root/'out';output.mkdir(exist_ok=True)
cells=bytearray(b'#'*(31*31))
for y in range(1,30):cells[y*31+1]=ord('.')
for x in range(1,30):cells[28*31+x]=ord('.')
cells[29*31+29]=ord('.')
template=root/'cave.bin';template.write_bytes(b'EWGMAP01'+cells)
shutil.copyfile(donor/'tests/smoke/opening_start.replay',root/'opening_start.replay')
opening=(donor/'tests/smoke/opening.replay').read_text()
script=root/'generated.replay';script.write_text(opening+'''\n# Leave Birch's lab and open World > Explore generated area.
hold DOWN
wait-until map_name=MAP_LITTLEROOT_TOWN max 1800
release DOWN
wait-until controls_locked=0 max 600
wait 30
dump generated_outside
press START
wait-until task_last=Task_ShowStartMenu max 300
wait 15
dump generated_start_menu
press DOWN
wait 10
press DOWN
wait 10
press DOWN
wait 10
press DOWN
wait 10
press DOWN
wait 10
press A
wait 60
dump generated_world_menu
press DOWN
wait 10
press DOWN
wait 10
press DOWN
wait 10
press A
wait 10
dump generated_selected
wait-until map=34.0 max 1800
wait-until callback2=CB2_Overworld max 900
wait 30
dump generated_entered
''')
env=dict(os.environ,EW_GENERATED_MAP=str(template),SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
result=subprocess.run([str(binary),'--headless','--silent','--unthrottled','--replay',str(script),
 '--out',str(output),'--save',str(root/'player.sav'),'--rtc-offset',str(root/'clock.rtc'),
 '--rtc-fixed','1700000000'],env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=240)
(root/'stdout.log').write_text(result.stdout);(root/'stderr.log').write_text(result.stderr)
if result.returncode:
 print(result.stderr[-10000:],file=sys.stderr)
 raise SystemExit(f'Generated-area entry replay failed ({result.returncode}).')
if not (output/'generated_entered.txt').is_file():
 raise SystemExit('Generated-area entry dump was not produced.')
print('Offline game entered generated cave via World menu after save and restart.')
