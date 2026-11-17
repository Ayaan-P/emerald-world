"""Opt-in two- or four-player team capture-the-flag on existing native maps.

Friendly position-attested play, not anti-cheat or native battle simulation.
"""
from contextlib import nullcontext
import json
import secrets
import sqlite3
from .field_relays import encoded
from .guilds import GuildError

ARENA = dict(id='petalburg_flags1', title='Petalburg Flag Duel', bases=[[0,0,10,10],[0,0,22,12]], limit=180, captures=3)


class FieldFlags:
    def __init__(self, server):
        self.s=server;self.p=server.relays;self.db=server.db;self.runs={}
        self.db.executescript('''CREATE TABLE IF NOT EXISTS flag_arenas(id TEXT PRIMARY KEY,document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS flag_results(run TEXT PRIMARY KEY,arena TEXT NOT NULL,players TEXT NOT NULL,scores TEXT NOT NULL);''')
        self.db.commit();self.publish(ARENA)

    def publish(self, arena, *, commit=True):
        import re
        if type(arena) is not dict or set(arena) not in ({'id','title','bases','limit','captures'},{'id','title','bases','limit','captures','starts'}):raise ValueError('Invalid flag arena.')
        if type(arena['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',arena['id']):raise ValueError('Invalid arena identifier.')
        if type(arena['title']) is not str or not 1<=len(arena['title'])<=50 or any(not 32<=ord(c)<=126 for c in arena['title']):raise ValueError('Invalid arena title.')
        if type(arena['limit']) is not int or not 30<=arena['limit']<=600 or type(arena['captures']) is not int or not 1<=arena['captures']<=5:raise ValueError('Invalid match limits.')
        if type(arena['bases']) is not list or len(arena['bases'])!=2:raise ValueError('Two bases required.')
        for point in arena['bases']:
            if type(point) is not list or len(point)!=4 or any(type(v) is not int for v in point):raise ValueError('Invalid base.')
            self.p.coords(*point)
            if tuple(point[:2]) in (self.s.cave_map,self.s.wilds_map):raise ValueError('Use standard maps.')
        a,b=arena['bases']
        if a[:2]!=b[:2] or abs(a[2]-b[2])+abs(a[3]-b[3])<8:raise ValueError('Bases need eight tiles separation on one map.')
        if 'starts' in arena:
            starts=arena['starts']
            if type(starts) is not list or len(starts)!=4:raise ValueError('Team arenas need four distinct alternating Red/Blue start pads.')
            for i,point in enumerate(starts):
                if type(point) is not list or len(point)!=4 or any(type(v) is not int for v in point):raise ValueError('Invalid team start.')
                self.p.coords(*point);home=arena['bases'][i%2]
                if point[:2]!=home[:2] or abs(point[2]-home[2])+abs(point[3]-home[3])>1:raise ValueError('Each start must be on or adjacent to its team base.')
            if len({tuple(p) for p in starts})!=4:raise ValueError('Team start pads must be distinct.')
        doc=encoded(arena)
        with self.db if commit else nullcontext():
            old=self.db.execute('SELECT document FROM flag_arenas WHERE id=?',(arena['id'],)).fetchone()
            if old and old[0]!=doc:raise ValueError('Arena identity is immutable.')
            if not old:
                if self.db.execute('SELECT count(*) FROM flag_arenas').fetchone()[0]>=64:raise ValueError('Arena capacity reached.')
                self.db.execute('INSERT INTO flag_arenas VALUES(?,?)',(arena['id'],doc))
        return dict(ok=True,id=arena['id'])

    def starts(self,arena):return arena.get('starts',arena['bases'])

    def current(self, name):return next((r for r in self.runs.values() if any(c['id']==name for c in r['members'])),None)
    def tell(self, run, lines):self.p._tell(run,lines)
    def end(self,run,text):self.runs.pop(run['id'],None);self.tell(run,[text])

    def status(self,run,c):
        slot=run['members'].index(c);i=slot%2;a=run['arena']
        return [a['title']+': '+run['phase']+'; start '+self.p._location(self.starts(a)[slot]), 'You are '+('Red' if i==0 else 'Blue')+'. Home: '+self.p._location(a['bases'][i]),
                'Enemy flag: '+self.p._location(a['bases'][1-i]),f"Score Red {run['scores'][0]} - Blue {run['scores'][1]}.",
                'Carrying enemy flag: '+('yes' if run['carrying'][slot] else 'no')+'. '+('Return home to re-arm.' if not run['armed'][slot] else 'Ready to steal.'),
                '/guild flag ready at home; /guild flag leave cancels.' if run['phase']=='lobby' else 'Tag an enemy carrier by moving within one tile.']

    def command(self,c,words):
        if len(words)==2 and words[0] in ('start','join') and getattr(self.s,'races',None) and self.s.races.current(c['id']):raise GuildError('Leave your current race first.')
        self.tick();name=c['id'];guild=self.s.guilds._require(name);now=self.p.clock()
        if not c.get('private_commands'):raise GuildError('Flag play needs the matched RC12 private-command client.')
        if words==['list']:return ['Flag arenas:']+[k+': '+json.loads(v)['title'] for k,v in self.db.execute('SELECT id,document FROM flag_arenas ORDER BY id LIMIT 8')]
        if words==['records']:
            rows=self.db.execute('SELECT arena,players,scores FROM flag_results WHERE EXISTS (SELECT 1 FROM json_each(players) WHERE value=?) ORDER BY rowid DESC LIMIT 5',(name,)).fetchall()
            return [a+': '+', '.join(n+' '+str(s) for n,s in ((n,json.loads(scores)[i%2]) for i,n in enumerate(json.loads(p)))) for a,p,scores in rows] or ['No completed flag matches yet.']
        r=self.current(name)
        if len(words)==2 and words[0]=='start':
            if r or self.p._current(name):raise GuildError('Leave your current field activity first.')
            if len(self.runs)>=32 or any(x['guild']==guild[0] for x in self.runs.values()):raise GuildError('A guild flag match is already open, or all slots are busy.')
            row=self.db.execute('SELECT document FROM flag_arenas WHERE id=?',(words[1],)).fetchone()
            if not row:raise GuildError('Unknown arena. Use /guild flag list.')
            r=dict(id=secrets.token_hex(6),guild=guild[0],arena=json.loads(row[0]),members=[c],phase='lobby',ready=set(),until=now+300,scores=[0,0],carrying=[False,False],armed=[True,True],cooldown=[0,0])
            count=len(self.starts(r['arena']));r.update(carrying=[False]*count,armed=[True]*count,cooldown=[0]*count)
            self.runs[r['id']]=r
            return self.status(r,c)+['Invite runners (alternating Red/Blue): /guild flag join '+r['id']]
        if len(words)==2 and words[0]=='join':
            if r or self.p._current(name):raise GuildError('Leave your current field activity first.')
            r=self.runs.get(words[1])
            if not r or r['guild']!=guild[0] or r['phase']!='lobby' or len(r['members'])>=len(self.starts(r['arena'])):raise GuildError('That invitation is unavailable to you.')
            r['members'].append(c);self.tell(r,['Runner joined. Stand on your assigned start pad and /guild flag ready.'])
            return self.status(r,c)
        if not r:return ['Use /guild flag list, start ARENA, join CODE, or records.']
        if not words or words==['status']:return self.status(r,c)
        if words==['leave']:self.end(r,'Flag match cancelled by a player. No result recorded.');return ['You left the flag match.']
        if words==['ready']:
            if r['phase']!='lobby':raise GuildError('Match already started.')
            i=r['members'].index(c)
            if not self.p._at(c,self.starts(r['arena'])[i],now):raise GuildError('Stand ready on your home base first.')
            r['ready'].add(name)
            if len(r['ready'])==len(self.starts(r['arena'])):r['phase']='countdown';r['started']=now+3;self.tell(r,['Flag match starts in three seconds. Stay at home.'])
            return ['Ready.']
        raise GuildError('Use /guild flag status, ready, leave or records.')

    def finish(self,r):
        try:
            with self.db:self.db.execute('INSERT INTO flag_results VALUES(?,?,?,?)',(r['id'],r['arena']['id'],encoded([c['id'] for c in r['members']]),encoded(r['scores'])))
        except sqlite3.Error:self.end(r,'Could not save match. No result recorded.');return
        a,b=r['scores'];winner='Draw' if a==b else ('Red wins' if a>b else 'Blue wins')
        self.end(r,f'{winner}: {a}-{b}. Saved privately. Start a new match to play again.')

    def tick(self):
        now=self.p.clock()
        for r in list(self.runs.values()):
            a=r['arena'];members=r['members']
            if any(self.s.peers.get(c['id']) is not c or c.get('closing') or self.s.guilds._member(c['id']) is None or self.s.guilds._member(c['id'])[0]!=r['guild'] for c in members):
                self.end(r,'Flag match cancelled: opponent disconnected or left the guild.');continue
            if r['phase']=='lobby':
                if now>r['until']:self.end(r,'Flag invitation expired.')
                continue
            if r['phase']=='countdown':
                if not all(self.p._at(c,self.starts(a)[i],now) for i,c in enumerate(members)):
                    r['phase']='lobby';r['ready'].clear();self.tell(r,['Countdown cancelled. Return home and ready again.']);continue
                if now<r['started']:continue
                r['phase']='playing';self.tell(r,['Go! Steal the enemy flag, then return home while your own flag is home.'])
            if any(c.get('state_time') is None or now-c['state_time']>10 for c in members):self.end(r,'Flag match cancelled: missing player presence.');continue
            if now-r['started']>=a['limit']:self.finish(r);continue
            active=[self.p._fresh(c,now) and c['state'][:2]==a['bases'][0][:2] for c in members]
            for i in range(len(members)):
                if not active[i] and r['carrying'][i]:
                    r['carrying'][i]=False;r['armed'][i]=False
                    self.tell(r,['Flag returned: carrier left active field play. Return home to re-arm.'])
                if active[i] and not r['armed'][i] and now>=r['cooldown'][i] and self.p._at(members[i],a['bases'][i%2],now):r['armed'][i]=True;self.tell(r,[members[i]['id']+' is re-armed.'])
            # Resolve all opposing tags against the same observed positions first.
            tagged=set()
            for i,p in enumerate(members):
                for j,q in enumerate(members):
                    if i%2==j%2 or not active[i] or not active[j]:continue
                    if abs(p['state'][2]-q['state'][2])+abs(p['state'][3]-q['state'][3])<=1 and r['carrying'][i]:tagged.add(i)
            for i in sorted(tagged):
                r['carrying'][i]=False;r['armed'][i]=False;r['cooldown'][i]=now+3
                self.tell(r,[members[i]['id']+' tagged! Flag returned. Go home to re-arm.'])
            for i in range(len(members)):
                if not active[i] or not r['armed'][i]:continue
                team=i%2
                # Exactly one carrier per team: there is only one enemy flag.
                if not any(r['carrying'][j] for j in range(team,len(members),2)) and self.p._at(members[i],a['bases'][1-team],now):
                    r['carrying'][i]=True;self.tell(r,[members[i]['id']+' stole the enemy flag!'])
                if r['carrying'][i] and not any(r['carrying'][j] for j in range(1-team,len(members),2)) and self.p._at(members[i],a['bases'][team],now):
                    r['carrying'][i]=False;r['scores'][team]+=1
                    self.tell(r,[members[i]['id']+f" captured! Red {r['scores'][0]} - Blue {r['scores'][1]}."])
            if max(r['scores'])>=a['captures']:self.finish(r)
