"""Launch two independently controlled native clients on a dedicated nested X display.

This is a local playtest harness, not an internet relay. Run Xephyr :93 first.
Only a new explicit save copy is accepted for initial trainer creation.
"""
import argparse
import json
import signal
import subprocess
import threading
import time
from pathlib import Path
from .launcher import REPO, prepare_profile, game_command
from .server import WorldServer


def run(state_dir, binary, seed_save, display=':93'):
    root = Path(state_dir).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    transport = root/'transport'; transport.mkdir(exist_ok=True, mode=0o700)
    server = WorldServer(str(transport/'world.sock'), str(root)).start()
    stop = threading.Event()
    clients = []
    handles = []
    def stopping(*args): stop.set()
    for sig in (signal.SIGINT,signal.SIGTERM): signal.signal(sig,stopping)
    try:
        for name,direction,frames in [('alice','LEFT',16),('bob','RIGHT',32)]:
            paths = prepare_profile(root,name,seed_save if not (root/'trainers'/name/'game.sav').exists() else None)
            bootstrap = paths['profile']/'bootstrap.txt'
            steps=[(300,'-'),(2,'START'),(140,'-'),(2,'START'),(220,'-'),(2,'A'),(220,'-'),(2,'A'),(240,'-'),(frames,direction),(24,'-'),(1,'DOWN'),(24,'-')]
            bootstrap.write_text(''.join(f'{n} {key}\n' for n,key in steps))
            command = game_command(binary,root,paths,display)
            command+=['--world-input',str(bootstrap),'--world-shot',str(paths['profile']/'bootstrap.ppm')]
            (paths['profile']/'graphical-command.json').write_text(json.dumps(command,indent=2))
            output=(paths['profile']/'graphical.log').open('w');handles.append(output)
            proc=subprocess.Popen(command,stdout=output,stderr=subprocess.STDOUT)
            clients.append((name,proc,paths))
        deadline=time.monotonic()+60
        while not stop.is_set():
            for name,proc,paths in clients:
                if proc.poll() is not None: raise RuntimeError(f'{name} native client exited {proc.returncode}; see {paths["profile"]}/graphical.log')
            snapshot=server.inspect()
            if len(snapshot['players'])==2 and all(p.get('ready') for p in snapshot['players']):
                telemetry=[]
                for name,proc,paths in clients:
                    try: telemetry.append(json.loads(paths['telemetry'].read_text()))
                    except (OSError,ValueError): break
                if len(telemetry)==2 and all(t['peers'] and t['peers'][0]['visible'] for t in telemetry):
                    manifest={'ready':True,'display':display,'state_dir':str(root),'socket':str(transport/'world.sock'),'clients':[{'trainer':n,'pid':proc.pid,'profile':str(paths['profile'])} for n,proc,paths in clients],'snapshot':snapshot,'telemetry':telemetry}
                    (root/'graphical-ready.json').write_text(json.dumps(manifest,indent=2))
                    print('GRAPHICAL_WORLD_READY '+str(root/'graphical-ready.json'),flush=True)
                    break
            if time.monotonic()>deadline: raise TimeoutError('native graphical clients did not become ready')
            stop.wait(.1)
        while not stop.wait(.25):
            if any(proc.poll() is not None for _,proc,_ in clients): break
    finally:
        for _,proc,_ in clients:
            if proc.poll() is None: proc.terminate()
        for _,proc,_ in clients:
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
        for output in handles:output.close()
        server.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state-dir',required=True,type=Path)
    p.add_argument('--seed-save',required=True,type=Path)
    p.add_argument('--binary',type=Path,default=REPO/'build/pokeemerald64')
    p.add_argument('--display',default=':93')
    a=p.parse_args();run(a.state_dir,a.binary.resolve(),a.seed_save.resolve(),a.display)

if __name__=='__main__':main()
