"""Disposable two-client EWGMAP10/native-species encounter proof."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from world.large_cave import encode_wildlife
from world.expansion import ExpansionSession, BINARY, stage_replay
from world.launcher import _prepare_profile
from world.server import WorldServer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'build/species-cohort/live-native'
SEED = ROOT / 'build/species-cohort/disposable-seed.sav'
BASE_REPLAY = ROOT / 'build/species-cohort/continue_saved_smoke.replay'
WORLD_REPLAY = ROOT / 'build/species-cohort/generated-world.replay'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if not SEED.is_file() or not BASE_REPLAY.is_file() or not WORLD_REPLAY.is_file():
        raise SystemExit('missing disposable seed or base replay fixture')
    seed_hash = sha(SEED)
    proposal = {'rows': ['#' * 63] + ['#' + '.' * 61 + '#' for _ in range(61)] + ['#' * 63],
                'spawn': [1, 1], 'exit': [61, 61]}
    roster = [{'species': 'TREECKO', 'level': 5} for _ in range(12)]
    area = encode_wildlife(proposal, 'ice', 100, roster, cohort='expansion-native')
    if not area.startswith(b'EWGMAP11'):
        raise RuntimeError('expansion cohort author did not emit EWGMAP11')
    world_steps = WORLD_REPLAY.read_text().splitlines()
    world_entry = world_steps.index('dump 28_generated_area')
    prefix = [line.replace('map=34.1', 'map=34.0') for line in world_steps[:world_entry + 1]]
    tail = prefix + ['expect map=34.0', 'expect party0_species=252', 'expect save_counter=1',
                     'mash RIGHT until in_battle=1 max 12000', 'wait 180',
                     'wait-until battle_opponent_species=252 max 300',
                     'dump 42_treecko_encounter', 'screenshot 42_treecko_encounter']
    with tempfile.TemporaryDirectory(prefix='species-cohort-live-') as temp:
        base = Path(temp)
        state = base / 'engines/expansion-native'
        state.mkdir(parents=True)
        server = WorldServer(state/'transport/world.sock', state, cave_template=area)
        server.start()
        children = []
        try:
            for trainer in ('CohortA', 'CohortB'):
                session = ExpansionSession(base, trainer)
                paths = session.paths
                _prepare_profile(session.state, trainer, SEED, paths)
                start = stage_replay(BASE_REPLAY, paths['profile'])
                replay = paths['profile']/'species-cohort.replay'
                replay.write_text(start.read_text() + '\n# enter the expansion wildlife area\n' + '\n'.join(tail) + '\n')
                output = paths['profile']/'replay-out'
                output.mkdir()
                command = [str(BINARY), '--data-dir', str(paths['profile']), '--save', str(paths['save']),
                           '--rtc-offset', str(paths['profile']/'clock.rtc'), '--headless', '--silent',
                           '--replay', str(replay), '--out', str(output), '--unthrottled',
                           '--rtc-fixed', '1700000000']
                env = os.environ.copy()
                env.update({'EW_WORLD_CONFIG': str(paths['config']), 'EW_WORLD_HEADLESS': '1',
                            'SDL_VIDEODRIVER': 'dummy', 'SDL_AUDIODRIVER': 'dummy',
                            'SDL_RENDER_DRIVER': 'software'})
                log_path = OUT/f'{trainer.lower()}.log'
                log = log_path.open('w')
                child = subprocess.Popen(command, cwd=ROOT/'engines/expansion-native', env=env,
                                         stdout=log, stderr=subprocess.STDOUT)
                children.append((trainer, child, log, output, paths, log_path))
            deadline = time.monotonic() + 360
            ack = None
            while time.monotonic() < deadline:
                cave = server.shared_cave
                if cave is not None:
                    admitted = sorted(name for name, peer in server.peers.items()
                                      if peer.get('cave_ack') == cave.identity)
                    if admitted == ['CohortA', 'CohortB']:
                        ack = {'clients': admitted, 'version': cave.version,
                               'area_bytes': len(cave.frames().encode()),
                               'same_area_ack': True}
                if all(child.poll() is not None for _, child, *_ in children):
                    break
                time.sleep(.01)
            if not all(child.poll() is not None for _, child, *_ in children):
                raise TimeoutError('two-client native encounter journey exceeded 360 seconds')
            results = []
            for trainer, child, log, output, paths, log_path in children:
                log.close()
                battle_dump = output/'42_treecko_encounter.txt'
                area_dump = output/'41_expansion_area.txt'
                screenshot = output/'42_treecko_encounter.ppm'
                persistent_screenshot = OUT/f'{trainer.lower()}-{screenshot.name}'
                persistent_dump = OUT/f'{trainer.lower()}-{battle_dump.name}'
                for artifact, target in ((area_dump, OUT/f'{trainer.lower()}-{area_dump.name}'),
                                         (battle_dump, persistent_dump), (screenshot, persistent_screenshot)):
                    if artifact.exists():
                        shutil.copyfile(artifact, target)
                results.append({'trainer': trainer, 'exit_code': child.returncode,
                                'area_dump': area_dump.read_text() if area_dump.exists() else None,
                                'battle_dump': battle_dump.read_text() if battle_dump.exists() else None,
                                'battle_dump_path': str(persistent_dump) if battle_dump.exists() else None,
                                'screenshot': str(persistent_screenshot) if screenshot.exists() else None,
                                'save_unchanged': sha(paths['save']) == seed_hash,
                                'log': str(log_path)})
            report = {'native_binary': str(BINARY), 'area_magic': area[:8].decode(),
                      'area_identity_sha256': hashlib.sha256(area).hexdigest(),
                      'authority': ack, 'clients': results, 'seed_sha256': seed_hash}
            (OUT/'result.json').write_text(json.dumps(report, indent=2)+'\n')
            if not ack or ack['version'] != 11 or not ack['same_area_ack']:
                raise RuntimeError(f'both native clients did not ACK the same EWGMAP11 area: {ack}')
            if any(item['exit_code'] != 0 or not item['battle_dump']
                   or 'battle_opponent_species=252' not in item['battle_dump']
                   or not item['save_unchanged'] for item in results):
                raise RuntimeError(f'native clients did not reach a saved-isolated encounter: {results}')
            print(json.dumps(report, indent=2))
        finally:
            for _, child, log, *_ in children:
                if child.poll() is None:
                    child.terminate()
                if not log.closed:
                    log.close()
            server.close()


if __name__ == '__main__':
    main()
