"""Cast-owned field studies installed on existing exact archived geometry.

No terrain edits, actor travel, item collection, or automatic player enrollment.
Publication participates in the normal character-admission transaction.
"""
import hashlib
import json
import re
from .shared_cave import SharedCave


def validate(study):
    if study is None:return
    if (type(study) is not dict or set(study)!={'revision','title','sites'}
            or type(study['revision']) is not str or not re.fullmatch('[0-9a-f]{64}',study['revision'])
            or type(study['title']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,55}",study['title'])
            or type(study['sites']) is not list or not 2<=len(study['sites'])<=8):
        raise ValueError('study requires exact archived revision, literal title and 2..8 sites')
    ids=set();points=set()
    for site in study['sites']:
        if (type(site) is not dict or set(site)!={'id','x','y'}
                or type(site['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',site['id'])
                or site['id'] in ids or site['id'] in ('entry','exit')
                or any(type(site[k]) is not int or not 2<=site[k]<=124 for k in ('x','y'))):
            raise ValueError('study sites need unique literal IDs and bounded coordinates')
        point=(site['x'],site['y'])
        if any(abs(point[0]-x)+abs(point[1]-y)<=2 for x,y in points):
            raise ValueError('study sites must have distinct arrival neighborhoods')
        ids.add(site['id']);points.add(point)


def publish(server,change):
    row=change['after'];study=row.get('study');identity=change['character_id']
    if not study or study==(change.get('before') or {}).get('study'):return
    validate(study)
    archive=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(study['revision'],)).fetchone()
    if not server.archive_generated_areas or not archive:raise ValueError('study needs an existing immutable archived map')
    cave=SharedCave(archive[0])
    if cave.version!=16:raise ValueError('study requires supported plain XL survey geometry')
    if any(not cave.walkable(site['x'],site['y']) for site in study['sites']):
        raise ValueError('study site is not walkable in the exact archived map')
    place=server.memory.place(study['revision'])
    if not place:raise ValueError('study needs an archived place identity')
    document=json.dumps(study,sort_keys=True,separators=(',',':'))
    digest=hashlib.sha256(document.encode()).hexdigest()
    existing=server.db.execute('SELECT actor,digest FROM canonical_studies WHERE revision=?',(study['revision'],)).fetchone()
    if existing:
        if existing!=(identity,digest):raise ValueError('study revision already belongs to another immutable project')
        return
    if server.db.execute('SELECT 1 FROM survey_routes WHERE revision=?',(study['revision'],)).fetchone():
        raise ValueError('existing survey cannot be replaced by a character study')
    if server.db.execute('SELECT count(*) FROM canonical_studies WHERE actor=?',(identity,)).fetchone()[0]>=8:
        raise ValueError('character study capacity reached')
    server.db.execute('INSERT INTO survey_routes VALUES (?,?)',(study['revision'],json.dumps(study['sites'],sort_keys=True)))
    server.db.execute('INSERT INTO canonical_studies VALUES (?,?,?,?)',(study['revision'],identity,digest,document))
    server.revision=server.memory.append('canonical_study_published',dict(
        character_id=identity,character_name=change['character_name'],title=study['title'],
        revision=study['revision'],place_id=place,sites=study['sites'],digest=digest,
        based_on=row['evidence'],places=[place],publication='public_cast_study',
        outcome='immutable_survey_installed',basis='archived_geometry_validation_and_atomic_registration'))


def relevant(event,identity):
    return (event.get('event')=='landmark_discovery_shared'
            and event.get('publication')=='explicit_player_share'
            and event.get('study_actor')==identity
            and type(event.get('study_digest')) is str)


def lines(server,identity):
    rows=server.db.execute('SELECT revision,document FROM canonical_studies WHERE actor=? ORDER BY rowid DESC LIMIT 3',(identity,)).fetchall()
    result=['Optional field studies. Visits are private unless you explicitly share them.']
    for revision,raw in rows:
        study=json.loads(raw);active=bool(server.shared_cave and server.shared_cave.identity==revision)
        result += [study['title'],f"{len(study['sites'])} sites; map revision {revision[:12]}.",
                   'Enter the current generated outdoor map; use /explore start.' if active else 'This exact map is not active. No automatic map switch.',
                   'No travel or discoveries by the character are implied.']
    return result if rows else ['This character has not installed a field study.']
