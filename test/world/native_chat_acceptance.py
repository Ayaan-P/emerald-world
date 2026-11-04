#!/usr/bin/env python3
"""Disposable Linux native chat acceptance using real X events and local sockets.

Run after headless smoke. Owns a fresh nested display, never controls its parent.
The seed must be an explicit disposable headless fixture, not a personal save.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'test/headless')]
from world.launcher import prepare_profile, game_command, ProfileLock
from world.server import WorldServer
from headless import tap, wait
import maps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--parent-display', required=True)
    parser.add_argument('--display', default=':138')
    parser.add_argument('--start-key-t', action='store_true', help='verify remapped Start and the visible Ctrl+T chat fallback')
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(ROOT/'build'):
        raise ValueError('use a fresh directory inside this worktree build/')
    if not args.display[1:].isdigit() or not 100 <= int(args.display[1:]) <= 199:
        raise ValueError('choose a fresh nested display :100..:199')
    xsocket = Path('/tmp/.X11-unix/X'+args.display[1:])
    if xsocket.exists() or Path('/tmp/.X'+args.display[1:]+'-lock').exists():
        raise ValueError('display already in use')
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    seed_hash = hashlib.sha256(args.seed.read_bytes()).hexdigest()
    processes, files, locks = [], [], []
    server = None
    report = {'ok': False, 'scope': 'two isolated Linux natives, real X keyboard events, local sockets only',
              'binary_sha256': hashlib.sha256(args.binary.read_bytes()).hexdigest(), 'checks': []}
    env = dict(os.environ, DISPLAY=args.display)

    def record(check):
        report['checks'].append(check)
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print(check,flush=True)

    def until(label, predicate, seconds=30):
        deadline = time.monotonic()+seconds
        while time.monotonic()<deadline:
            if any(p.poll() is not None for p in processes):
                raise AssertionError('owned process exited: '+label)
            result = predicate()
            if result: return result
            time.sleep(.05)
        raise AssertionError('deadline: '+label)

    def x(*command):
        result = subprocess.run(['xdotool',*map(str,command)],env=env,text=True,capture_output=True)
        if command[0] == 'search' and result.returncode == 1: return ''
        result.check_returncode()
        return result.stdout.strip()

    def state(name):
        try: return json.loads(paths[name]['telemetry'].read_text())
        except (OSError,ValueError): return {}

    def open_chat(name):
        x('windowfocus','--sync',windows[name])
        x('key','ctrl+t' if args.start_key_t and name=='alice' else 't')
        time.sleep(.15)

    def chat(name, text):
        open_chat(name)
        x('type','--clearmodifiers','--delay','20','--',text)
        x('key','Return')

    def received(name, text):
        with server.lock:
            return any(bytes.fromhex(m[3]).decode()==text for m in server.peers[name]['chat_history'])

    def screenshot(name, label):
        # Read only the owned native window on the fresh nested display.
        # XGetPixel avoids assumptions about XImage byte order or row padding.
        import ctypes as c
        import struct
        import zlib
        lib=c.CDLL('libX11.so.6')
        lib.XOpenDisplay.argtypes=[c.c_char_p];lib.XOpenDisplay.restype=c.c_void_p
        lib.XGetGeometry.argtypes=[c.c_void_p,c.c_ulong,c.POINTER(c.c_ulong),c.POINTER(c.c_int),c.POINTER(c.c_int),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint)]
        lib.XGetImage.argtypes=[c.c_void_p,c.c_ulong,c.c_int,c.c_int,c.c_uint,c.c_uint,c.c_ulong,c.c_int];lib.XGetImage.restype=c.c_void_p
        lib.XGetPixel.argtypes=[c.c_void_p,c.c_int,c.c_int];lib.XGetPixel.restype=c.c_ulong
        lib.XDestroyImage.argtypes=[c.c_void_p];lib.XCloseDisplay.argtypes=[c.c_void_p]
        display=lib.XOpenDisplay(args.display.encode())
        assert display
        image=None
        try:
            root=c.c_ulong();xx=c.c_int();yy=c.c_int();width=c.c_uint();height=c.c_uint();border=c.c_uint();depth=c.c_uint()
            assert lib.XGetGeometry(display,int(windows[name]),c.byref(root),c.byref(xx),c.byref(yy),c.byref(width),c.byref(height),c.byref(border),c.byref(depth))
            image=lib.XGetImage(display,int(windows[name]),0,0,width.value,height.value,c.c_ulong(-1),2)
            assert image and depth.value==24
            raw=bytearray()
            for y in range(height.value):
                raw.append(0)
                for xcoord in range(width.value):
                    pixel=lib.XGetPixel(image,xcoord,y)
                    raw.extend(((pixel>>16)&255,(pixel>>8)&255,pixel&255))
            def chunk(kind,data):
                return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
            png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width.value,height.value,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
            (out/(label+'.png')).write_bytes(png)
        finally:
            if image:lib.XDestroyImage(image)
            lib.XCloseDisplay(display)

    try:
        log=(out/'display.log').open('w');files.append(log)
        display_env=dict(os.environ,DISPLAY=args.parent_display,HOME=str(out))
        display=subprocess.Popen(['Xephyr',args.display,'-screen','1100x900','-ac','-nolisten','tcp','-noreset','-extension','GLX'],env=display_env,stdout=log,stderr=subprocess.STDOUT)
        processes.append(display)
        until('nested X socket',xsocket.is_socket,5)
        world=out/'w'
        server=WorldServer(world/'transport/world.sock',world)
        server.start()
        paths={n:prepare_profile(world,n,args.seed) for n in ('alice','bob')}
        startup=wait(300)+tap('START')+wait(120)+tap('START')+wait(200)+tap('A')+wait(200)+tap('A')+wait(200)
        windows={}
        initial_hashes={}
        for index,name in enumerate(paths):
            p=paths[name]
            initial_hashes[name]=hashlib.sha256(p['save'].read_bytes()).hexdigest()
            p['settings'].write_text('scale = 2\nfullscreen = false\n'+('key_start = T\n' if args.start_key_t and name=='alice' else ''))
            boot=p['profile']/'boot.txt'
            boot.write_text(''.join(f'{frames} {buttons}\n' for frames,buttons in startup))
            locks.append(ProfileLock(world,name))
            log=(out/(name+'.log')).open('w');files.append(log)
            boot_done=p['profile']/'boot-done.ppm'
            command=game_command(args.binary,world,p,display=args.display)+['--world-input',str(boot),'--world-shot',str(boot_done)]
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            processes.append(proc)
            windows[name]=until(name+' window',lambda: x('search','--name','^'+re.escape('Emerald World | '+name+' | Human')+'$') or None)
            x('windowmove',windows[name],index*500,0)
            x('windowfocus',windows[name]);x('keydown','space')
            until(name+' field ready',lambda: state(name).get('ready'),15)
            until(name+' human input handoff',boot_done.exists,5)
            x('keyup','space')
        record('Both natives loaded independent copied fixtures into the field')
        if args.start_key_t:
            x('windowfocus','--sync',windows['alice'])
            start_frame=state('alice')['frame']
            x('keydown','t');time.sleep(.15);x('keyup','t')
            def start_menu_open():
                current=state('alice')
                return (current.get('ready') is False and current.get('frame',0)>start_frame
                        and current.get('map')==[1,4] and current.get('in_battle') is False)
            until('remapped T opens native Start menu',start_menu_open)
            screenshot('alice','remapped-start-menu')
            x('keydown','x');time.sleep(.15);x('keyup','x')
            until('remapped Start menu closes',lambda:state('alice').get('ready'))
            record('Configured key_start=T opens the native Start menu. Ctrl+T remains available for chat')
        chat('alice','/w bob First private message!')
        until('first-open private delivery',lambda:received('bob','First private message!'))
        chat('alice','Hello field friends! <&> 100%')
        until('room delivery',lambda:received('bob','Hello field friends! <&> 100%'))
        until('native room receipt',lambda:state('bob').get('chat_count')==2)
        screenshot('bob','field-room')
        chat('bob','/w alice Private field reply!')
        until('direct reply',lambda:received('alice','Private field reply!'))
        record('Room and direct messages traverse native SDL input, server authority and receiving native snapshots')
        # Follow the real saved rival-route input, stopping at the first natural
        # encounter. No save edits, debug warps, or battle-state forcing.
        x('windowfocus',windows['alice'])
        def move(key, predicate, label):
            x('keydown',key)
            try: until(label,lambda:state('alice').get('in_battle') or predicate(),8)
            finally:x('keyup',key)
            if not state('alice').get('in_battle'):
                until('movement settled',lambda:state('alice').get('ready') or state('alice').get('in_battle'),8)
        def walk_to(tx,ty):
            for _ in range(80):
                current=state('alice')
                if current.get('in_battle'):return
                px,py=current['pos']
                if [px,py]==[tx,ty]:return
                terrain=maps.load(maps.map_name(*current['map']))
                route=terrain.path((px,py),(tx,ty),grass_cost=0)
                if not route:raise AssertionError('no walkable path to target')
                key=route[0].title()
                previous=current['pos']
                move(key,lambda:state('alice').get('pos')!=previous,'walking '+key)
            raise AssertionError('walking did not reach target')
        walk_to(6,11)
        move('Down',lambda:state('alice').get('map')==[0,9],'outside lab')
        walk_to(11,0)
        move('Up',lambda:state('alice').get('map')==[0,16],'Route 101')
        for _ in range(6):
            walk_to(11,0)
            if state('alice').get('in_battle'):break
            walk_to(11,15)
            if state('alice').get('in_battle'):break
        until('natural wild battle',lambda:state('alice').get('in_battle'),10)
        before=state('alice')['frame']
        chat('alice','Battle chat works!')
        until('battle chat delivery',lambda:received('bob','Battle chat works!'))
        chat('bob','/w alice Good luck in battle!')
        until('battle native receipt',lambda:state('alice').get('chat_count',0)>=5)
        until('battle intro rendering',lambda:state('alice').get('in_battle') and state('alice').get('frame',0)>=before+300,10)
        assert state('alice')['in_battle'] and state('alice')['frame']>before
        screenshot('alice','battle-direct')
        open_chat('alice')
        x('type','--delay','20','--','Typing without covering Pokemon')
        screenshot('alice','battle-composer')
        x('key','Escape')
        record('Natural native wild battle keeps advancing while room/direct chat is delivered above the game image')
        for name,p in paths.items():
            assert hashlib.sha256(p['save'].read_bytes()).hexdigest()==initial_hashes[name]
        assert hashlib.sha256(args.seed.read_bytes()).hexdigest()==seed_hash
        record('Both private saves and the fixture seed remained byte-identical')
        report['ok']=True
    finally:
        for p in reversed(processes):
            if p.poll() is None: p.terminate()
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for lock in locks:lock.close()
        if server:server.close()
        for f in files:f.close()
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0


if __name__=='__main__':
    sys.exit(main())
