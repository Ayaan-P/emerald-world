"""Opt-in cooperative checkpoint relays using validated native field presence.

Authority clocks order the race. Positions are client attestations, so records
are recreational, not anti-cheat evidence. No saves, inventory or battle writes.
"""
import json
import re
import secrets
import sqlite3
import time
from .guilds import GuildError

COURSE = dict(id='petalburg_relay1',title='Petalburg Baton Circuit',limit=180,legs=[
    dict(start=[0,0,10,10],checkpoints=[[0,0,10,12],[0,0,18,13],[0,0,21,12]]),
    dict(start=[0,0,22,12],checkpoints=[[0,0,22,10],[0,0,23,10],[0,0,23,13]])])


def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def validate(course,coords,generated):
    if type(course) is not dict or set(course) not in ({'id','title','limit','legs'},{'id','title','limit','legs','mounted'}) or len(encoded(course))>8192:raise ValueError('Invalid relay course.')
    if 'mounted' in course and type(course['mounted']) is not bool:raise ValueError('Invalid mounted requirement.')
    if type(course['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',course['id']):raise ValueError('Invalid course identifier.')
    if type(course['title']) is not str or not 1<=len(course['title'])<=55 or any(not 32<=ord(c)<=126 for c in course['title']):raise ValueError('Invalid course title.')
    if type(course['limit']) is not int or not 30<=course['limit']<=900:raise ValueError('Relay limit must be 30..900 seconds.')
    if type(course['legs']) is not list or not 2<=len(course['legs'])<=4:raise ValueError('Relay courses need two to four runners.')
    for i,leg in enumerate(course['legs']):
        if type(leg) is not dict or set(leg)!={'start','checkpoints'} or type(leg['checkpoints']) is not list or not 2<=len(leg['checkpoints'])<=8:raise ValueError('Each leg needs a start pad and two to eight checkpoints.')
        points=[leg['start']]+leg['checkpoints']
        for point in points:
            if type(point) is not list or len(point)!=4 or any(type(n) is not int for n in point):raise ValueError('Invalid relay position.')
            coords(*point)
            if tuple(point[:2]) in generated:raise ValueError('Relay courses require stable standard maps.')
        if any(a==b for a,b in zip(points,points[1:])):raise ValueError('Consecutive checkpoints must differ.')
        if i:
            previous=course['legs'][i-1]['checkpoints'][-1];start=leg['start']
            if start[:2]!=previous[:2] or abs(start[2]-previous[2])+abs(start[3]-previous[3])!=1:
                raise ValueError('Handoff pads must be adjacent, distinct tiles on the same map.')
    return course


class FieldRelays:
    def __init__(self,server,coords,clock=time.monotonic):
        self.s=server;self.db=server.db;self.coords=coords;self.clock=clock;self.runs={}
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS relay_courses(id TEXT PRIMARY KEY,document TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS relay_records(run TEXT PRIMARY KEY,course TEXT NOT NULL,team TEXT NOT NULL,milliseconds INTEGER NOT NULL,splits TEXT NOT NULL);
        ''');self.db.commit()
        self.publish(COURSE)
        mounted=json.loads(encoded(COURSE));mounted.update(id="petalburg_mount1",title="Petalburg Pokemon Mount Relay",mounted=True)
        self.publish(mounted)

    def publish(self,course):
        validate(course,self.coords,(self.s.cave_map,self.s.wilds_map));document=encoded(course)
        with self.db:
            row=self.db.execute('SELECT document FROM relay_courses WHERE id=?',(course['id'],)).fetchone()
            if row and row[0]!=document:raise ValueError('Course identity already names different content.')
            if not row:
                if self.db.execute('SELECT count(*) FROM relay_courses').fetchone()[0]>=64:raise ValueError('Course capacity reached.')
                self.db.execute('INSERT INTO relay_courses VALUES(?,?)',(course['id'],document))
        return dict(ok=True,id=course['id'])

    def _course(self,key):
        row=self.db.execute('SELECT document FROM relay_courses WHERE id=?',(key,)).fetchone()
        if not row:raise GuildError('Unknown relay course. Use /guild relay list.')
        course=json.loads(row[0])
        validate(course,self.coords,(self.s.cave_map,self.s.wilds_map))
        return course

    def _current(self,trainer):
        return next((r for r in self.runs.values() if any(c['id']==trainer for c in r['members'])),None)

    def _fresh(self,conn,now):
        from .combined_regions import admitted
        if getattr(self.s,'combined_regions',False) and not admitted(self.s,conn):return False
        state=conn.get('state');updated=conn.get('state_time')
        return bool(self.s.peers.get(conn['id']) is conn and not conn.get('closing') and conn.get('chat')
                    and state and state[6] and updated is not None and 0<=now-updated<=3
                    and not conn.get('in_generated_cave'))

    def _at(self,conn,point,now):return self._fresh(conn,now) and conn['state'][:4]==point

    def _tell(self,run,lines):
        for conn in run['members']:
            if self.s.peers.get(conn['id']) is conn and not conn.get('closing'):
                for line in lines:self.s.guild_chat.message(conn,conn['id'],line[:120])
                self.s._queue(conn,self.s._snapshot(conn))

    def _end(self,run,reason):
        self.runs.pop(run['id'],None)
        self._tell(run,[reason])

    def _location(self,point):
        return f"{self.coords(*point)['name']} ({point[2]},{point[3]})"

    def _target(self,run):
        if run['phase'] in ('lobby','countdown'):return None
        return run['course']['legs'][run['leg']]['checkpoints'][run['checkpoint']]

    def status(self,run,conn):
        role=run['members'].index(conn);course=run['course'];phase=run['phase']
        if phase in ('lobby','countdown'):
            return [course['title']+f" - runner {role+1}/{len(course['legs'])}.",
                    'Your start pad: '+self._location(course['legs'][role]['start']),
                    'At your pad: /guild relay ready. Ready runners: '+str(len(run['ready'])),
                    'Join code: /guild relay join '+run['id']]
        runner=run['members'][run['leg']]['id']
        target=(course['legs'][role]['start'] if role>run['leg'] else self._target(run))
        lines=[f'Relay: {runner} carries the baton. '+f"{max(0,int(self.clock()-run['started']))} seconds elapsed."]
        if phase=='handoff':lines.append('Handoff: both runners must stand on their adjacent pads.')
        lines.append(('Your waiting pad: ' if role>run['leg'] else 'Next checkpoint: ')+self._location(target))
        state=conn.get('state')
        if state and state[:2]==target[:2]:
            dx,dy=target[2]-state[2],target[3]-state[3]
            lines.append(f'From you: {abs(dx)} tiles '+('east' if dx>=0 else 'west')+f', {abs(dy)} '+('south' if dy>=0 else 'north')+'.')
        return lines

    def command(self,conn,words):
        if len(words)==2 and words[0] in ('start','join') and getattr(self.s,'races',None) and self.s.races.current(conn['id']):raise GuildError('Leave your current race first.')
        self.tick()
        if not conn.get('private_commands'):raise GuildError('Relay play needs the matched RC12 private-command client.')
        trainer=conn['id'];guild=self.s.guilds._require(trainer);now=self.clock()
        if words==['list']:
            return ['Relay courses:']+[key+': '+self._course(key)['title'] for key, in self.db.execute('SELECT id FROM relay_courses ORDER BY id LIMIT 8')]
        if words and words[0]=='records' and len(words)<=2:
            records=self.db.execute('''SELECT course,milliseconds,team FROM relay_records
                 WHERE EXISTS (SELECT 1 FROM json_each(relay_records.team) WHERE value=?)
                 AND (? IS NULL OR course=?) ORDER BY milliseconds LIMIT 8''',(trainer,words[1] if len(words)==2 else None,words[1] if len(words)==2 else None)).fetchall()
            lines=[]
            for course,ms,team in records:
                lines += [f'{course}: {ms/1000:.2f}s', 'Team: '+', '.join(json.loads(team))]
            return lines or ['No completed relay times yet.']
        run=self._current(trainer)
        if len(words)==2 and words[0]=='start':
            if run or (getattr(self.s,'flags',None) and self.s.flags.current(trainer)):raise GuildError('Leave your current field activity first.')
            if len(self.runs)>=32 or any(r['guild']==guild[0] for r in self.runs.values()):raise GuildError('Your guild already has a relay, or all relay slots are busy.')
            course=self._course(words[1]);rid=secrets.token_hex(6)
            run=dict(id=rid,guild=guild[0],course=course,members=[conn],ready=set(),phase='lobby',until=now+300,leg=0,checkpoint=0,splits=[])
            from .canonical_collaboration import briefing
            run['cast_briefing']=briefing(self.s,course['id'])
            self.runs[rid]=run
            return run['cast_briefing']+self.status(run,conn)
        if len(words)==2 and words[0]=='join':
            if run or (getattr(self.s,'flags',None) and self.s.flags.current(trainer)):raise GuildError('Leave your current field activity first.')
            run=self.runs.get(words[1])
            if not run or run['phase']!='lobby' or run['guild']!=guild[0] or len(run['members'])>=len(run['course']['legs']):raise GuildError('That relay invitation is unavailable to you.')
            run['members'].append(conn)
            return run.get('cast_briefing',[])+self.status(run,conn)
        if not run:return ['Use /guild relay list, start COURSE, join CODE, or records.']
        if not words or words==['status']:return self.status(run,conn)
        if words==['leave']:
            self._end(run,'Relay cancelled by a runner. No time was recorded.')
            return ['You left the relay.']
        if words==['ready']:
            if run['course'].get('mounted') and (not conn.get('mount_capable') or not conn.get('mount',(0,0))[0]):raise GuildError('Mount a supported party Pokemon first: /mount 1..6')
            if run['phase']!='lobby':raise GuildError('The relay already started.')
            role=run['members'].index(conn)
            if not self._at(conn,run['course']['legs'][role]['start'],now):raise GuildError('Stand ready at your start pad. Use /guild relay status for directions.')
            run['ready'].add(trainer)
            if len(run['ready'])==len(run['course']['legs']):
                run['phase']='countdown';run['started']=now+3
                run['mounts']=[c.get('mount',(0,0)) for c in run['members']]
                self._tell(run,['Relay starts in three seconds. Stay on your pads. Timer continues through menus and battles.'])
            return ['Ready. Keep standing on your pad.']
        raise GuildError('Use /guild relay list, start COURSE, join CODE, ready, status, records, or leave.')

    def _checkpoint_hit(self,run,conn,target,now):
        if not run['course'].get('mounted'):return self._at(conn,target,now)
        if not self._fresh(conn,now):return False
        seq=conn['seq'];old_seq,index=run.get('trace_cursor',{}).get(conn['id'],(-1,-1))
        if old_seq!=seq:index=-1
        trail=conn.get('mount_trail',[])
        for i,point in enumerate(trail):
            if i>index and point==target:
                run.setdefault('trace_cursor',{})[conn['id']]=(seq,i)
                return True
        # An exact current position remains a valid witness, without inventing
        # any intermediate visit on a diagonal, warp or congested sample.
        return self._at(conn,target,now)

    def tick(self):
        now=self.clock()
        for run in list(self.runs.values()):
            course=run['course']
            if any(self.s.peers.get(c['id']) is not c or c.get('closing') or self.s.guilds._member(c['id']) is None or self.s.guilds._member(c['id'])[0]!=run['guild'] for c in run['members']):
                self._end(run,'Relay cancelled: a runner disconnected or left the guild. No time recorded.');continue
            if run['phase']=='lobby':
                if now>run['until']:self._end(run,'Relay invitation expired. Start a new relay when ready.')
                continue
            if course.get('mounted') and (any(not c.get('mount',(0,0))[0] or c.get('mount')!=run['mounts'][i] for i,c in enumerate(run['members'])) or any(c.get('mount_trail_lost') for c in run['members'])):
                self._end(run,'Mounted relay cancelled: mount changed or movement reports were incomplete. No time recorded.');continue
            if run['phase']=='countdown':
                if not all(self._at(c,course['legs'][i]['start'],now) for i,c in enumerate(run['members'])):
                    run['phase']='lobby';run['ready'].clear()
                    self._tell(run,['Countdown cancelled. Return to your pads and ready again.']);continue
                if now<run['started']:continue
                run['phase']='running'
                run['trace_cursor']={c['id']:(c['seq'],len(c.get('mount_trail',[]))-1) for c in run['members']}
                self._tell(run,['Go! '+run['members'][0]['id']+' runs first.', 'Next checkpoint: '+self._location(self._target(run))])
            if now-run['started']>course['limit']:
                self._end(run,'Relay time limit reached. No completed time recorded.');continue
            if any(c.get('state_time') is None or now-c['state_time']>10 for c in run['members']):
                self._end(run,'Relay cancelled: a runner stopped reporting. No time recorded.');continue
            runner=run['members'][run['leg']]
            if run['phase']=='handoff':
                incoming=run['members'][run['leg']+1]
                if self._at(runner,self._target(run),now) and self._at(incoming,course['legs'][run['leg']+1]['start'],now):
                    run['leg']+=1;run['checkpoint']=0;run['phase']='running'
                    run.setdefault('trace_cursor',{})[incoming['id']]=(incoming['seq'],len(incoming.get('mount_trail',[]))-1)
                    self._tell(run,['Baton handed to '+incoming['id']+'.','Next checkpoint: '+self._location(self._target(run))])
                continue
            if not self._checkpoint_hit(run,runner,self._target(run),now):continue
            if run['checkpoint']+1<len(course['legs'][run['leg']]['checkpoints']):
                run['checkpoint']+=1
                self._tell(run,['Checkpoint cleared. Next: '+self._location(self._target(run))]);continue
            run['splits'].append(max(0,round((now-run['started'])*1000)))
            if run['leg']+1<len(course['legs']):
                run['phase']='handoff'
                self._tell(run,['Leg complete. Meet on the adjacent handoff pads: '+self._location(course['legs'][run['leg']+1]['start'])]);continue
            team=[c['id'] for c in run['members']];elapsed=run['splits'][-1]
            try:
                with self.db:
                    best=self.db.execute('SELECT min(milliseconds) FROM relay_records WHERE course=? AND team=?',(course['id'],encoded(team))).fetchone()[0]
                    self.db.execute('INSERT INTO relay_records VALUES(?,?,?,?,?)',(run['id'],course['id'],encoded(team),elapsed,encoded(run['splits'])))
            except sqlite3.Error:
                self._end(run,'Finish could not be saved. No completed time recorded.');continue
            improvement='First team time!' if best is None else ('New team best!' if elapsed<best else f'Team best: {best/1000:.2f}s.')
            self._tell(run,[improvement,'Leg split times: '+', '.join(f'{(v-(run["splits"][i-1] if i else 0))/1000:.2f}s' for i,v in enumerate(run['splits']))])
            self._end(run,f'Relay finished in {elapsed/1000:.2f}s. /guild relay records shows your saved times.')
