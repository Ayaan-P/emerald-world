#!/usr/bin/env python3
"""Paired app/native character acceptance using only disposable profiles.

Public authored NPC fixture is deployed through the actual sandbox/admin API.
Only PlayerClient controller input drives the native game. No debugger, private
mon injection, synthetic native packets, user saves or installed client is used.
Generated route/XL gameplay is not asserted by this normal-map vertical slice.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from world.client import admin_request
from world.expansion import ENGINE, ExpansionSession
from world.launcher import ProfileLock, _prepare_profile, game_command, player_endpoint
from world.player import PlayerClient
from world.server import WorldServer


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def progress(state):
    return {k: int(v) for k, v in (item.split('=') for item in state['party0_progress'].split())}


def ready(state):
    return (state.get('overworld') and not state.get('locked') and not state.get('battle')
            and not state.get('fade') and state.get('world', {}).get('connected')
            and state['world'].get('ready'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=ROOT / 'engines/expansion-native/build/native64/pokeemerald-native')
    parser.add_argument('--disposable-seed', type=Path, required=True)
    parser.add_argument('--seed-provenance', required=True, help='Actual disposable opening replay provenance, never human data')
    parser.add_argument('--output', type=Path, required=True, help='Fresh directory below build/character-acceptance')
    args = parser.parse_args(argv)
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / 'build/character-acceptance'):
        parser.error('--output must be below this checkout build/character-acceptance')
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    report: dict = dict(ok=False, milestones=[], scope='normal-map character dialogue/cancel/consent, native battle win, normal save and cold Continue',
                  fixture='public authored trainer with canonical level-2 opponent; sandbox deployment, not normal NPC discovery or acquisition',
                  seed_provenance=args.seed_provenance, generated_route_xl='not exercised', debug_invoked=False,
                  command=[sys.executable, *sys.argv], app_root=str(ROOT))
    client = proc = server = lock = log = None
    base = paths = None
    started = time.monotonic()

    def record(label, state=None, **extra):
        with (out / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(label=label, elapsed=time.monotonic()-started, state=state, **extra))+'\n')

    def observe():
        if proc.poll() is not None:
            raise RuntimeError('owned native exited: ' + str(proc.returncode))
        return client.observe()['state']

    def press(buttons=(), frames=24):
        result = client.press(list(buttons), frames)
        record('controller', result.get('state'), buttons=list(buttons), frames=frames)
        return result

    def tap(button):
        press([button], 2)
        press([], 24)

    def capture(label):
        client.screenshot()
        ppm = out / (label+'.ppm')
        shutil.copyfile(paths['profile']/'screenshot.ppm', ppm)
        try:
            from PIL import Image
            Image.open(ppm).save(out/(label+'.png'))
        except ImportError:
            pass

    def milestone(label):
        report['milestones'].append(label)
        record(label, observe())

    def until(label, predicate, attempts=40, buttons=()):
        for _ in range(attempts):
            state = observe()
            if predicate(state):
                record(label, state)
                return state
            press(buttons, 60)
        raise TimeoutError(label)

    def boot():
        nonlocal client
        deadline = time.monotonic()+15
        endpoint = player_endpoint(paths)
        while not endpoint.is_socket():
            if proc.poll() is not None:
                raise RuntimeError('native startup failed: '+str(proc.returncode))
            if time.monotonic()>deadline:
                raise TimeoutError('native player endpoint startup')
            time.sleep(.05)
        client = PlayerClient(endpoint, timeout=10)
        for _ in range(3):
            press([], 120)
        tap('START')
        press([], 90)
        for _ in range(10):
            if ready(observe()):
                return observe()
            tap('A')
            press([], 120)
        raise TimeoutError('cold Continue to linked ready field')

    def launch(label):
        nonlocal proc, log
        log = (out/(label+'.log')).open('wb')
        proc = subprocess.Popen(report['game_command'], cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        return boot()

    def stop():
        nonlocal client, proc, log
        if client:
            client.close()
            client = None
        if proc:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            report.setdefault('owned_process_exits', []).append(proc.returncode)
            proc = None
        if log:
            log.close()
            log = None

    try:
        # A single readiness inspection, never wait/poll a concurrent build.
        binary = args.binary.resolve()
        if not binary.is_file():
            raise FileNotFoundError('parent build not ready: '+str(binary))
        seed = args.disposable_seed.resolve(strict=True)
        report.update(seed_path=str(seed), seed_sha256=sha(seed), binary_source=str(binary))
        pinned = out/'runtime'/binary.name
        pinned.parent.mkdir()
        before = sha(binary)
        shutil.copy2(binary, pinned)
        after = sha(binary)
        if before != after or sha(pinned) != before:
            raise RuntimeError('binary changed while snapshotting; rerun in a fresh evidence directory')
        symbols = binary.with_name(binary.name+'.symbols')
        if not symbols.is_file():
            raise FileNotFoundError('matching native symbols missing: '+str(symbols))
        symbol_before = sha(symbols)
        shutil.copy2(symbols, pinned.with_name(pinned.name+'.symbols'))
        if sha(symbols) != symbol_before or sha(pinned.with_name(pinned.name+'.symbols')) != symbol_before:
            raise RuntimeError('symbols changed while snapshotting')
        report.update(binary_sha256=before, symbols_sha256=symbol_before)
        source_files = ['world/server.py', 'world/characters.py', 'world/launcher.py', 'world/player.py',
                        'world/route_characters.py', 'world/region_characters.py', 'world/expansion_species.json',
                        'engines/expansion-native/src/world/world_bridge.c',
                        'engines/expansion-native/src/world/world_character.c']
        report['source_hashes_before'] = {p:sha(ROOT/p) for p in source_files}
        # Short private temp root is necessary for sockaddr_un's 107-byte limit.
        # Entire directory belongs to this harness and is removed on cleanup.
        base = Path(tempfile.mkdtemp(prefix='rc11-char-'))
        session = ExpansionSession(base, 'alice')
        paths = session.paths
        lock = ProfileLock(base, 'alice', engine=ENGINE)
        lock.__enter__()
        session.state.mkdir(parents=True, mode=0o700, exist_ok=True)
        # As in run_expansion_release_journey, this low-level helper receives
        # the already engine-scoped authority root, not the outer world root.
        _prepare_profile(session.state, 'alice', seed, paths)
        os.chmod(paths['save'], 0o600)
        server = WorldServer(session.state/'transport/world.sock', session.state)
        report['wire'] = []
        original_line, original_queue = server._line, server._queue

        def traced_line(conn, raw):
            if raw.startswith((b'CHARACTER_', b'INTERACT')):
                report['wire'].append(dict(direction='native_to_authority', line=raw.decode(), elapsed=time.monotonic()-started))
            return original_line(conn, raw)

        def traced_queue(conn, text):
            for line in text.splitlines():
                if line.startswith(('CHARACTER_', 'ERROR ')):
                    report['wire'].append(dict(direction='authority_to_native', line=line, elapsed=time.monotonic()-started))
            return original_queue(conn, text)

        server._line, server._queue = traced_line, traced_queue
        server.start()
        report['game_command'] = game_command(pinned, base, paths, agent_control=True, engine=ENGINE)
        state = launch('native')
        report['opening_state'] = state
        milestone('exact pinned native cold-Continued disposable opening into linked field')
        assert state['world']['pos'] == [6,5] and state['map_name'] == 'MAP_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB', 'unexpected disposable opening fixture'
        before_progress = progress(state)
        # Birch and rival are north at (6,4)/(7,4). East (7,5) is clear in the
        # canonical lab object list and verified rendered below, not a mon edit.
        species_catalog = json.loads((ROOT/'world/expansion_species.json').read_text())['species']
        opponent = species_catalog['SPECIES_POOCHYENA'] if 'SPECIES_POOCHYENA' in species_catalog else species_catalog['POOCHYENA']
        obj = dict(id='dot_acceptance', group=state['world']['map'][0], num=state['world']['map'][1],
                   x=7, y=5, gfx=8, text='Ready for a friendly match?')
        character = dict(version=1, name='Dot', role='Disposable acceptance trainer', goals=['Practice a friendly match'],
                         relationships={}, team=[dict(species=opponent,level=2)], status='active',
                         object_id=obj['id'], evidence=[], reason='Explicit disposable public author fixture')
        result = dict(state={'world_characters':{obj['id']:character}}, tiles=[], objects=[obj])
        source = 'def update(context, state):\n    return '+repr(result)+'\n'
        candidate = server.root/'candidates'/'acceptance.py'
        candidate.parent.mkdir(exist_ok=True)
        candidate.write_text(source)
        (out/'authored-fixture.py').write_text(source)
        response = admin_request(server.socket_path, dict(command='deploy', source_path=str(candidate)), timeout=15)
        report['deployment'] = response
        assert response['ok'], response
        inspected = server.inspect()
        report['authority_after_deploy'] = inspected
        assert inspected['objects'] == [obj] and inspected['state']['world_characters'][obj['id']] == character
        until('authored character rendered', lambda s:any(o['id']==obj['id'] and o['visible'] and o['pos']==[7,5] for o in s['world']['objects']))
        tap('RIGHT')
        assert observe()['world']['pos'] == [6,5], 'facing should be blocked by rendered character'
        capture('rendered-character')
        milestone('public character committed by real sandbox/admin and visibly rendered beside native player')

        def dialogue():
            tap('A')
            return until('authored dialogue', lambda s:s['world']['dialogue_active'] and s['world']['dialogue_text']==obj['text'])

        def consent():
            for _ in range(8):
                tap('A')
                state = observe()
                if state['world']['dialogue_active'] and state['world']['dialogue_text'].startswith('Battle this trainer?'):
                    return state
            raise TimeoutError('authored dialogue did not advance to explicit consent')

        dialogue()
        press([], 120)
        capture('authored-dialogue')
        assert not any(w['line'].startswith('CHARACTER_CHALLENGE') for w in report['wire'])
        consent()
        press([], 120)
        capture('consent-before-cancel')
        assert not any(w['line'].startswith('CHARACTER_CHALLENGE') for w in report['wire']), 'dialogue automatically accepted battle'
        for _ in range(6):
            tap('B')
            if ready(observe()):
                break
        assert ready(observe()), 'cancel failed to release field controls'
        assert not any(w['line'].startswith('CHARACTER_CHALLENGE') for w in report['wire']), 'cancel sent challenge'
        with server.lock:
            assert not server.peers['alice'].get('character_pending')
        milestone('controller opened authored dialogue and separate consent, B cancelled without challenge or battle')
        dialogue()
        consent()
        for _ in range(8):
            tap('A')
            if observe()['battle']:
                break
        state = until('actual native character battle', lambda s:s['battle'], attempts=60)
        capture('native-character-battle')
        challenges = [w for w in report['wire'] if w['line'].startswith('CHARACTER_CHALLENGE ')]
        replies = [w for w in report['wire'] if w['line'].startswith('CHARACTER_BATTLE_V1 ')]
        assert len(challenges)==1 and len(replies)==1, 'expected exactly one consented authority challenge/reply'
        assert replies[0]['line'].endswith(' %s 2'%opponent), 'authority returned wrong team'
        milestone('native accepted actual authority-frozen team and entered real trainer battle')
        # First move is starter Pound. Advance intro and ordinary fight/move
        # menus with distinct edges; no memory writes or battle debug helpers.
        deadline = time.monotonic()+180
        captured_action_selection = False
        while True:
            state = observe()
            if state.get('battle') and state.get('battle_main') == 'HandleTurnActionSelectionState' and not captured_action_selection:
                capture('native-battle-action-selection')
                captured_action_selection = True
            if ready(state):
                break
            if time.monotonic()>deadline:
                raise TimeoutError('native character battle did not finish and return')
            tap('A')
            press([], 60)
        after_progress = progress(state)
        report['rendered_battle_action_selection_captured'] = captured_action_selection
        report['private_progress'] = dict(before=before_progress, after=after_progress)
        assert after_progress['outcome']==1, 'native character battle did not win'
        assert after_progress['exp']>before_progress['exp'], 'owned starter did not gain battle EXP'
        for field in ('species','personality','ot'):
            assert after_progress[field]==before_progress[field], 'private identity changed: '+field
        reports = [w for w in report['wire'] if w['line'].startswith('CHARACTER_RESULT ')]
        assert len(reports)==1 and reports[0]['line'].endswith(' 1'), 'missing native won result'
        assert any(w['line'].startswith('CHARACTER_RESULT_ACK ') for w in report['wire']), 'no authority result ACK'
        with server.lock:
            assert not server.peers['alice'].get('character_pending')
            report['character_battle_reports'] = [json.loads(row[0]) for row in server.db.execute("SELECT data FROM events WHERE kind='character_battle_report'")]
        capture('battle-return')
        milestone('actual character battle won, native returned unlocked, authority consumed result and ACKed once')
        save_before = sha(paths['save'])
        expected = dict(map=state['world']['map'], pos=state['world']['pos'], party_count=state['party_count'], progress=after_progress)
        tap('START')
        for _ in range(4):
            tap('UP')
        tap('A')
        press([], 60)
        for _ in range(10):
            tap('A')
            press([], 60)
            if sha(paths['save'])!=save_before and ready(observe()):
                break
        until('normal save returned', ready)
        save_after = sha(paths['save'])
        assert save_after!=save_before, 'normal save did not advance private save hash'
        shutil.copyfile(paths['save'], out/'post-battle-disposable.sav')
        report['save_hashes'] = dict(seed=report['seed_sha256'], before=save_before, after=save_after)
        milestone('normal START-menu save wrote changed private save bytes')
        stop()
        player_endpoint(paths).unlink(missing_ok=True)
        loaded = launch('cold')
        loaded_progress = progress(loaded)
        assert loaded['world']['map']==expected['map'] and loaded['world']['pos']==expected['pos'], 'cold position mismatch'
        assert loaded['party_count']==expected['party_count']
        for field in ('species','personality','ot','exp','hp','level','status'):
            assert loaded_progress[field]==expected['progress'][field], 'cold private Pokemon mismatch: '+field
        assert sha(paths['save'])==save_after, 'cold Continue rewrote save'
        report['cold_state'] = loaded
        report['save_hashes']['cold'] = sha(paths['save'])
        capture('cold-continue')
        milestone('cold Continue loaded exact changed save with post-battle private identity/progress/location')
        assert sha(seed)==report['seed_sha256'], 'source disposable seed changed'
        assert sha(pinned)==report['binary_sha256'], 'pinned binary changed during run'
        report['source_hashes_after'] = {p:sha(ROOT/p) for p in source_files}
        report['concurrent_source_changes'] = [p for p in source_files if report['source_hashes_before'][p]!=report['source_hashes_after'][p]]
        report['ok'] = True
    except Exception as exc:
        report['error'] = type(exc).__name__+': '+str(exc)
        report['traceback'] = traceback.format_exc()
        if client:
            try:
                record('failure', observe())
                capture('failure')
            except Exception as capture_error:
                report['capture_error'] = str(capture_error)
    finally:
        if proc:
            report['process_exit_before_cleanup'] = proc.poll()
        stop()
        if server:
            report['authority_final'] = server.inspect()
            server.close()
        if lock:
            lock.__exit__(None,None,None)
        if base:
            shutil.rmtree(base)
        if report.get('binary_sha256'):
            report['pinned_binary_sha256_after'] = sha(out/'runtime'/args.binary.name)
            report['pinned_symbols_sha256_after'] = sha(out/'runtime'/(args.binary.name+'.symbols'))
        report['elapsed_seconds'] = time.monotonic()-started
        (out/'acceptance.json').write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps(dict(ok=report['ok'], milestones=report['milestones'], error=report.get('error'), report=str(out/'acceptance.json'))))
    return 0 if report['ok'] else 1


if __name__=='__main__':
    sys.exit(main())
