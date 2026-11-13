"""Agent-owned group investigations at reviewed ordinary Hoenn stations.

Definitions are public fictional content. Individual clues/participation/completion
remain in the private mystery subsystem; only explicit shared project choices
can inform the public author afterward.
"""
import hashlib,json
from .cooperative_mysteries import validate as validate_mystery,dump
from .build_catalog import validate_coords

# Existing cooperative_signal stations, checked against the repository's released
# map geometry tests. Do not invent terrain or treat these as canonical lore.
STATIONS=((0,0,10,10),(0,0,22,12),(0,3,10,40),(0,3,22,40))


def validate(pack,row):
    if pack is None:return
    validate_mystery(pack,validate_coords)
    for stage in pack['stages']:
        for station in stage['stations']:
            if tuple(station['at']) not in STATIONS:raise ValueError('Use reviewed investigation stations')
            place=validate_coords(*station['at'])['name']
            if 'native:'+place not in row['places']:raise ValueError('Station outside actor interests')


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS canonical_investigations(id TEXT PRIMARY KEY,actor TEXT,digest TEXT)')


def publish(server,change):
    pack=change['after'].get('investigation')
    if not pack:return
    actor=change['character_id'];document=dump(pack);digest=hashlib.sha256(document.encode()).hexdigest()
    old=server.db.execute('SELECT actor,digest FROM canonical_investigations WHERE id=?',(pack['id'],)).fetchone()
    content=server.db.execute('SELECT document FROM mystery_packs WHERE id=?',(pack['id'],)).fetchone()
    if old or content:
        if old!=(actor,digest) or content!=(document,):raise ValueError('Investigation identity/content/owner is immutable')
        return
    if server.db.execute('SELECT count(*) FROM canonical_investigations WHERE actor=?',(actor,)).fetchone()[0]>=8:raise ValueError('Eight investigations per actor')
    if server.db.execute('SELECT count(*) FROM mystery_packs').fetchone()[0]>=64:raise ValueError('Mystery capacity reached')
    # Caller owns canonical admission transaction; never call the committing publish helper.
    server.db.execute('INSERT INTO mystery_packs VALUES(?,?)',(pack['id'],document))
    server.db.execute('INSERT INTO canonical_investigations VALUES(?,?,?)',(pack['id'],actor,digest))


def choice_receipt(server,pack,place,scene,choice,revision,changes):
    owner=server.db.execute('SELECT actor FROM canonical_initiatives WHERE pack=?',(pack,)).fetchone()
    if not owner or not changes:return
    document=server.db.execute('SELECT document FROM story_packs WHERE id=?',(pack,)).fetchone()
    prerequisite=json.loads(document[0])['scenes'][scene].get('mystery')
    bound=server.db.execute('SELECT actor FROM canonical_investigations WHERE id=?',(prerequisite,)).fetchone()
    if bound!=owner:return # Preserve legacy private project-choice behavior.
    # No trainer/run/clue/answer/participation information is published.
    server.memory.append('canonical_shared_project_decided',dict(character_id=owner[0],pack=pack,place=place,
        scene=scene,choice=choice,revision=revision,changes=changes,places=['native:'+place],
        publication='explicit_shared_project_choice',basis='authority_committed_shared_story_consequence',
        limits='Anonymous shared choice only. Does not identify a solver, publish private clues, or prove a native campaign event.'))


def relevant(event,actor):
    return (event.get('event')=='canonical_shared_project_decided' and event.get('character_id')==actor
        and event.get('publication')=='explicit_shared_project_choice'
        and event.get('basis')=='authority_committed_shared_story_consequence')


def lines(row):
    pack=(row or {}).get('investigation')
    if not pack:return ['This actor has no group investigation.']
    return [pack['title'],str(len(pack['roles']))+' trainers; private clues, no native rewards or story changes.',
            '/mystery start '+pack['id']+' ROLE',
            'Roles: '+', '.join(str(i+1)+' '+name for i,name in enumerate(pack['roles'])),
            'Return here afterward for available project choices. Shared choices affect the public project.']
