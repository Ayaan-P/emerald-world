"""Consented brackets, existing native PvP and concordant client outcome reports.

No closure is a victory, no authority simulation, no party or save mutation.
"""
import json,re,secrets
IDENT=re.compile(r'[A-Za-z0-9_-]{1,24}\Z')
def setup(s):
 s.db.execute('CREATE TABLE IF NOT EXISTS player_tournaments(id TEXT PRIMARY KEY,actor TEXT,document TEXT)')
 s.db.execute('CREATE TABLE IF NOT EXISTS tournament_attempts(wire TEXT PRIMARY KEY,tournament TEXT,players TEXT,lineages TEXT,reports TEXT)')
 if not getattr(s,'_tournaments_started',False):
  with s.db:
   for key,raw in s.db.execute('SELECT id,document FROM player_tournaments').fetchall():
    d=json.loads(raw)
    for m in d['matches']:
     if m['status'] in ('offering','running','interrupted'):m['status']='recovered';m['retry']=[]
    save(s,key,d)
  s._tournaments_started=True

def save(s,key,d):s.db.execute('UPDATE player_tournaments SET document=? WHERE id=?',(json.dumps(d,sort_keys=True),key))
def get(s,key):
 row=s.db.execute('SELECT document FROM player_tournaments WHERE id=?',(key,)).fetchone()
 if not row:raise ValueError('Unknown tournament')
 return json.loads(row[0])
def public(key,d):
 return dict(id=key,title=d['title'],size=d['size'],status=d['status'],entrants=[p['trainer'] for p in d['entrants']],matches=[{k:m.get(k) for k in ('players','status','winner')} for m in d['matches']],champion=d.get('champion'),basis='concordant_session_bound_native_client_reports',limits='Public entrants and bracket. Outcomes are matching client reports, not authority-verified victories. No save rewards or shared progress.')
def catalog(s):
 setup(s);return [public(k,json.loads(raw)) for k,raw in s.db.execute('SELECT id,document FROM player_tournaments ORDER BY id')]
def publish(s,actor,row,args):
 setup(s)
 if set(args)!={'id','title','size'} or type(args['id'])is not str or not IDENT.fullmatch(args['id']) or type(args['title'])is not str or not 1<=len(args['title'])<=60 or any(not 32<=ord(c)<=126 for c in args['title']) or type(args['size'])is not int or args['size'] not in (2,4,8):raise ValueError('Use stable ID, public title <=60 ASCII, and 2/4/8 entrants')
 if s.db.execute('SELECT 1 FROM player_tournaments WHERE id=?',(args['id'],)).fetchone():raise ValueError('Tournament identity already used')
 if sum(t['status'] not in ('complete','cancelled') for t in catalog(s))>=16:raise ValueError('Sixteen active tournament limit')
 d=dict(title=args['title'],size=args['size'],status='open',entrants=[],matches=[],round=0)
 s.db.execute('INSERT INTO player_tournaments VALUES(?,?,?)',(args['id'],actor,json.dumps(d)))
 s.revision=s.memory.append('player_tournament_published',dict(character_id=actor,tournament=args['id'],title=args['title'],size=args['size'],basis='optional_native_pvp_bracket',limits='Invitation only. Players explicitly join and accept each native battle.'))
 return dict(outcome='tournament_opened',tournament=args['id'])
def match(d,trainer):
 return next((m for m in d['matches'] if trainer in m['players'] and m['status']!='resolved'),None)
def next_round(d,players):
 d['round']+=1
 for i in range(0,len(players),2):d['matches'].append(dict(players=players[i:i+2],status='ready',winner=None,wire=None,retry=[],handshake=False,round=d['round']))
def lineage(s,trainer):return s.peers.get(trainer,{}).get('campaign_run')
def command(s,conn,words):
 from .guilds import GuildError
 setup(s);who=conn['id']
 if not words:return ['Public native PvP brackets:']+[f"{t['id']}: {t['title']} ({t['status']}, {len(t['entrants'])}/{t['size']})" for t in catalog(s)]+['/guild tournament show ID; join ID yes publishes your name and match results to ALL world players/agents.']
 try:
  if len(words)<2:raise ValueError('Use show/join/fight/retry/leave ID')
  op,key=words[:2];d=get(s,key)
  if op=='show' and len(words)==2:return [key+': '+d['title']+' ['+d['status']+']', 'Entrants: '+', '.join(e['trainer'] for e in d['entrants'])]+[' vs '.join(m['players'])+': '+m['status']+(' winner '+m['winner'] if m['winner'] else '') for m in d['matches']]+['Singles, own party; no normalization. fight ID requests normal native invitation.']
  if op=='join' and words[2:]!=['yes']:return ['join ID yes publishes your trainer name and session-bound match results to ALL world players/agents. Own party and save progression stay independent.']
  with s.db:
   if op=='join':
    run=lineage(s,who)
    if not run or d['status']!='open' or any(e['trainer']==who for e in d['entrants']):raise ValueError('Open bracket and active save required; no duplicate entry')
    for t in catalog(s):
     if t['status'] not in ('complete','cancelled') and who in t['entrants']:raise ValueError('Already entered an active tournament')
    d['entrants'].append(dict(trainer=who,lineage=run))
    if len(d['entrants'])==d['size']:d['status']='playing';next_round(d,[e['trainer'] for e in d['entrants']])
    save(s,key,d);return ['Joined public bracket. /guild tournament show '+key]
   if op=='leave' and len(words)==2:
    if not any(e['trainer']==who for e in d['entrants']):raise ValueError('Not an entrant')
    if d['status']=='playing':
     d['status']='cancelled'
     for m in d['matches']:
      if m['status']!='resolved':m['status']='cancelled'
     save(s,key,d);return ['Withdrew consent: bracket cancelled without a winner. Any existing native battle is separate.']
    if d['status']!='open':raise ValueError('Tournament already ended')
    d['entrants']=[e for e in d['entrants'] if e['trainer']!=who];save(s,key,d);return ['Left waiting bracket.']
   m=match(d,who)
   if d['status']!='playing' or not m or next(e['lineage'] for e in d['entrants'] if e['trainer']==who)!=lineage(s,who):raise ValueError('No current match for this save')
   if op=='retry' and words[2:]==['yes']:
    if m['status'] not in ('disputed','interrupted','recovered','draw','offering'):raise ValueError('Match not awaiting retry')
    if any(s.link_protocol.busy(p) for p in m['players']):raise ValueError('Finish existing native session before retrying')
    if who not in m['retry']:m['retry'].append(who)
    if len(m['retry'])==2:m.update(status='ready',wire=None,retry=[],handshake=False)
    save(s,key,d);return ['Retry consent recorded. Both participants must agree; no result invented.']
   if op=='fight' and len(words)==2:
    if m['status']!='ready':raise ValueError('Match is not ready; inspect bracket/retry state')
    other=next(p for p in m['players'] if p!=who);channel=s.link_channels.get(who)
    if not channel or not s.link_channels.get(other):raise ValueError('Both native link clients must be connected')
    if any(lineage(s,e['trainer'])!=e['lineage'] for e in d['entrants'] if e['trainer'] in m['players']):raise ValueError('Both entrants must use their enrolled saves')
    m['status']='offering';save(s,key,d)
    # Normal server handler retains proximity, generated-area and activity guards.
    s._link_line(channel,f'L OFFER 1 {other}'.encode())
    current=get(s,key);pending=match(current,who)
    if pending and pending['status']=='offering' and pending['wire'] is None:
     pending['status']='ready';save(s,key,current);return ['Invitation unavailable. Meet nearby in ordinary Hoenn with both native clients ready.']
    return ['Native invitation requested. Opponent must accept; inspect the normal native activity UI.']
   raise ValueError('Use show/join/fight/retry/leave ID; join and retry require yes')
 except (ValueError,StopIteration) as e:raise GuildError(str(e)) from None

def observe(s,trainer,line):
 """Called after a current native coordinator message is queued; never invents a result."""
 f=line.split()
 if len(f)<3 or f[0]!='L':return None
 handshake=len(f)>=4 and f[1:3]==['COMMIT','2']
 if not handshake and f[1] not in ('OFFER','ADMIT','ABORT'):return None
 setup(s)
 wire=f[3] if handshake else f[2]
 with s.db:
  for key,raw in s.db.execute('SELECT id,document FROM player_tournaments').fetchall():
   d=json.loads(raw)
   for m in d['matches']:
    if f[1]=='OFFER' and len(f)==5 and f[3]=='1' and m['status']=='offering' and set(m['players'])=={trainer,f[4]} and not m['wire']:
     m['wire']=wire
     lines={e['trainer']:e['lineage'] for e in d['entrants'] if e['trainer'] in m['players']}
     s.db.execute('INSERT INTO tournament_attempts VALUES(?,?,?,?,?)',(wire,key,json.dumps(m['players']),json.dumps(lines),'{}'));save(s,key,d)
    elif m['wire']==wire and trainer in m['players']:
     if handshake and m['status']=='running':m['handshake']=True;save(s,key,d)
     if f[1]=='ADMIT' and m['status'] in ('offering','running'):
      m['status']='running';save(s,key,d);return f'U WATCH {wire}\n'
     if f[1]=='ABORT' and m['status'] in ('offering','running'):
      m['status']='interrupted';save(s,key,d)
 return None

def result(s,conn,raw):
 setup(s);wire='0'
 try:
  f=raw.decode('ascii').split(' ')
  if len(f)!=4 or f[:2]!=['U','RESULT'] or not re.fullmatch('[0-9]{1,20}',f[2]) or f[3] not in ('1','2','3'):raise ValueError('shape')
  wire=f[2];who=conn['id'];outcome=int(f[3])
  with s.db:
   row=s.db.execute('SELECT tournament,players,lineages,reports FROM tournament_attempts WHERE wire=?',(wire,)).fetchone()
   if not row:raise ValueError('attempt')
   key,players,lines,reports=row;players=json.loads(players);lines=json.loads(lines);reports=json.loads(reports)
   if who not in players or conn['presence'].get('campaign_run')!=lines[who]:raise ValueError('entrant/save')
   if who in reports:
    if reports[who]!=outcome:raise ValueError('conflicting replay')
    return f'U ACK {wire}\n'
   d=get(s,key);m=next((m for m in d['matches'] if m['wire']==wire),None)
   if d['status']!='playing' or not m or not m.get('handshake') or m['status'] not in ('running','interrupted'):raise ValueError('inactive attempt')
   reports[who]=outcome;s.db.execute('UPDATE tournament_attempts SET reports=? WHERE wire=?',(json.dumps(reports),wire))
   if len(reports)==2:
    a,b=players;pair=(reports[a],reports[b])
    if pair in ((1,2),(2,1)):
     winner=a if pair[0]==1 else b;m.update(status='resolved',winner=winner)
     current=[x for x in d['matches'] if x['round']==d['round']]
     if all(x['status']=='resolved' for x in current):
      winners=[x['winner'] for x in current]
      if len(winners)==1:d.update(status='complete',champion=winners[0])
      else:next_round(d,winners)
     s.revision=s.memory.append('player_tournament_match_reported',dict(tournament=key,players=players,winner=winner,basis='concordant_session_bound_native_client_reports',limits='Both enrolled clients reported complementary outcomes. Not authority-verified victory; no save/reward changes.'))
    else:m['status']='draw' if pair==(3,3) else 'disputed'
    save(s,key,d)
   return f'U ACK {wire}\n'
 except (ValueError,KeyError,UnicodeError):return f'U ERROR {wire}\n'

def cancel(s,actor,row,args):
 setup(s)
 if set(args)!={'id'}:raise ValueError('Supply own tournament ID')
 owner=s.db.execute('SELECT actor FROM player_tournaments WHERE id=?',(args['id'],)).fetchone()
 if not owner or owner[0]!=actor:raise ValueError('Only the organizer may cancel this tournament')
 d=get(s,args['id'])
 if d['status'] in ('complete','cancelled'):raise ValueError('Tournament already ended')
 d['status']='cancelled'
 for m in d['matches']:
  if m['status']!='resolved':m['status']='cancelled'
 save(s,args['id'],d)
 s.revision=s.memory.append('player_tournament_cancelled',dict(character_id=actor,tournament=args['id'],limits='Bracket ended without assigning new winners. Existing native battles are not terminated.'))
 return dict(outcome='tournament_cancelled',tournament=args['id'])
