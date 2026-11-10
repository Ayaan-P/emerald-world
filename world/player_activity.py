"""Read-only projections of existing activity, never a second quest authority.

snapshot's trainer must come from an authenticated connection or the launcher's
selected live local identity. Browser payloads cannot select a trainer.
"""
import json
from .session import SessionError


def snapshot(server, trainer):
    from .characters import records
    from .world_journal import describe, _label
    with server.lock:
        row = server.db.execute('SELECT revision,active FROM survey_sessions WHERE trainer=?', (trainer,)).fetchone()
        survey = None
        if row:
            route = server.db.execute('SELECT sites FROM survey_routes WHERE revision=?', (row[0],)).fetchone()
            sites = json.loads(route[0]) if route else []
            seen = [r[0] for r in server.db.execute('SELECT landmark FROM survey_visits WHERE trainer=? AND revision=? ORDER BY landmark', (trainer,row[0]))]
            conn = server.peers.get(trainer)
            survey = dict(revision=row[0],active=bool(row[1]),visited=seen,landmarks=sites,
                          in_scope=bool(conn and not conn.get('closing') and server.landmark_survey.scope(conn)==row[0]),
                          complete=bool(sites) and all(site['id'] in seen for site in sites),
                          next_objective=server.landmark_survey.next_objective(conn, row[0], sites, seen, bool(row[1])))
        guild = None
        membership = server.guilds._member(trainer)
        if membership:
            goals = []
            for kind, table in (('expedition','guild_expeditions'),('meetup','guild_meetups')):
                goal = server.db.execute('SELECT map_name,goal,complete FROM '+table+' WHERE guild_id=?', (membership[0],)).fetchone()
                if goal:
                    count = server.db.execute('SELECT count(*) FROM guild_expedition_visits WHERE guild_id=?', (membership[0],)).fetchone()[0] if kind=='expedition' else None
                    goals.append(dict(kind=kind,destination=goal[0],target=goal[1],credited=count,complete=bool(goal[2])))
            guild = dict(name=membership[1],leader=membership[2]==trainer,goals=goals)
        offers = []
        for identity, resident in sorted(records(server.module_state).items()):
            offer = resident.get('offer')
            if resident['status']=='active' and offer:
                destination = _label(offer['place_id'])
                if offer['place_id'].startswith('area:'):
                    archived = server.db.execute('SELECT a.label FROM generated_area_archive a JOIN world_places p ON p.revision=a.identity WHERE p.place_id=? AND a.identity=?', (offer['place_id'],offer.get('region_revision'))).fetchone()
                    destination = archived[0] if archived and archived[0] else 'Archived generated destination'
                offers.append(dict(resident=identity,name=resident['name'],destination=destination,target=offer['target']))
        # Public committed facts only. This is not a private quest log.
        rows = server.db.execute("SELECT seq,data FROM events WHERE kind='world_memory' ORDER BY seq DESC LIMIT 8").fetchall()
        recap = []
        for seq, data in rows:
            event = dict(seq=seq, **json.loads(data))
            entry: dict = describe(event)
            if event['event'] == 'landmark_discovery_shared':
                entry.update(title='Landmark discovery shared', details=[
                    f"{event['landmark']} near ({event['x']}, {event['y']}).",
                    'A player explicitly shared this arrival. Their private survey trail is not published.',
                    'Arrival is client-reported, not independently simulated travel.'])
            recap.append(entry)
        coverage = server.db.execute("SELECT value FROM world_memory_metadata WHERE key='coverage_start_seq'").fetchone()[0]
        return dict(trainer=trainer,survey=survey,guild=guild,offers=offers,recap=recap,coverage_start_seq=int(coverage))


def read_activity(session, worlds, payload):
    if (type(payload) is not dict or set(payload)!={'world'} or type(payload['world']) is not str):
        raise SessionError('Choose your connected world. Trainer selection is private to this launcher.')
    if session.state is None or session.state.name != payload['world'] or not session.remote_trainer:
        raise SessionError('Connect as your trainer to read your own activities.')
    server = session.server
    if server is not None:
        with server.lock:
            conn = server.peers.get(session.remote_trainer)
            if conn is not None and not conn.get('closing'):
                return snapshot(server, conn['id'])
    if not callable(getattr(session, '_intent_client', None)):
        raise SessionError('Open your trainer in the game to authenticate your activity view.')
    try:
        with session._intent_client(session.remote_trainer) as client:
            result = client._request(dict(command='player_activity'))
        if result.get('ok') is not True or type(result.get('activity')) is not dict:
            raise ValueError('unsupported activity response')
        if result['activity'].get('trainer') != session.remote_trainer:
            raise ValueError('wrong activity identity')
        return result['activity']
    except (OSError, ValueError, ConnectionError):
        raise SessionError('This host does not provide your private activity view yet. Your native game remains available.') from None
