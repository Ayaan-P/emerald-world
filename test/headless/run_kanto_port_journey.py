"""Disposable full native Kanto port slice; no human saves or live clients.

The ordinary opening supplies Treecko and the first save. An existing debug
warp stages Slateport. All regional travel, walking, saving and Continue use
normal controls after that. This does not prove earned Slateport progression,
Kanto battles, complete story support or connected-world Kanto admission.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engines/expansion-native'
PORT = r'''
wait 30
hold R
press START
release R
wait-until debug_menu_open=1 max 120
wait 20
press A # Utilities
wait 20
press DOWN
press A # Existing debug warp
wait 20
press A # group 0
wait 20
press UP # map 1 Slateport
press A
wait 20
press A # warp 0
wait 120
mash B until controls_locked=0 max 1200
wait 30
expect map=0.1
dump slateport
screenshot slateport
press START
wait-until task_last=Task_ShowStartMenu max 120
wait 20
press UP times 2 # WORLD
press A
wait 60
dump slateport_world
screenshot slateport_world
press DOWN # generated area -> regional port
press A
wait 120
mash B until controls_locked=0 max 1200
wait 60
expect map=38.0
expect pos=6,8
dump pallet
screenshot pallet
hold RIGHT for 16
wait 30
expect pos=7,8
dump pallet_walk
screenshot pallet_walk
press START
wait-until task_last=Task_ShowStartMenu max 120
wait 20
press UP times 2 # WORLD cursor -> SAVE
press A
mash A until controls_locked=0 max 3000
wait 30
expect save_counter=2
dump pallet_saved
restart
wait-until callback2=MainCB2_Intro max 1000
wait-until callback2=MainCB2 max 20000
wait-until task_first=Task_TitleScreenPhase3 max 600
press START
wait-until task_first=Task_HandleMainMenuInput max 600
press A
wait-until callback2=CB2_Overworld max 1200
wait 30
wait-until controls_locked=0 max 600
expect map=38.0
expect pos=7,8
expect save_counter=2
expect party0_species=252
dump pallet_cold_continue
screenshot pallet_cold_continue
press START
wait-until task_last=Task_ShowStartMenu max 120
wait 20
press UP times 2
press A
wait 60
press DOWN
press A
wait 180
mash B until controls_locked=0 max 1200
expect map=0.1
expect pos=19,20
dump hoenn_return
screenshot hoenn_return
'''


def facts(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='fresh evidence directory')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    profile = out / 'profile'
    profile.mkdir(mode=0o700)
    replay = out / 'journey.replay'
    replay.write_text(f'include {ENGINE}/tests/smoke/opening.replay\n' + PORT)
    binary = ENGINE / 'build/native64/pokeemerald-native'
    command = [str(binary), '--headless', '--silent', '--unthrottled', '--data-dir', str(profile),
               '--save', str(profile / 'kanto.sav'), '--replay', str(replay), '--out', str(out),
               '--rtc-fixed', '1700000000']
    with (out / 'runtime.log').open('wb') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    report = {'ok': False, 'command': command, 'returncode': result.returncode,
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'scope': __doc__}
    try:
        assert result.returncode == 0, (out / 'runtime.log').read_text()
        stages = {name: facts(out / (name + '.txt')) for name in
                  ('slateport', 'pallet', 'pallet_walk', 'pallet_saved', 'pallet_cold_continue', 'hoenn_return')}
        first = stages['slateport']
        for name, state in stages.items():
            assert state['party0_progress'] == first['party0_progress'], name
            assert state['town_state'] == first['town_state'], name
            assert state['rival_state'] == first['rival_state'], name
            assert state['controls_locked'] == '0', name
        assert stages['pallet_cold_continue']['save_counter'] == '2'
        assert (profile / 'kanto.sav').read_bytes().startswith(b'PENSAV2\0')
        report.update(ok=True, stages=stages, save_format='PENSAV2')
    finally:
        (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'ok': report['ok'], 'output': str(out)}))


if __name__ == '__main__':
    main()
