"""Actor-owned executable shared projects, using existing story state authority.

Publication installs choices, not a claimed accomplishment. Other actors choose
independently; only committed actions can support a subsequent assessment.
"""
import hashlib
import json
from .opportunities import encoded, validate as validate_pack


def install(db):
    db.execute('CREATE TABLE IF NOT EXISTS canonical_initiatives(pack TEXT PRIMARY KEY,actor TEXT,digest TEXT,seq INTEGER)')


def validate(project, identity, row, actors):
    if project is None:return
    places={p[7:] for p in row['places'] if p.startswith('native:') and not p[7:].startswith('GeneratedWorld_')}
    validate_pack(project,places)
    if any(q['scope']!='place' for q in project['qualities'].values()):
        raise ValueError('Cast initiatives use public shared qualities only')
    if any('mystery' in s for s in project['scenes'].values()):
        raise ValueError('Cast initiatives cannot inspect private mystery progress')
    assigned={a for s in project['scenes'].values() for a in s.get('actors',[])}
    if identity not in assigned or assigned-set(actors):
        raise ValueError('Initiative requires its owner and only existing actors')
    if not any('actors' not in s for s in project['scenes'].values()):
        raise ValueError('Initiative needs a real player-facing scene')


def publish(server, change):
    project=change['after'].get('initiative')
    if project is None:return
    identity=change['character_id'];document=encoded(project)
    digest=hashlib.sha256(document.encode()).hexdigest()
    old=server.db.execute('SELECT actor,digest FROM canonical_initiatives WHERE pack=?',(project['id'],)).fetchone()
    existing=server.db.execute('SELECT document FROM story_packs WHERE id=?',(project['id'],)).fetchone()
    if old or existing:
        if old!=(identity,digest) or existing!=(document,):
            raise ValueError('Initiative identity already belongs to different immutable content or owner')
        return
    if server.db.execute('SELECT count(*) FROM canonical_initiatives WHERE actor=?',(identity,)).fetchone()[0]>=8:
        raise ValueError('Eight initiative limit reached for this actor')
    if server.db.execute('SELECT count(*) FROM story_packs').fetchone()[0]>=64:
        raise ValueError('World story capacity reached')
    # Caller owns the module admission transaction. Opportunities.publish would
    # commit that outer transaction early; insert only after identical validation.
    validate_pack(project,server.opportunities.places)
    server.db.execute('INSERT INTO story_packs VALUES(?,?)',(project['id'],document))
    seq=server.memory.append('canonical_initiative_published',dict(
        character_id=identity,title=project['title'],pack=project['id'],digest=digest,
        actors=sorted({a for s in project['scenes'].values() for a in s.get('actors',[])}),
        based_on=change['after']['evidence'],places=change['after']['places'],
        publication='public_cast_initiative',outcome='executable_shared_project_installed',
        limits='Authored shared choices, not travel, physical labor, participation, rewards or campaign progression.'))
    server.db.execute('INSERT INTO canonical_initiatives VALUES(?,?,?,?)',(project['id'],identity,digest,seq))
    server.revision=seq


def relevant(event,identity,row):
    return (event.get('event')=='canonical_initiative_published'
            and event.get('publication')=='public_cast_initiative'
            and event.get('outcome')=='executable_shared_project_installed'
            and (identity in event.get('actors',[]) or bool(set(row['places'])&set(event.get('places',[])))))


def assessment(event,identity,target,row):
    # Evidence supports only a directional interpretation of a real public
    # choice by the target. It never proves a meeting or reciprocal feeling.
    from .canonical_world_actions import relevant as action_relevant
    return (action_relevant(event,identity,row) and event.get('character_id')==target
            and event.get('outcome')=='shared_story_state_committed')


def view(server,identity=None):
    result=[]
    for key,owner,digest,seq,raw in server.db.execute('SELECT i.pack,i.actor,i.digest,i.seq,p.document FROM canonical_initiatives i JOIN story_packs p ON p.id=i.pack ORDER BY i.seq DESC'):
        if identity is not None and owner!=identity:continue
        pack=json.loads(raw);places=[]
        for place in sorted({s['place'] for s in pack['scenes'].values()}):
            data=server.db.execute('SELECT revision,state,played FROM story_places WHERE pack=? AND place=?',(key,place)).fetchone()
            revision,state,played=(data[0],json.loads(data[1]),json.loads(data[2])) if data else (0,{k:q['initial'] for k,q in pack['qualities'].items()},[])
            places.append(dict(place=place,revision=revision,qualities=state,completed_scenes=played))
        result.append(dict(pack=key,owner=owner,title=pack['title'],digest=digest,publication=seq,places=places))
    return result


def lines(server,identity):
    rows=view(server,identity)
    result=['Public shared projects. Choices change shared story state, not native story flags.']
    for row in rows[:3]:
        result.extend([row['title'], '/story '+row['pack']+' at '+', '.join(p['place'] for p in row['places'])])
        for p in row['places']:
            result.append(str(len(p['completed_scenes']))+' committed choices; revision '+str(p['revision'])+'.')
    return result if rows else ['This actor has not published a shared project.']
