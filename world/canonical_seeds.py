"""Source-grounded identities, not authored arcs or fabricated world evidence."""
from copy import deepcopy
from .canonical_cast import BINDINGS

PROFILES={
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


def enroll(queue,inspection):
    data=inspection.get('data',inspection);memory=data.get('world_memory',{})
    if inspection.get('ok') is not True or not memory.get('world_id') or type(memory.get('through')) is not int:raise ValueError('Need current world inspection')
    # Existing enrollment and cursors are preserved; no replay or automatic retry.
    with queue.db:
        existing={r['id'] for r in queue.db.execute('SELECT id FROM character_reactions')}
        if len(existing|set(PROFILES))>8:raise ValueError('At most eight followed characters')
        if queue.db.execute('SELECT 1 FROM character_reactions WHERE world!=?',(memory['world_id'],)).fetchone():raise ValueError('Enrollment belongs to another world')
        for identity in PROFILES:
            queue.db.execute('INSERT OR IGNORE INTO canonical_seed_enrollments VALUES(?)',(identity,))
            queue.db.execute('INSERT OR IGNORE INTO character_reactions VALUES(?,?,?,?)',
                (identity,'Let this original character develop from actual public events while preserving their identity and ordinary story.',memory['world_id'],memory['through']))
