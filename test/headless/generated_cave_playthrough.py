#!/usr/bin/env python3
"""Disposable offline native cave entry/walk/return check; not multiplayer acceptance."""
import argparse
import hashlib
import os
from pathlib import Path
import shlex
import tempfile

import driver
from world.cave_blueprint import proposal_from_blueprint
from scripts.export_generated_cave import encode


def run(binary, seed, out, encounter=False, profile=None, observe_only=False):
    binary, seed, out = Path(binary).resolve(), Path(seed).resolve(), Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    blueprint = {'rooms': [[2,2,12,12],[16,16,12,12]], 'links': [[0,1]],
                 'entrance_room': 0, 'exit_room': 1, 'style': 'organic',
                 'seed': 42, 'corridor_width': 2}
    proposal = proposal_from_blueprint(blueprint)
    if proposal['rows'][1][1:3] != '..':
        raise RuntimeError('fixture requires a walkable eastward first step')
    with tempfile.TemporaryDirectory(prefix='cave-playthrough-') as temp:
        root = Path(temp)
        cave = root/'cave.bin'
        cave.write_bytes(encode(proposal, encounter_profile=profile))
        # driver.Game accepts an executable path; the wrapper supplies only the
        # local validated test template and forwards all of its existing args.
        wrapper = root/'run-native'
        wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(str(binary)) + ' --generated-map ' + shlex.quote(str(cave)) + ' "$@"\n')
        wrapper.chmod(0o700)
        try:
            game = driver.Game(str(wrapper), str(out), save=str(seed), max_frames=40000 if encounter else 20000)
        except Exception as error:
            stderr_path = out/'stderr.txt'
            details = stderr_path.read_text(errors='replace')[-4000:] if stderr_path.exists() else 'no native stderr'
            raise RuntimeError(f'native startup failed: {details}') from error
        save_before = hashlib.sha256(Path(game.save_path).read_bytes()).digest()
        try:
            driver.continue_game(game)
            if game.state.map_name != 'LittlerootTown_ProfessorBirchsLab':
                raise RuntimeError(f'unexpected seed map: {game.state}')
            driver.walk_to(game, 6, 11)
            driver.leave_map(game, 'DOWN')
            driver.wait_until(game, lambda state: state.free)
            origin = (tuple(game.state.map), game.state.pos)
            # The first-battle fixture has POKEMON, BAG, PLAYER, SAVE, OPTION,
            # WORLD, EXIT, and a fresh process starts with cursor at row zero.
            game.tap('START', gap=30)
            game.tap('DOWN', times=5)
            game.tap('A', gap=60)
            # World opens with Story rally selected: two rows down is Explore.
            game.tap('DOWN', times=2)
            game.tap('A', gap=90)
            driver.wait_until(game, lambda state: state.map_name == 'GeneratedWorld_Cave' and state.free)
            if game.state.pos != (1, 1):
                raise RuntimeError(f'unexpected cave spawn: {game.state}')
            game.press('RIGHT', 16)
            game.wait(20)
            if encounter:
                # Walk only between two known floor cells. Wait for the real
                # wild-battle screen; do not inspect hidden enemy party data.
                for _ in range(600):
                    driver.wait_until(game, lambda state: state.free or state.battle)
                    if game.state.battle:
                        break
                    if game.state.map_name != 'GeneratedWorld_Cave' or game.state.pos not in ((1,1),(2,1)):
                        raise RuntimeError(f'unexpected encounter route: {game.state}')
                    game.press('LEFT' if game.state.pos == (2,1) else 'RIGHT', 16)
                    game.wait(20)
                if not game.state.battle:
                    raise RuntimeError('no cave encounter after 600 steps')
                driver.wait_until(game, lambda state: state.battle and state.battle_state
                                  and any(mon['side'] == 1 for mon in state.battle_state['battlers']),
                                  step=10, limit=3000)
                enemies = [mon for mon in game.state.battle_state['battlers'] if mon['side'] == 1]
                # Confirm the visible opponent belongs to the selected native table.
                if profile == 'meteor':
                    allowed = {(41,level) for level in range(14,21)} | {(349,14),(349,16),(349,18)}
                else:
                    allowed = {(41,7),(41,8),(335,7),(335,8),(335,9),(335,10),(335,6),
                               (63,8),(74,7),(74,8),(74,6),(74,9)}
                if len(enemies) != 1 or (enemies[0]['species'], enemies[0]['level']) not in allowed:
                    raise RuntimeError(f'unexpected cave encounter: {enemies}')
                if not observe_only:
                    # Advance intro/outcome text and choose RUN. Down and Right are
                    # idempotent on the native two-by-two action menu.
                    for _ in range(12):
                        if not game.state.battle:
                            break
                        game.tap('B', times=6, gap=12)
                        if not game.state.battle:
                            break
                        game.tap('DOWN'); game.tap('RIGHT'); game.tap('A', gap=60)
                    if game.state.battle:
                        raise RuntimeError('could not flee the generated-cave encounter')
                    driver.wait_until(game, lambda state: state.free)
                    if game.state.map_name != 'GeneratedWorld_Cave' or not game.state.party:
                        raise RuntimeError(f'wild battle did not return the trainer and party to the cave: {game.state}')
            else:
                if game.state.battle:
                    driver.fight_battle(game)
                driver.wait_until(game, lambda state: state.free)
                if game.state.map_name != 'GeneratedWorld_Cave' or game.state.pos != (2, 1):
                    raise RuntimeError(f'could not walk the generated floor: {game.state}')
            if not observe_only:
                # Inside, SAVE is absent, shifting WORLD one row above its previous
                # cursor position. The cave World menu defaults to its Back row.
                game.tap('START', gap=30)
                game.tap('UP')
                game.tap('A', gap=60)
                game.tap('UP')
                game.tap('A', gap=90)
                driver.wait_until(game, lambda state: tuple(state.map) == origin[0] and state.free)
                if game.state.pos != origin[1]:
                    raise RuntimeError(f'cave returned to the wrong field position: {game.state}, expected {origin}')
        finally:
            code = game.finish()
        if code != 0:
            raise RuntimeError(f'native test process exited {code}')
        if hashlib.sha256(Path(game.save_path).read_bytes()).digest() != save_before:
            raise RuntimeError('entering/leaving the cave unexpectedly changed the disposable save file')
    if encounter and observe_only:
        print('PASS: native offline cave loaded the selected encounter profile without writing the save')
    elif encounter:
        print('PASS: native cave wild encounter, escape and field return without writing the save')
    else:
        print('PASS: native offline generated cave entry, walking, return and save isolation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--seed-save', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--encounter', action='store_true', help='walk until a visible wild encounter starts')
    parser.add_argument('--profile', choices=('meteor',), help='use a versioned offline encounter profile')
    parser.add_argument('--observe-only', action='store_true', help='stop at the visible encounter')
    args = parser.parse_args()
    if (args.profile or args.observe_only) and not args.encounter:
        parser.error('--profile and --observe-only require --encounter')
    run(args.binary, args.seed_save, args.out, encounter=args.encounter,
        profile=args.profile, observe_only=args.observe_only)

if __name__ == '__main__':
    main()
