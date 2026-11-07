#!/usr/bin/env python3
"""Read-only compile probes: RC7 world sources against either engine's headers.
No definitions are stubbed out. Results distinguish compiler errors from warnings.
"""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
NATIVE = ROOT / 'engines/expansion-native'
MODULES = ['native_link', 'link_transport', 'world_coop_potion', 'world_coop_roster',
           'world_cave_wire', 'world_chat', 'world_rally', 'world_bridge', 'world_activity',
           'world_coop', 'world_menu', 'world_travel', 'generated_map', 'dexnav_native',
           'party_autoheal', 'repeat_repel', 'player_control']
FEATURES = ['COOP_FULL_SIX_READY','GENERATED_MAP_READY','GENERATED_MAP_AUTOTILE',
            'GENERATED_MAP_LARGE','GENERATED_MAP_WILDS','GENERATED_CAVE_PROFILES',
            'GENERATED_CAVE_BIOMES','GENERATED_CAVE_WILDLIFE','WORLD_EXTENDED_OBJECTS',
            'WORLD_EXTENDED_SPRITES','WORLD_NATIVE_OAM','WORLD_NATIVE_TILEBANK',
            'WORLD_MATCHED_TRAINERS','WORLD_SMOOTH_PRESENCE','GENERATED_WILDS_GUIDE',
            'GENERATED_WILDS_CAST','GENERATED_WILDS_EVENTS']

def probe(engine, include_root):
    results = []
    for module in MODULES:
        source = (NATIVE / f'src/world/{module}.c') if engine == 'ported' else (ROOT / f'src/platform/{module}.c')
        command = ['gcc','-fsyntax-only','-std=gnu17','-funsigned-char','-fmax-errors=40',
                   '-Werror=implicit-function-declaration','-DMODERN=1','-DEMERALD',
                   '-DPORTABLE=1','-DPLATFORM_NATIVE=1','-DTESTING=0','-DNONMATCHING',
                   '-DUBFIX=1','-DVER_64BIT=1','-iquote',str(include_root/'include'),
                   '-iquote',str(ROOT/'include'),'-iquote',str(include_root),'-iquote',str(ROOT)]
        if engine == 'baseline':
            command += ['-iquote', str(OUT/'baseline-generated'), '-iquote',str(OUT/'baseline-generated/constants')]
        sdl = Path('/home/ayaan/projects/emerald-world-research/deps/sysroot/usr/include')
        command += ['-isystem',str(sdl),'-isystem',str(sdl/'x86_64-linux-gnu')]
        command += [f'-D{feature}=1' for feature in FEATURES]
        command += [str(source)]
        run = subprocess.run(command, text=True, capture_output=True)
        log = OUT / f'{engine}-{module}.log'
        log.write_text(run.stdout+run.stderr)
        errors = [l for l in run.stderr.splitlines() if re.search(r'\b(?:fatal )?error:',l)]
        results.append({'module':module,'exit':run.returncode,'errors':errors,'log':str(log.relative_to(ROOT))})
    return results

report = {'kind':'syntax-only; no linked gameplay or behavior claim',
          'baseline':probe('baseline',ROOT),'expansion':probe('expansion',NATIVE)}
(OUT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
for side in ['baseline','expansion']:
    rows = report[side]
    print(side, 'passing', sum(r['exit']==0 for r in rows),'of',len(rows))
    for row in rows:
        print(row['module'],row['exit'],len(row['errors']),'; '.join(row['errors'][:2]))
