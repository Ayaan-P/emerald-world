"""Versioned new native maze geometry, not imported e-Reader saves or victories."""
import hashlib,json,re

def generate(seed,floor):
 if type(seed) is not int or not 0<=seed<=4095 or type(floor) is not int or not 0<=floor<=3:raise ValueError('Use seed 0..4095 and floor 0..3')
 rng=(((seed+1)*0x9e3779b9)^((floor+1)*0x85ebca6b))&0xffffffff or 1
 cells=[0]*256;stack=[0];seen={0};cells[17]=1
 while stack:
  cur=stack[-1];cx,cy=cur%7,cur//7;choices=[]
  if cx<6 and cur+1 not in seen:choices.append(cur+1)
  if cy>0 and cur-7 not in seen:choices.append(cur-7)
  if cx>0 and cur-1 not in seen:choices.append(cur-1)
  if cy<6 and cur+7 not in seen:choices.append(cur+7)
  if not choices:stack.pop();continue
  rng^=(rng<<13)&0xffffffff;rng^=rng>>17;rng^=(rng<<5)&0xffffffff
  next=choices[rng%len(choices)];nx,ny=next%7,next//7
  cells[(cy+ny+1)*16+cx+nx+1]=cells[(2*ny+1)*16+2*nx+1]=1;seen.add(next);stack.append(next)
 for index in (1,13,11*16+14,13*16+14):cells[index]=1
 return [''.join('.' if c else '#' for c in cells[y*16:(y+1)*16]) for y in range(16)]
def preview(seed):return dict(seed=seed,generator=1,floors=[dict(index=f+1,rows=generate(seed,f),entrances=[[1,0],[13,0]],trainers=[[14,11],[14,13]]) for f in range(4)],limits='Generated intended native layout, not player exploration, victory or verified rendering. Stock selected-mode trainers remain; custom prizes/best-time writes are suppressed.')
def setup(db):db.execute('CREATE TABLE IF NOT EXISTS maze_courses(id TEXT PRIMARY KEY,actor TEXT,seed INTEGER,revision TEXT,active INTEGER)')
def catalog(server):
 setup(server.db)
 return [dict(id=i,actor=a,seed=s,revision=r) for i,a,s,r in server.db.execute('SELECT id,actor,seed,revision FROM maze_courses WHERE active=1 ORDER BY id')]
def publish(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id','seed'} or type(args['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',args['id']) or type(args['seed']) is not int or not 0<=args['seed']<=4095:raise ValueError('Use id and seed 0..4095')
 ident,seed=args['id'],args['seed'];revision=hashlib.sha256(f'hillmaze1:{seed}'.encode()).hexdigest()[:16]
 old=server.db.execute('SELECT actor,seed,active FROM maze_courses WHERE id=?',(ident,)).fetchone()
 if old and old[:2]!=(actor,seed):raise ValueError('Course identity is immutable')
 if (not old or not old[2]) and len(catalog(server))>=32:raise ValueError('Close a course first')
 server.db.execute('INSERT OR REPLACE INTO maze_courses VALUES(?,?,?,?,1)',(ident,actor,seed,revision))
 return dict(outcome='procedural_maze_course_published',id=ident,revision=revision,**preview(seed))
def close(server,actor,row,args):
 setup(server.db)
 if set(args)!={'id'} or type(args['id']) is not str:raise ValueError('Use course id')
 old=server.db.execute('SELECT actor FROM maze_courses WHERE id=?',(args['id'],)).fetchone()
 if not old or old[0]!=actor:raise ValueError('Only own course may close')
 server.db.execute('UPDATE maze_courses SET active=0 WHERE id=?',(args['id'],))
 return dict(outcome='maze_closed_to_new_downloads',id=args['id'],limits='Already armed or admitted personal runs retain geometry.')
def tool(server,actor,row,args):
 if set(args)!={'operation','value'} or type(args['value']) is not str:raise ValueError('Use operation and string value')
 op,value=args['operation'],args['value']
 if op=='inspect' and value=='':return dict(outcome='native_maze_catalog',generator=1,seed_range=[0,4095],courses=catalog(server))
 if op=='preview' and re.fullmatch('[0-9]{1,4}',value):return preview(int(value))
 if op=='close':return close(server,actor,row,dict(id=value))
 if op=='publish':
  try:value=json.loads(value)
  except ValueError:raise ValueError('Use JSON {id,seed}') from None
  if type(value) is not dict:raise ValueError('Use JSON {id,seed}')
  return publish(server,actor,row,value)
 raise ValueError('Use inspect, preview, publish or close')
def handle(server,conn,raw):
 setup(server.db);seq=0
 try:
  f=raw.decode('ascii').split(' ')
  if len(f)!=5 or f[:2]!=['MC','GET'] or not re.fullmatch('[1-9][0-9]{0,9}',f[2]):raise ValueError()
  seq=int(f[2])
  if seq>0xffffffff or not conn['presence'].get('campaign_run') or server.link_protocol.busy(conn['id']):raise ValueError()
  r=server.db.execute('SELECT seed FROM maze_courses WHERE id=? AND revision=? AND active=1',(f[3],f[4])).fetchone()
  if not r:raise ValueError()
  return f'MC MAZE {seq} {r[0]}\n'
 except (ValueError,KeyError,UnicodeError):return f'MC ERROR {seq}\n'
def command(server,conn,words):
 from .guilds import GuildError
 if not words:return ['Procedural Hill mazes: /guild mazes page 0; show ID previews.','Optional next NEW native Hill run. No custom-course vanilla prizes or best-time updates.']
 rows=catalog(server)
 if len(words)==2 and words[0]=='page' and words[1].isdigit() and len(words[1])<4:
  rows=rows[int(words[1])*3:int(words[1])*3+3]
  return [line for r in rows for line in (f"{r['id']} by {r['actor']}: four generated maze floors",f"/maze load {r['id']} {r['revision']} yes")]+([] if rows else ['No maze courses.'])
 if len(words)==2 and words[0]=='show':
  r=next((r for r in rows if r['id']==words[1]),None)
  if not r:raise GuildError('Course unavailable')
  return [f"Seed {r['seed']}, generator 1. Native selected-mode opponents; no guaranteed win or reward.",'Two side-alcove trainers per floor; real entrances remain connected.']
 raise GuildError('Use /guild mazes page N or show ID')
