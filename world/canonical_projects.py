"""Cast-authored playable practice courses, not simulated construction/travel."""
import copy
import hashlib
import json
from .field_relays import COURSE, encoded, validate


def validate_project(project):
    if project is None:return
    if (type(project) is not dict or set(project)!={'kind','title','limit','mounted'}
            or project['kind']!='petalburg_relay' or type(project['title']) is not str
            or not 1<=len(project['title'])<=55 or any(not 32<=ord(c)<=126 for c in project['title'])
            or type(project['limit']) is not int or not 30<=project['limit']<=900
            or type(project['mounted']) is not bool):
        raise ValueError('project requires a bounded Petalburg relay title, time limit and mount requirement')


def course_for(identity, project):
    validate_project(project)
    course=copy.deepcopy(COURSE)
    digest=hashlib.sha256(encoded(project).encode()).hexdigest()[:12]
    course.update(id='cast_'+identity.removeprefix('canon_')+'_'+digest,
                  title=project['title'],limit=project['limit'],mounted=project['mounted'])
    return course


def publish(server, change):
    """Same transaction as authored state. Does not start a run or commit early."""
    identity=change['character_id'];project=change['after'].get('project')
    if not project or project==(change.get('before') or {}).get('project'):return
    course=course_for(identity,project)
    validate(course,server.relays.coords,(server.cave_map,server.wilds_map))
    document=encoded(course);digest=hashlib.sha256(document.encode()).hexdigest()
    existing=server.db.execute('SELECT document FROM relay_courses WHERE id=?',(course['id'],)).fetchone()
    receipt=server.db.execute('SELECT actor,digest FROM canonical_projects WHERE course=?',(course['id'],)).fetchone()
    if existing or receipt:
        if existing is None or receipt!=(identity,digest) or existing[0]!=document:
            raise ValueError('character project conflicts with an existing course')
        return # Immutable content was already installed; never publish twice.
    if server.db.execute('SELECT count(*) FROM canonical_projects WHERE actor=?',(identity,)).fetchone()[0]>=8:
        raise ValueError('character project capacity reached')
    if server.db.execute('SELECT count(*) FROM relay_courses').fetchone()[0]>=64:
        raise ValueError('relay course capacity reached')
    server.db.execute('INSERT INTO relay_courses VALUES(?,?)',(course['id'],document))
    server.db.execute('INSERT INTO canonical_projects VALUES(?,?,?)',(course['id'],identity,digest))
    server.revision=server.memory.append('canonical_project_published',dict(
        character_id=identity,character_name=change['character_name'],character_version=change['after']['version'],
        course=course['id'],title=course['title'],limit=course['limit'],mounted=course['mounted'],digest=digest,
        based_on=change['after']['evidence'],publication='public_cast_project',places=['native:PetalburgCity'],
        outcome='immutable_relay_course_installed',basis='authority_course_validation_and_atomic_installation'))


def public_project(event, places):
    return (event.get('event')=='canonical_project_published' and event.get('publication')=='public_cast_project'
            and event.get('outcome')=='immutable_relay_course_installed'
            and 'native:PetalburgCity' in places)


def lines(server, identity):
    rows=server.db.execute('SELECT p.course,c.document FROM canonical_projects p JOIN relay_courses c ON c.id=p.course WHERE p.actor=? ORDER BY p.rowid DESC LIMIT 3',(identity,)).fetchall()
    result=['Published practice courses. Joining is optional; records remain private.']
    for key,raw in rows:
        course=json.loads(raw)
        result.extend([course['title'],f"{course['limit']} seconds; "+('mounts required.' if course['mounted'] else 'on-foot practice.'),
                       '/guild relay start '+key])
    return result if rows else ['This character has not published a practice course.']
