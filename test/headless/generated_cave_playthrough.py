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


def run(binary, seed, out):
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
        cave.write_bytes(encode(proposal))
        # driver.Game accepts an executable path; the wrapper supplies only the
        # local validated test template and forwards all of its existing args.
        wrapper = root/'run-native'
        wrapper.write_text('#!/bin/sh\nexec ' + shlex.quote(str(binary)) + ' --generated-map ' + shlex.quote(str(cave)) + ' "$@"\n')
        wrapper.chmod(0o700)
        try:
            game = driver.Game(str(wrapper), str(out), save=str(seed), max_frames=20000)
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
            if game.state.battle:
                driver.fight_battle(game)
            driver.wait_until(game, lambda state: state.free)
            if game.state.map_name != 'GeneratedWorld_Cave' or game.state.pos != (2, 1):
                raise RuntimeError(f'could not walk the generated floor: {game.state}')
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
    print('PASS: native offline generated cave entry, walking, return and save isolation')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', required=True)
    parser.add_argument('--seed-save', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    run(args.binary, args.seed_save, args.out)

if __name__ == '__main__':
    main()
