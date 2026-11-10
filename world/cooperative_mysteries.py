"""Two-to-four-role field investigations. Private clues require fresh station occupancy.

This coordinates existing native walking/chat, not new map geometry or rewards.
Locations remain client reports under the existing world's trust model.
"""
from contextlib import nullcontext
import json
import re
import secrets
import sqlite3
import time


def dump(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
def label(value,limit=110):
    if type(value) is not str or not 1<=len(value)<=limit or any(ord(c)<32 or ord(c)>126 for c in value):raise ValueError('Use bounded plain ASCII puzzle text.')


def validate(pack,coords):
    if type(pack) is not dict or set(pack)!={'id','title','roles','stages','ending'} or len(dump(pack))>16384:raise ValueError('Invalid mystery pack.')
    if type(pack['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',pack['id']):raise ValueError('Invalid mystery identifier.')
    label(pack['title'],60);label(pack['ending'])
    if type(pack['roles']) is not list or not 2<=len(pack['roles'])<=4:raise ValueError('Mysteries need two to four distinct roles.')
    for role in pack['roles']:label(role,24)
    if len(set(pack['roles']))!=len(pack['roles']):raise ValueError('Roles must differ.')
    if type(pack['stages']) is not list or not 1<=len(pack['stages'])<=12:raise ValueError('Mysteries need 1..12 stages.')
    for stage in pack['stages']:
        if type(stage) is not dict or set(stage)!={'title','stations','answer','result'}:raise ValueError('Invalid mystery stage.')
        label(stage['title'],60);label(stage['result'])
        if type(stage['answer']) is not str or not re.fullmatch('[A-Z0-9]{2,16}',stage['answer']):raise ValueError('Answers must be 2..16 uppercase letters or digits.')
        stations=stage['stations']
        if type(stations) is not list or len(stations)!=len(pack['roles']):raise ValueError('Each role needs one station.')
        for station in stations:
            if type(station) is not dict or set(station)!={'at','clue'}:raise ValueError('Invalid station.')
            at=station['at']
            if type(at) is not list or len(at)!=4 or any(type(n) is not int for n in at):raise ValueError('Invalid station position.')
            coords(*at);label(station['clue'])
        if len({tuple(s['at']) for s in stations})!=len(stations):raise ValueError('Partners need different stations.')
    return pack


class Mysteries:
    def __init__(self,server,coords,freshness):
        self.s=server;self.db=server.db;self.coords=coords;self.freshness=freshness
        from .private_mystery_partners import setup
        setup(self.db)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS mystery_packs(id TEXT PRIMARY KEY,document TEXT);
        CREATE TABLE IF NOT EXISTS mystery_runs(id TEXT PRIMARY KEY,pack TEXT,stage INTEGER,status TEXT);
        CREATE TABLE IF NOT EXISTS mystery_members(run TEXT,role INTEGER,trainer TEXT,PRIMARY KEY(run,role),UNIQUE(run,trainer));
        CREATE TABLE IF NOT EXISTS mystery_lineages(run TEXT,trainer TEXT,lineage TEXT,PRIMARY KEY(run,trainer));
        CREATE TABLE IF NOT EXISTS mystery_clues(run TEXT,stage INTEGER,role INTEGER,PRIMARY KEY(run,stage,role));
        CREATE TABLE IF NOT EXISTS mystery_solved(run TEXT,stage INTEGER,PRIMARY KEY(run,stage));
        ''');self.db.commit()

    def publish(self,pack):
        validate(pack,self.coords)
        for stage in pack['stages']:
            if any(tuple(s['at'][:2]) in (self.s.cave_map,self.s.wilds_map) for s in stage['stations']):raise ValueError('Mysteries require stable standard maps.')
        document=dump(pack)
        with self.db:
            old=self.db.execute('SELECT document FROM mystery_packs WHERE id=?',(pack['id'],)).fetchone()
            if old and old[0]!=document:raise ValueError('Mystery identity already names different content.')
            if not old:
                if self.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0]>=64:raise ValueError('Mystery capacity reached.')
                self.db.execute('INSERT INTO mystery_packs VALUES(?,?)',(pack['id'],document))
        return dict(ok=True,id=pack['id'])

    def _canonical(self,pack):
        table=self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='canonical_investigations'").fetchone()
        return bool(table and self.db.execute('SELECT 1 FROM canonical_investigations WHERE id=?',(pack,)).fetchone())

    def _lineage(self,trainer):
        value=(self.s.peers.get(trainer) or {}).get('core_active_run')
        return value if type(value) is str and re.fullmatch('[0-9a-f]{32}',value) else None

    def _bound(self,run,trainer,pack):
        if not self._canonical(pack):return True
        lineage=self._lineage(trainer)
        return bool(lineage and self.db.execute('SELECT 1 FROM mystery_lineages WHERE run=? AND trainer=? AND lineage=?',(run,trainer,lineage)).fetchone())

    def _bind(self,run,trainer,pack):
        if not self._canonical(pack):return
        lineage=self._lineage(trainer)
        if not lineage:raise ValueError('Connect this save to canonical history before joining this cast investigation.')
        self.db.execute('INSERT INTO mystery_lineages VALUES(?,?,?)',(run,trainer,lineage))

    def _current(self,trainer,active=True):
        rows=self.db.execute('''SELECT r.id,r.pack,r.stage,r.status,m.role FROM mystery_runs r
          JOIN mystery_members m ON m.run=r.id WHERE m.trainer=? '''+
          ("AND r.status IN ('waiting','active') " if active else '')+'ORDER BY r.rowid DESC',(trainer,)).fetchall()
        return next((row for row in rows if self._bound(row[0],trainer,row[1])),None)

    @staticmethod
    def _role(value,pack):
        if value not in tuple(str(i+1) for i in range(len(pack['roles']))):raise ValueError('Choose a displayed role number.')
        return int(value)-1

    def _pack(self,key):
        row=self.db.execute('SELECT document FROM mystery_packs WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Unknown mystery.')
        return json.loads(row[0])

    def _at(self,trainer,position,run=None,pack=None):
        if run and not self._bound(run,trainer,pack):return False
        if trainer.startswith("@npc:"):
            from .private_mystery_partners import at
            return at(self.s,trainer,position)
        peer=self.s.peers.get(trainer)
        if not peer or peer.get('closing'):return False
        state=peer.get('state');updated=peer.get('state_time')
        return bool(state and state[6] and state[:4]==position and updated is not None and 0<=time.monotonic()-updated<=self.freshness)

    def completed(self,trainer,pack):
        return any(self._bound(run,trainer,pack) for (run,) in self.db.execute("SELECT r.id FROM mystery_runs r JOIN mystery_members m ON m.run=r.id WHERE r.pack=? AND m.trainer=? AND r.status='completed'",(pack,trainer)))

    def status(self,trainer):
        run=self._current(trainer) or self._current(trainer,False)
        if not run:return ['Use /mystery list, /mystery start PACK, or /mystery join CODE.']
        rid,key,index,state,role=run;pack=self._pack(key)
        if state=='completed':return [pack['ending'],'Mystery completed. Read /story here for unlocked opportunities.']
        if state=='cancelled':return ['This mystery was ended by a participant.']
        lines=[pack['title']+' - '+pack['roles'][role]]
        if state=='waiting':
            occupied={r for r, in self.db.execute('SELECT role FROM mystery_members WHERE run=?',(rid,))}
            lines+=['Invite partners: /mystery join '+rid, 'Open roles: '+', '.join(str(i+1)+' '+name for i,name in enumerate(pack['roles']) if i not in occupied)]
        station=pack['stages'][index]['stations'][role];at=station['at'];place=self.coords(*at)['name']
        lines += [f"Stage {index+1}: {pack['stages'][index]['title']}",f'Your station: {place} ({at[2]},{at[3]}).',
                  'At your station, use /mystery clue. All partners must be present to solve.']
        if role==len(pack['roles'])-1:lines.append(f'/mystery solve {index+1} ANSWER')
        return lines

    def command(self,trainer,words,*,transaction=True):
        if len(words)==2 and words[0] in ('start','join') and getattr(self.s,'races',None) and self.s.races.current(trainer):raise ValueError('Leave your current race first.')
        if not words or words==['status']:return self.status(trainer)
        with self.db if transaction else nullcontext():
            from .private_mystery_partners import command as private_command
            handled=private_command(self.s,trainer,words)
            if handled is not None:return handled
            if words==['list']:
                return [key+': '+self._pack(key)['title'] for key, in self.db.execute('SELECT id FROM mystery_packs ORDER BY id LIMIT 12')] or ['No mysteries have been published.']
            if len(words) in (2,3) and words[0]=='start':
                pack=self._pack(words[1]);chosen=self._role(words[2],pack) if len(words)==3 else 0;old=self._current(trainer)
                if old:
                    if old[1]!=words[1]:raise ValueError('Finish or /mystery leave your current expedition first.')
                else:
                    rid=secrets.token_hex(8)
                    self.db.execute('INSERT INTO mystery_runs VALUES(?,?,0,?)',(rid,words[1],'waiting'))
                    self.db.execute('INSERT INTO mystery_members VALUES(?,?,?)',(rid,chosen,trainer))
                    self._bind(rid,trainer,words[1])
                return self.status(trainer)
            if len(words) in (2,3) and words[0]=='join':
                old=self._current(trainer)
                if old:
                    if old[0]!=words[1]:raise ValueError('You already have an unfinished mystery.')
                    return self.status(trainer)
                row=self.db.execute('SELECT status,pack FROM mystery_runs WHERE id=?',(words[1],)).fetchone()
                if not row or row[0]!='waiting':raise ValueError('That invitation is unavailable.')
                pack=self._pack(row[1]);occupied={r for r, in self.db.execute('SELECT role FROM mystery_members WHERE run=?',(words[1],))}
                chosen=self._role(words[2],pack) if len(words)==3 else next(r for r in range(len(pack['roles'])) if r not in occupied)
                if chosen in occupied:raise ValueError('That role is already occupied.')
                self.db.execute('INSERT INTO mystery_members VALUES(?,?,?)',(words[1],chosen,trainer))
                self._bind(words[1],trainer,row[1])
                if len(occupied)+1==len(pack['roles']):self.db.execute("UPDATE mystery_runs SET status='active' WHERE id=?",(words[1],))
                return self.status(trainer)
            run=self._current(trainer)
            if not run:raise ValueError('Join or start a mystery first.')
            rid,key,index,state,role=run;pack=self._pack(key);stage=pack['stages'][index]
            if words==['leave']:
                self.db.execute("UPDATE mystery_runs SET status='cancelled' WHERE id=?",(rid,))
                from .private_mystery_partners import cancel
                cancel(self.s,rid)
                return ['Mystery ended for all participants. No saves or inventory changed.']
            if words==['clue']:
                if state!='active':raise ValueError('Wait for all roles to join before reading clues.')
                if not self._at(trainer,stage['stations'][role]['at'],rid,key):raise ValueError('Stand ready at your current station to read its clue.')
                self.db.execute('INSERT OR IGNORE INTO mystery_clues VALUES(?,?,?)',(rid,index,role))
                return [stage['stations'][role]['clue'],'Share what you discovered with your partners.']
            if len(words)==3 and words[0]=='solve':
                if role!=len(pack['roles'])-1:raise ValueError('The final role is the solver. Share your clue with them.')
                if not words[1].isascii() or not words[1].isdecimal() or int(words[1])!=index+1:raise ValueError('That is not the current stage. Use /mystery status.')
                members=self.db.execute('SELECT role,trainer FROM mystery_members WHERE run=? ORDER BY role',(rid,)).fetchall()
                if state!='active' or len(members)!=len(pack['roles']) or not all(self._at(t,stage['stations'][r]['at'],rid,key) for r,t in members):raise ValueError(('Both partners' if len(pack['roles'])==2 else 'All partners')+' must stand ready at their current stations.')
                if self.db.execute('SELECT count(*) FROM mystery_clues WHERE run=? AND stage=?',(rid,index)).fetchone()[0]!=len(pack['roles']):raise ValueError('All partners must read their current clue first.')
                if words[2]!=stage['answer']:return ['That answer does not fit. Compare all your clues again.']
                self.db.execute('INSERT INTO mystery_solved VALUES(?,?)',(rid,index))
                finished=index+1==len(pack['stages'])
                self.db.execute('UPDATE mystery_runs SET stage=?,status=? WHERE id=?',(index+1,'completed' if finished else 'active',rid))
                return [stage['result']]+self.status(trainer)
            raise ValueError('Use /mystery list, status, clue, leave, or the displayed solve line.')

    def handle(self,conn,message):
        words=message.split()
        if not words or words[0]!='/mystery':return False
        try:
            with self.s.lock:lines=self.command(conn['id'],words[1:])
        except (ValueError,TypeError,sqlite3.Error) as exc:
            lines=[str(exc) if isinstance(exc,ValueError) else 'Mystery transaction failed; check /mystery status.']
        for line in lines[:12]:self.s.guild_chat.message(conn,conn['id'],line[:120])
        conn['chat_status']='sent';self.s._queue(conn,self.s._snapshot(conn));return True
