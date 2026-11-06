"""Prototype: two donor games, real in-memory LINK authority, file-only relay.

This is NOT a socket, TLS, real transport, or user gameplay test. The two games
have disposable copied saves; only the test build contains the fake adapter.
"""
import io,json,os,shutil,subprocess,sys,tempfile,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from world.server import WorldServer
from world.client import WorldClient
from world.expansion import serialize_peers

binary=Path(sys.argv[1]).resolve(strict=True)
save=Path(sys.argv[2]).resolve(strict=True)
startup='''wait-until callback2=MainCB2_Intro max 1000
wait-until callback2=MainCB2 max 20000
wait-until task_first=Task_TitleScreenPhase3 max 600
press START
wait-until task_first=Task_HandleMainMenuInput max 600
press A
wait-until callback2=CB2_Overworld max 1200
wait-until controls_locked=0 max 600
wait 60
'''
scripts={
'Bob':startup+'''hold DOWN
wait-until pos=5,10 max 120
release DOWN
wait 60
wait-until task_last=task_menu max 9000
wait 5
press UP
press A
wait-until in_battle=1 max 9000
dump entered_battle
wait 300
''',
'Alice':startup+'''wait 120
press DOWN
wait 30
mash A until task_last=task_menu max 3000
wait 5
press UP times 2
press A
wait-until in_battle=1 max 9000
dump entered_battle
wait 300
'''}
with tempfile.TemporaryDirectory(prefix='expansion-battle-file-test-') as tmp:
 root=Path(tmp);server=WorldServer(str(root/'unused.sock'),root/'world');names=('Alice','Bob');conns={};seq={n:0 for n in names};procs={};profiles={};logs={};offset={n:0 for n in names}
 for n in names:
  token=server.create_identity(n)['token'];c=dict(sock=object(),id=None,seq=-1,state=None,incoming=bytearray(),out=bytearray(),closing=False,born=time.monotonic(),admin=False)
  server._line(c,f'HELLO 1 {n} {token} SOCIAL'.encode());assert c.get('id')==n;c['out'].clear();conns[n]=c
 def start(n):
  p=root/n;p.mkdir();profiles[n]=p;(p/'out').mkdir();shutil.copyfile(save,p/'game.sav');(p/'in').touch();(p/'events').touch();(p/'peers.txt').write_text('EWPEERS 1\n');(p/'game.replay').write_text(scripts[n]);logs[n]=(p/'stderr').open('w')
  env=dict(os.environ,EW_EXPANSION_PRESENCE=str(p/'presence.json'),EW_EXPANSION_PEERS=str(p/'peers.txt'),EW_EXPERIMENTAL_EXPANSION_PEERS='1',EW_EXPERIMENTAL_EXPANSION_ACTIVITIES='1',EW_EXPANSION_LINK_CONFIG='fake-file-relay',EW_FAKE_LINK_IN=str(p/'in'),EW_FAKE_LINK_OUT=str(p/'events'),EW_ACTIVITY_DIAGNOSTIC='1')
  procs[n]=subprocess.Popen([str(binary),'--headless','--silent','--replay',str(p/'game.replay'),'--out',str(p/'out'),'--save',str(p/'game.sav'),'--rtc-offset',str(p/'clock.rtc'),'--rtc-fixed','1700000000'],env=env,stdout=subprocess.DEVNULL,stderr=logs[n])
 def deliver(out):
  for target,line in out:
   with (profiles[target]/'in').open('a') as f:f.write(line)
 def snapshot(name):
  c=conns[name];client=WorldClient.__new__(WorldClient);client.stream=io.BytesIO(server._snapshot(c).encode());client.control=False;client.social=True;client.trainer_id=name;return client.snapshot()
 try:
  start('Bob');deadline=time.monotonic()+180;last={};launched=False
  while time.monotonic()<deadline:
   for n in list(profiles):
    p=profiles[n]
    try: state=json.loads((p/'presence.json').read_text())
    except (OSError,ValueError):continue
    if state.get('field'):
     vals=[state[k] for k in ('group','num','x','y','facing','gfx')];ready=bool(state.get('ready'))
     seq[n]+=1;server._line(conns[n],('FIELD '+ ' '.join(map(str,[seq[n],*vals,int(ready)]))+' '+'0'*16+' '+'0'*16).encode())
     if conns[n].get('closing'):raise AssertionError('presence rejected')
     last[n]=state
    if n=='Bob' and not launched and state.get('field') and (state.get('x'),state.get('y'))==(5,10) and state.get('ready'):
     start('Alice');launched=True
   for n in list(profiles):
    c=conns[n]; data=serialize_peers(snapshot(n));p=profiles[n];temp=p/'peers.tmp';temp.write_text(data);temp.replace(p/'peers.txt');c['out'].clear()
   for n in list(profiles):
    fpath=profiles[n]/'events'
    with fpath.open() as f:
     f.seek(offset[n]);lines=f.readlines();offset[n]=f.tell()
    for line in lines:
     if not line.endswith('\n'):raise AssertionError('partial test file line')
     if line.startswith('L REJECT '): raise AssertionError(f'{n} declined the invitation in the test replay')
     messages=server.link_protocol.process(n,line.rstrip('\n').encode(),server._link_presence())
     if any(message.startswith('L ERROR ') for _,message in messages): raise AssertionError(f'coordinator rejected {n}: {messages}')
     deliver(messages)
   if launched and all((profiles[n]/'out'/'entered_battle.txt').exists() for n in names):
    print('Both donor games entered a link battle using file-only test relay and real in-memory LINK coordinator.');break
   if any(p.poll() is not None for p in procs.values()):raise AssertionError('donor exited before both entered battle')
   time.sleep(.01)
  else:raise AssertionError('two-donor battle timed out')
 except BaseException:
  for f in logs.values():f.flush()
  for n,p in profiles.items():print(n,'state=',last.get(n),'stderr=',(p/'stderr').read_text()[-5000:],'events=',(p/'events').read_text()[-5000:],file=sys.stderr)
  raise
 finally:
  for p in procs.values():
   if p.poll() is None:p.terminate()
  for p in procs.values():
   try:p.wait(timeout=3)
   except subprocess.TimeoutExpired:p.kill();p.wait()
  for f in logs.values():f.close()
