"""Completed native Cut -> durable walkable terrain. Client report, not attestation."""
import hashlib,re,time
from .shared_terrain import validate

def wire(server,conn,raw):
 nonce='0'
 try:
  t=raw.decode('ascii').split()
  if len(t)!=7 or t[:2]!=['PG','CUT']:raise ValueError()
  candidate,identity,snapshot,center,cells=t[2:]
  if not re.fullmatch(r'[1-9][0-9]{0,9}',candidate) or int(candidate)>4294967295:raise ValueError()
  nonce=candidate
  if not re.fullmatch(r'[0-9a-f]{64}',identity) or not re.fullmatch(r'[0-9a-f]{64}',snapshot):raise ValueError()
  if not re.fullmatch(r'[0-9a-f]{4}',center) or not re.fullmatch(r'(?:[0-9a-f]{4}){1,25}',cells):raise ValueError()
  cx,cy=bytes.fromhex(center);points=list(zip(*[iter(bytes.fromhex(cells))]*2))
  if len(set(points))!=len(points) or any(abs(x-cx)>2 or abs(y-cy)>2 for x,y in points):raise ValueError()
  with server.lock:
   p=conn['presence'];state=p.get('state');cave=server.shared_cave
   if (not cave or cave.version!=9 or cave.identity!=identity or not server.archive_generated_areas
       or not state or time.monotonic()-p.get('state_time',0)>5
       or not p.get('in_generated_cave') or p.get('region_cave') or p.get('cave_ack')!=identity
       or p.get('cave_transfer_pending') or not p.get('cave_terrain')
       or tuple(state[:2])!=server.wilds_map or tuple(state[2:4])!=(cx,cy)):raise ValueError()
   revision,payload=server._active_terrain()
   if hashlib.sha256(payload).hexdigest()!=snapshot:raise ValueError()
   overlay=validate(cave,payload)
   for x,y in points:
    baseline=1 if cave._rows[y][x]==ord('.') and (x*13+y*7)%5 else 0
    if overlay.get((x,y),baseline)!=1:raise ValueError()
   # Same authority lock spans comparison and existing transaction/broadcast.
   # This existing path validates endpoints/NPCs/capacity, records actual delta,
   # and commits before delivery. No new flags, rewards, identities or PP.
   result=server.set_shared_terrain(identity,[dict(x=x,y=y,terrain='grass') for x,y in points])
   return f"PG COMMITTED {nonce} {result['revision']}\n"
 except (ValueError,KeyError,TypeError,IndexError,UnicodeError):
  return f'PG REJECTED {nonce}\n'
