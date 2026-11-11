"""Bounded catalogue sampled at native safe idle, never arbitrary flag telemetry."""
import time

MILESTONES=tuple(dict(id='badge_'+str(i+1),place='native:'+place,
    summary='A trainer obtained the '+badge+' Badge.') for i,(place,badge) in enumerate((
    ('RustboroCity_Gym','Stone'),('DewfordTown_Gym','Knuckle'),('MauvilleCity_Gym','Dynamo'),
    ('LavaridgeTown_Gym_1F','Heat'),('PetalburgCity_Gym','Balance'),('FortreeCity_Gym','Feather'),
    ('MossdeepCity_Gym','Mind'),('SootopolisCity_Gym_1F','Rain'))))+(dict(
    id='league_clear',place='native:EverGrandeCity_ChampionsRoom',summary='A trainer completed the Pokemon League.'),)


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS campaign_observations(
      trainer TEXT,run TEXT,mask INTEGER NOT NULL,published INTEGER NOT NULL,enabled INTEGER NOT NULL,
      PRIMARY KEY(trainer,run))''')


def handle(server,conn,run,key,guard):
    if not conn.get('state') or time.monotonic()-conn.get('state_time',0)>3:
        raise ValueError('Campaign observation needs a fresh field snapshot')
    trainer=conn['id']
    with server.db:
        old=server.db.execute('SELECT mask,published,enabled FROM campaign_observations WHERE trainer=? AND run=?',(trainer,run)).fetchone()
        if key in ('on','off') and guard=='confirm':
            if key=='on' and (old is None or conn.get('campaign_run')!=run):
                raise ValueError('Synchronize this save before enabling future campaign sharing')
            if old:
                server.db.execute('UPDATE campaign_observations SET enabled=?,published=published|mask WHERE trainer=? AND run=?',(int(key=='on'),trainer,run))
            return dict(ok=True,sharing=key=='on')
        if guard!='private' or not key.isascii() or not key.isdecimal() or len(key)>3 or not 0<=int(key)<512:
            raise ValueError('Invalid bounded campaign snapshot')
        mask=int(key);previous,published,enabled=old or (mask,0,0)
        # Baseline and off-mode data are private. Rewinds never retract public
        # history or republish the same achievement from this lineage.
        new=mask & ~previous & ~published if enabled else 0
        for i,milestone in enumerate(MILESTONES):
            if new&(1<<i):
                server.revision=server.memory.append('canonical_campaign_milestone',dict(
                    milestone=milestone['id'],summary=milestone['summary'],places=[milestone['place']],
                    source='future_campaign_sharing_opt_in',basis='native_completed_flag_snapshot',
                    limits='Anonymous client attestation. No actor participation, current location, battle details or another save progression is implied.'))
        server.db.execute('''INSERT INTO campaign_observations VALUES(?,?,?,?,?)
          ON CONFLICT(trainer,run) DO UPDATE SET mask=excluded.mask,published=excluded.published''',
          (trainer,run,mask,published|new,enabled))
    conn['campaign_run']=run
    return dict(ok=True)


def relevant(event,places):
    return (event.get('event')=='canonical_campaign_milestone'
        and event.get('source')=='future_campaign_sharing_opt_in'
        and event.get('basis')=='native_completed_flag_snapshot'
        and any(event.get('milestone')==m['id'] and event.get('summary')==m['summary']
                and event.get('places')==[m['place']] and m['place'] in places for m in MILESTONES))
