"""Opt-in private landmark exploration over acknowledged generated geometry.

Arrivals are client-reported validated presence, not anti-cheat proof. Private
visits stay private unless a player explicitly shares one anonymous landmark
arrival with public world history.
"""
import argparse
import json
import time
import sqlite3
from pathlib import Path
from .route_landscape import compile_plan, MAX_INPUT


class LandmarkSurvey:
    def __init__(self, server):
        self.server=server
        server.db.executescript('''
            CREATE TABLE IF NOT EXISTS route_artifacts (revision TEXT PRIMARY KEY, artifact TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS survey_routes (revision TEXT PRIMARY KEY, sites TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS survey_inherited (trainer TEXT, revision TEXT, landmark TEXT, source_revision TEXT NOT NULL,
                PRIMARY KEY(trainer,revision,landmark));
            CREATE TABLE IF NOT EXISTS survey_sessions (trainer TEXT PRIMARY KEY, revision TEXT NOT NULL, active INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS survey_publications (revision TEXT, landmark TEXT, seq INTEGER NOT NULL,
                PRIMARY KEY(revision,landmark));
            CREATE TABLE IF NOT EXISTS survey_visits (trainer TEXT, revision TEXT, landmark TEXT,
                PRIMARY KEY(trainer,revision,landmark));
        ''')

    def register(self, plan):
        """Owner registers an already archived exact generated route plan."""
        s=self.server
        from .route_artifacts import create, archive
        blob,artifact=create(plan)
        report=artifact['report']
        sites=[site for site in report['landmarks'] if site['id'] not in ('entry','exit')]
        with s.lock:
            if not s.archive_generated_areas:raise ValueError('survey requires persistent area archive')
            row=s.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(report['revision'],)).fetchone()
            if row is None or row[0]!=blob:raise ValueError('publish this exact route map before registering its survey')
            encoded=json.dumps(sites,sort_keys=True)
            old=s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(report['revision'],)).fetchone()
            if old and old[0]!=encoded:raise ValueError('survey landmarks are already fixed for this revision')
            with s.db:
                archive(s,artifact,blob)
                s.db.execute('INSERT OR IGNORE INTO survey_routes VALUES (?,?)',(report['revision'],encoded))
        return dict(ok=True,revision=report['revision'],landmarks=len(sites))

    def register_revision(self, revision):
        from .route_artifacts import load
        with self.server.lock:
            artifact=load(self.server, revision)
            sites=[p for p in artifact['report']['landmarks'] if p['id'] not in ('entry','exit')]
            encoded=json.dumps(sites,sort_keys=True)
            old=self.server.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()
            if old and old[0]!=encoded:raise ValueError('survey landmarks are already fixed for this revision')
            with self.server.db:self.server.db.execute('INSERT OR IGNORE INTO survey_routes VALUES (?,?)',(revision,encoded))
            return dict(ok=True,revision=revision,landmarks=len(sites))

    def continue_revision(self, artifact):
        """Within the construction transaction; retain evidence, never invent arrivals."""
        s=self.server;old=artifact['parent'];new=artifact['revision']
        old_survey=s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(old,)).fetchone()
        if old_survey is None:return
        sites=[p for p in artifact['report']['landmarks'] if p['id'] not in ('entry','exit')]
        encoded=json.dumps(sites,sort_keys=True)
        existing=s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(new,)).fetchone()
        if existing and existing[0]!=encoded:raise ValueError('derived survey already differs')
        s.db.execute('INSERT OR IGNORE INTO survey_routes VALUES (?,?)',(new,encoded))
        from .route_artifacts import load
        parent_sites={p['id']:p for p in load(s,old)['report']['landmarks']}
        registered={p['id']:p for p in json.loads(old_survey[0])}
        retained={name for name in artifact['report']['retained'] if registered.get(name)==parent_sites.get(name)}
        evidence=s.db.execute('SELECT trainer,landmark,source_revision FROM survey_inherited WHERE revision=?',(old,)).fetchall()
        evidence+=s.db.execute('SELECT trainer,landmark,revision FROM survey_visits WHERE revision=?',(old,)).fetchall()
        for trainer,landmark,source in evidence:
            if landmark in retained:
                s.db.execute('INSERT OR IGNORE INTO survey_inherited VALUES (?,?,?,?)',(trainer,new,landmark,source))
        s.db.execute('UPDATE survey_sessions SET revision=? WHERE revision=?',(new,old))

    def scope(self, conn):
        s=self.server;state=conn.get('state');cave=s._connection_cave(conn)
        if (not state or time.monotonic()-conn.get('state_time',0)>5 or not state[6] or not conn.get('in_generated_cave') or cave is None
                or cave.version not in (16,17) or tuple(state[:2])!=s.wilds_map or s._region_scope(conn)!=cave.identity):
            return None
        return cave.identity

    def lines(self, conn):
        s=self.server;row=s.db.execute('SELECT revision,active FROM survey_sessions WHERE trainer=?',(conn['id'],)).fetchone()
        if row is None:return ['Use /explore start inside a registered route map.']
        revision,active=row
        sites=json.loads(s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()[0])
        seen={r[0] for r in s.db.execute('SELECT landmark FROM survey_visits WHERE trainer=? AND revision=?',(conn['id'],revision))}
        inherited={r[0] for r in s.db.execute('SELECT landmark FROM survey_inherited WHERE trainer=? AND revision=?',(conn['id'],revision))}
        carried=len(inherited-seen);seen|=inherited
        lines=([f'{carried} unchanged landmarks retained from earlier visits.'] if carried else [])
        lines += [f'Survey: {len(seen)}/{len(sites)} landmarks. '+('Active.' if active else 'Paused.')]
        if len(seen)==len(sites):return lines+['Survey complete. Your discoveries are saved privately.']
        if self.scope(conn)!=revision:return lines+['Return to the same map revision to continue.']
        x,y=conn['state'][2:4]
        site=min((p for p in sites if p['id'] not in seen),key=lambda p:(abs(p['x']-x)+abs(p['y']-y),p['id']))
        return lines+[f'Next: {site["id"]} near ({site["x"]},{site["y"]}). Reach its clearing center.']

    def share(self, conn, landmark, confirmed=False):
        s=self.server;revision=self.scope(conn)
        if revision is None:return ['Stand beside a discovered landmark in its acknowledged map to share it.']
        row=s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()
        sites=json.loads(row[0]) if row else []
        site=next((p for p in sites if p['id']==landmark),None)
        visited=s.db.execute('SELECT 1 FROM survey_visits WHERE trainer=? AND revision=? AND landmark=?',
                             (conn['id'],revision,landmark)).fetchone()
        if (site is None or not visited or abs(site['x']-conn['state'][2])+abs(site['y']-conn['state'][3])>1):
            return ['Only a landmark you discovered and are standing beside can be shared.']
        if not confirmed:
            return ['Publish this landmark name, coordinates and map revision to public world history?',
                    'Agents and other players can read it. Your name and private survey trail are excluded.',
                    f'This record persists. Confirm with /explore share {landmark} confirm']
        old=s.db.execute('SELECT seq FROM survey_publications WHERE revision=? AND landmark=?',(revision,landmark)).fetchone()
        if old:return ['That landmark discovery is already in public world history.']
        place=s.db.execute('SELECT place_id FROM world_places WHERE revision=?',(revision,)).fetchone()
        if place is None:return ['Archived place identity unavailable; nothing was shared.']
        try:
            with s.db:
                seq=s.memory.append('landmark_discovery_shared',dict(place_id=place[0],revision=revision,
                    landmark=landmark,x=site['x'],y=site['y'],publication='explicit_player_share',
                    basis='authenticated_acknowledged_client_presence',
                    limits='A player chose to share this arrival. Travel is client-reported, not independently simulated.'))
                s.db.execute('INSERT INTO survey_publications VALUES (?,?,?)',(revision,landmark,seq))
        except sqlite3.Error:
            return ['World history could not be saved. Nothing was shared; you can try again.']
        s.revision=seq
        return ['Landmark discovery shared with public world history. Your other discoveries remain private.']

    def reply(self, conn, lines):
        s=self.server
        for line in lines:s.guild_chat.message(conn,'World',line)
        conn['chat_status']='sent';s._queue(conn,s._snapshot(conn))

    def handle(self, conn, text):
        if text!='/explore' and not text.startswith('/explore '):return False
        s=self.server
        with s.lock:
            command=text.split()[1:]
            if command==['protocol','1']:
                s._queue(conn,f'EXPLORE_READY {conn["seq"]}\n');return True
            if command in (['history'],['history','older']):
                from .player_chronicle import read
                self.reply(conn,read(s,conn,older=len(command)==2));return True
            if len(command)==2 and command[0]=='guide':
                from .character_guides import guide
                self.reply(conn,guide(s,conn,command[1]));return True
            if command==['directions']:
                from .character_guides import directions
                self.reply(conn,directions(s,conn));return True
            if command==['start']:
                revision=self.scope(conn)
                if not revision or not s.db.execute('SELECT 1 FROM survey_routes WHERE revision=?',(revision,)).fetchone():
                    self.reply(conn,['Enter an acknowledged route map with a registered survey first.']);return True
                with s.db:s.db.execute('INSERT OR REPLACE INTO survey_sessions VALUES (?,?,1)',(conn['id'],revision))
                self.observe(conn)
            elif len(command) in (2,3) and command[0]=='share' and (len(command)==2 or command[2]=='confirm'):
                self.reply(conn,self.share(conn,command[1],len(command)==3));return True
            elif command==['stop']:
                with s.db:s.db.execute('UPDATE survey_sessions SET active=0 WHERE trainer=?',(conn['id'],))
            elif command not in ([],['status']):
                self.reply(conn,['Use /explore start, status, stop, share LANDMARK, guide NPC_ID, directions, or history.']);return True
            lines=self.lines(conn)
            if not command:lines.append('Read this place\'s public past with /explore history.')
            self.reply(conn,lines)
        return True

    def observe(self, conn):
        s=self.server;revision=self.scope(conn)
        if revision is None:return
        row=s.db.execute('SELECT revision FROM survey_sessions WHERE trainer=? AND active=1',(conn['id'],)).fetchone()
        if row is None or row[0]!=revision:return
        sites=json.loads(s.db.execute('SELECT sites FROM survey_routes WHERE revision=?',(revision,)).fetchone()[0])
        x,y=conn['state'][2:4]
        for site in sites:
            if abs(site['x']-x)+abs(site['y']-y)>1:continue
            with s.db:
                inserted=s.db.execute('INSERT OR IGNORE INTO survey_visits VALUES (?,?,?)',(conn['id'],revision,site['id'])).rowcount
            if inserted and conn.get('chat'):
                self.reply(conn,[f'Discovered {site["id"]}.']+self.lines(conn))


def main(argv=None):
    parser=argparse.ArgumentParser(description='Register an archived route map survey without activating or changing terrain.')
    parser.add_argument('plan',type=Path,nargs='?');parser.add_argument('--revision')
    parser.add_argument('--admin-socket',required=True)
    args=parser.parse_args(argv)
    if (args.plan is None) == (args.revision is None):parser.error('provide a plan/artifact file or --revision')
    from .client import admin_request
    if args.revision is not None:
        request=dict(command='register_survey',revision=args.revision)
    else:
        with args.plan.open('rb') as stream:raw=stream.read(MAX_INPUT*8+1)
        if len(raw)>MAX_INPUT*8:parser.error('artifact too large')
        plan=json.loads(raw)
        if type(plan) is dict and 'schema' in plan:
            from .route_artifacts import validate
            validate(plan);plan=plan['plan']
        compile_plan(plan)
        request=dict(command='register_survey',plan=plan)
    result=admin_request('',request,admin_path=args.admin_socket)
    if result.get('ok') is not True:parser.error(result.get('error','survey registration refused'))
    print(json.dumps(result))

if __name__=='__main__':main()
