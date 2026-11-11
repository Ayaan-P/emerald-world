"""Source-grounded identities, not authored arcs or fabricated world evidence."""
from copy import deepcopy
from .canonical_cast import BINDINGS

PROFILES={
 'canon_birch':dict(identity='Professor Birch researches Pokemon in Hoenn. Public Dex reports are anonymous client claims, not current ownership, a sighting location, a personal meeting or an observed migration. Can independently propose native-backed world opportunities from those findings, or wait. Original starter, rating and reward services remain personal.',places=['LittlerootTown_ProfessorBirchsLab','Route101','Route102','Route103']),
 'canon_rydel':dict(identity='Bicycle shop owner in Mauville. Enthusiastic about cycling and helping trainers choose and use bikes.',places=['MauvilleCity_BikeShop','MauvilleCity_Gym','Route110']),
 'canon_wally':dict(identity='Aspiring trainer connected to Petalburg and his family in Verdanturf. Wants to become stronger with his Pokemon. Never assume a particular trainer has met, defeated or helped him.',places=['VerdanturfTown_WandasHouse','PetalburgCity_Gym','MauvilleCity_Gym','EverGrandeCity_ChampionsRoom']),
 'canon_briney':dict(identity='Experienced sailor fond of Peeko. Provides the original conditional Dewford and Slateport sailing service. Never assume Peeko has been rescued in any player save.',places=['Route104_MrBrineysHouse','DewfordTown_Gym','SlateportCity','RusturfTunnel']),
 'canon_steven':dict(identity='Steven Stone collects rare rocks and stones and values Pokemon. His original house contains his collection. Do not infer current travel, gifts, battle results or player story progress.',places=['MossdeepCity_StevensHouse','MossdeepCity_Gym','GraniteCave_B2F','EverGrandeCity_ChampionsRoom'])}


def profile(identity):
    row=deepcopy(PROFILES[identity]);binding=BINDINGS[identity]
    row.update(name=binding['name'],source='data/maps/'+binding['map']+'/scripts.inc',binding=deepcopy(binding),
        limits='Fictional identity background only, never event evidence. Keep vanilla story, services, teams and per-save progression unchanged. Choose supported goals from actual public events, or wait. No fixed future arc.')
    return row


def pending(identity):
    return dict(version=0,status='active',canonical=True,places=['native:'+p for p in PROFILES[identity]['places']])


def enroll(queue,inspection,*,initial=None,actors=None,purpose=None):
    selected=tuple(PROFILES if actors is None else actors)
    if not selected or set(selected)-set(PROFILES):raise ValueError('Unknown canonical enrollment')
    purpose=purpose or 'Let this original character develop from actual public events while preserving their identity and ordinary story.'
    if type(purpose) is not str or not 1<=len(purpose)<=1024:raise ValueError('Invalid character purpose')
    data=inspection.get('data',inspection);memory=data.get('world_memory',{})
    if inspection.get('ok') is not True or not memory.get('world_id') or type(memory.get('through')) is not int:raise ValueError('Need current world inspection')
    # Existing enrollment and cursors are preserved; no replay or automatic retry.
    with queue.db:
        existing={r['id'] for r in queue.db.execute('SELECT id FROM character_reactions')}
        if len(existing|set(selected))>8:raise ValueError('At most eight followed characters')
        if queue.db.execute('SELECT 1 FROM character_reactions WHERE world!=?',(memory['world_id'],)).fetchone():raise ValueError('Enrollment belongs to another world')
        for identity in selected:
            first=bool(initial and identity in initial and not queue.db.execute('SELECT 1 FROM canonical_seed_starts WHERE id=?',(identity,)).fetchone())
            if initial and identity in initial:queue.db.execute('INSERT OR IGNORE INTO canonical_seed_starts VALUES(?,?)',(identity,initial[identity]))
            queue.db.execute('INSERT OR IGNORE INTO canonical_seed_enrollments VALUES(?)',(identity,))
            queue.db.execute('INSERT OR IGNORE INTO character_reactions VALUES(?,?,?,?)',
                (identity,purpose,memory['world_id'],(initial[identity]-1 if first else memory['through'])))


def commissioning(event,identity):
    return (event.get('event')=='canonical_actor_commissioned'
        and event.get('character_id')==identity and identity in BINDINGS
        and event.get('basis')=='explicit_local_host_cast_enrollment'
        and event.get('places')==['native:'+BINDINGS[identity]['map']])


def initialize(queue,server,*,actor=None,purpose=None):
    """Record a real host request, never a fictional achievement or private meeting.

    The world receipt is durable before queue enrollment. Retrying after a crash
    finds that receipt; an existing cursor is never rewound or failed job retried.
    """
    from .canonical_cast import records
    if actor is not None and actor not in PROFILES:raise ValueError('Unknown canonical actor')
    selected=tuple(PROFILES) if actor is None else (actor,)
    with server.lock:
        with server.db:
            server.db.execute('CREATE TABLE IF NOT EXISTS canonical_seed_commissions(actor TEXT PRIMARY KEY,seq INTEGER NOT NULL)')
            existing=records(server.module_state);boundaries={}
            for actor in selected:
                if actor in existing:continue
                row=server.db.execute('SELECT seq FROM canonical_seed_commissions WHERE actor=?',(actor,)).fetchone()
                if row:boundaries[actor]=row[0];continue
                seq=server.memory.append('canonical_actor_commissioned',dict(character_id=actor,
                    places=['native:'+BINDINGS[actor]['map']],basis='explicit_local_host_cast_enrollment',
                    summary='The local host enabled optional living-cast initialization for '+BINDINGS[actor]['name']+'.',
                    limits='A setup request, not an in-world experience. Supports initial identity-based goal and greeting only. No player history, achievement, relationship, travel or story progression is implied.'))
                server.db.execute('INSERT INTO canonical_seed_commissions VALUES(?,?)',(actor,seq))
                server.revision=seq;boundaries[actor]=seq
        enroll(queue,server.inspect(),initial=boundaries,actors=selected,purpose=purpose)
