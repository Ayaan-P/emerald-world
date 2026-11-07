"""Observe and talk to a generated outdoor guide in the actual native game."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import tempfile
import driver
from large_cave_playthrough import flee
from world.xl_painted_events import encode
from world.xl_versioned_world import create
from world import xl_revision_author,runtime_gm
from unittest.mock import patch
from world.map_store import write_map
from world.author_cave import decode_blueprint_events


def run(binary,seed,out):
    binary,seed,out=map(lambda p:Path(p).resolve(),(binary,seed,out));out.mkdir(parents=True,exist_ok=True)
    doc={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0,
         'cast':[{'gfx':'boy','x':2,'y':1,'text':'Welcome, traveler!'},{'gfx':'girl','x':75,'y':20,'text':'Far away!'}],
         'paint':[{'x':10,'y':1,'width':30,'height':1,'terrain':'tall_grass'},{'x':80,'y':80,'width':8,'height':8,'terrain':'water'}],
         'events':{'initial':0,'rules':[{'state':0,'npc':1,'next':1,'text':'Please ask my friend.'},{'state':1,'npc':2,'next':2,'text':'Tell them I am well.'},{'state':2,'npc':1,'next':3,'text':'Thank you!'}]}}
    wire='\n'.join(json.dumps(x) for x in ({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(doc)}},{'type':'turn.completed'})).encode()
    proposal,cast,events,paint=decode_blueprint_events(wire,large=True,xl=True,cast=True,events=True,painted=True)
    blob=create(encode(proposal,paint,cast,events),b'1'*16)
    with tempfile.TemporaryDirectory(prefix='wilds-guide-') as t:
        root=Path(t);area=root/'area.bin';area.write_bytes(blob)
        wrapper=root/'run';wrapper.write_text('#!/bin/sh\nexec '+shlex.quote(str(binary))+' --generated-map '+shlex.quote(str(area))+' --generated-progress on "$@"\n');wrapper.chmod(0o700)
        game=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=80000)
        before=hashlib.sha256(Path(game.save_path).read_bytes()).digest()
        try:
            driver.continue_game(game);driver.walk_to(game,6,11);driver.leave_map(game,'DOWN');driver.wait_until(game,lambda s:s.free)
            origin=(tuple(game.state.map),game.state.pos)
            game.tap('START',gap=30);game.tap('DOWN',times=5);game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90)
            driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Wilds' and s.free)
            if (2,1) not in game.state.objects:raise RuntimeError(f'guide not present: {game.state.objects}')
            game.press('RIGHT',1);game.wait(12);game.press('A',2);game.wait(20)
            if not game.state.script and not game.state.locked:raise RuntimeError('interacting with guide did not open dialogue')
            driver.finish_dialog(game)
            if game.state.event_state!=1:raise RuntimeError(f'event did not start: {game.state.event_state}')
            for _ in range(20):
                if game.state.battle:flee(game)
                if game.state.pos==(1,2):break
                game.press('DOWN',16);game.wait(20)
            if game.state.pos!=(1,2):raise RuntimeError(f'guide blocked route: {game.state}')
            def step_to(x,y):
                for _ in range(240):
                    if game.state.battle:flee(game)
                    driver.wait_until(game,lambda s:s.free or s.battle)
                    if game.state.battle:continue
                    cx,cy=game.state.pos
                    if (cx,cy)==(x,y):return
                    direction='RIGHT' if cx<x else 'LEFT' if cx>x else 'DOWN' if cy<y else 'UP'
                    game.press(direction,16);game.wait(15)
                raise RuntimeError(f'could not reach {(x,y)}: {game.state}')
            def talk_to_npc(x,y):
                if (x,y) not in game.state.objects:raise RuntimeError(f'character missing at {(x,y)}: {game.state.objects}')
                game.press('RIGHT',1);game.wait(12);game.press('A',2);game.wait(20)
                if not game.state.script and not game.state.locked:raise RuntimeError(f'character at {(x,y)} did not open dialogue')
                driver.finish_dialog(game)
            step_to(74,2);step_to(74,20);talk_to_npc(75,20)
            if game.state.event_state!=2:raise RuntimeError(f'event handoff failed: {game.state.event_state}')
            step_to(74,2);step_to(1,2);step_to(1,1);talk_to_npc(2,1)
            if game.state.event_state!=3:raise RuntimeError(f'event did not finish: {game.state.event_state}')
            if game.state.battle:flee(game)
            driver.wait_until(game,lambda s:s.free)
            game.tap('START',gap=30);game.tap('UP');game.tap('A',gap=60);game.tap('UP');game.tap('A',gap=90)
            driver.wait_until(game,lambda s:tuple(s.map)==origin[0] and s.free)
            if game.state.pos!=origin[1]:raise RuntimeError('guided wilds returned to wrong position')
            blueprint={'rooms':[[1,1,125,125]],'links':[],'entrance_room':0,'exit_room':0}
            good={**blueprint,'paint':[{'x':30,'y':30,'width':5,'height':5,'terrain':'water'}]}
            bad={**blueprint,'paint':[{'x':75,'y':20,'width':1,'height':1,'terrain':'water'}]}
            def revision_wire(candidate):
                return '\n'.join(json.dumps(x) for x in ({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(candidate)}},{'type':'turn.completed'})).encode()
            catalog=json.dumps({'models':[{'slug':'gpt-6-luna'}]}).encode()
            with patch('world.author_cave.gm._run_author',side_effect=[runtime_gm.CODEX_VERSION.encode(),catalog,revision_wire(bad),revision_wire(good)]):
                updated=xl_revision_author.author_revision('mock revision',blob,attempts=2)
            write_map(area,updated,replace=True)
            game.tap('START',gap=30);game.tap('DOWN');game.tap('A',gap=60);game.tap('DOWN',times=2);game.tap('A',gap=90)
            driver.wait_until(game,lambda s:s.map_name=='GeneratedWorld_Wilds' and s.free)
            if game.state.event_state!=3:raise RuntimeError('story state did not survive world revision')
            game.tap('START',gap=30);game.tap('UP');game.tap('A',gap=60);game.tap('UP');game.tap('A',gap=90)
            driver.wait_until(game,lambda s:tuple(s.map)==origin[0] and s.free)
            if game.state.pos!=origin[1]:raise RuntimeError('revised world exit returned to wrong position')
        finally:code=game.finish()
        if code:raise RuntimeError(f'native client exited {code}')
        if hashlib.sha256(Path(game.save_path).read_bytes()).digest()!=before:raise RuntimeError('disposable save changed')
        sidecar=Path(game.save_path+'.generated-story')
        if not sidecar.exists():raise RuntimeError('durable story sidecar missing')
        again=driver.Game(str(wrapper),str(out),save=str(seed),max_frames=40000)
        try:
            driver.continue_game(again);driver.walk_to(again,6,11);driver.leave_map(again,'DOWN');driver.wait_until(again,lambda s:s.free)
            again.tap('START',gap=30);again.tap('DOWN',times=5);again.tap('A',gap=60);again.tap('DOWN',times=2);again.tap('A',gap=90)
            driver.wait_until(again,lambda s:s.map_name=='GeneratedWorld_Wilds' and s.free)
            if again.state.event_state!=3:raise RuntimeError(f'event progress did not survive restart: {again.state.event_state}')
        finally:code=again.finish()
        if code:raise RuntimeError(f'restarted client exited {code}')
        if hashlib.sha256(Path(again.save_path).read_bytes()).digest()!=before:raise RuntimeError('restarted disposable save changed')
    print('PASS: versioned XL story survived a mocked-model terrain revision and process restart without writing the save')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--seed-save',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();run(a.binary,a.seed_save,a.out)
