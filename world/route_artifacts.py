"""Owner-held route recipes, validated against exact archived geometry.

No provider identity, prompt, private trainer state, or claimed visits are stored.
The hash binds bytes, not authorship or trust in an external artifact.
"""
import json
from .route_landscape import compile_plan, MAX_INPUT


def create(plan):
    if len(json.dumps(plan).encode()) > MAX_INPUT:
        raise ValueError('route plan too large')
    blob, report = compile_plan(plan)
    artifact = dict(schema=1, revision=report['revision'], plan=plan, report=report)
    if len(json.dumps(artifact).encode()) > MAX_INPUT * 8:
        raise ValueError('route artifact too large')
    return blob, artifact


def validate(artifact, blob=None, server=None):
    if type(artifact) is dict and artifact.get('schema') == 2:
        if server is None or blob is None:raise ValueError('derived artifact requires its authority archive')
        parent=load(server,artifact.get('parent'))
        row=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(artifact.get('parent'),)).fetchone()
        expected=derived(parent,row[0],blob,artifact.get('construction'))
        return _same_artifact(artifact,expected)

    if (type(artifact) is not dict or set(artifact) != {'schema','revision','plan','report'}
            or type(artifact['schema']) is not int or artifact['schema'] != 1
            or len(json.dumps(artifact).encode()) > MAX_INPUT * 8):
        raise ValueError('invalid route artifact')
    compiled, expected = create(artifact['plan'])
    if json.dumps(expected, sort_keys=True) != json.dumps(artifact, sort_keys=True) or (blob is not None and compiled != blob):
        raise ValueError('route artifact does not match compiled map')
    return json.dumps(expected, sort_keys=True, separators=(',', ':'))


def archive(server, artifact, blob):
    """Caller owns the map publication transaction and lock."""
    encoded = validate(artifact, blob, server)
    old = server.db.execute('SELECT artifact FROM route_artifacts WHERE revision=?', (artifact['revision'],)).fetchone()
    if old and old[0] != encoded:
        raise ValueError('route artifact is already fixed for this revision')
    server.db.execute('INSERT OR IGNORE INTO route_artifacts VALUES (?,?)', (artifact['revision'], encoded))


def _same_artifact(artifact, expected):
    encoded=json.dumps(artifact,sort_keys=True,separators=(',', ':'))
    if len(encoded.encode()) > MAX_INPUT*8 or encoded != json.dumps(expected,sort_keys=True,separators=(',', ':')):
        raise ValueError('invalid derived route artifact')
    return encoded


def load(server, revision):
    # Iterative replay avoids a recursion limit on long-lived construction chains.
    chain=[];seen=set()
    while True:
        if type(revision) is not str or revision in seen:raise ValueError('invalid route ancestry')
        seen.add(revision)
        row=server.db.execute('SELECT artifact FROM route_artifacts WHERE revision=?',(revision,)).fetchone()
        saved=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(revision,)).fetchone()
        if row is None or saved is None:raise ValueError('archived route artifact unavailable')
        artifact=json.loads(row[0]);blob=saved[0]
        if artifact.get('revision')!=revision:raise ValueError('route artifact revision mismatch')
        if artifact.get('schema')==1:
            validate(artifact,blob);break
        if artifact.get('schema')!=2:raise ValueError('unknown route artifact schema')
        chain.append((artifact,blob));revision=artifact.get('parent')
    for child, child_blob in reversed(chain):
        expected=derived(artifact,blob,child_blob,child.get('construction'))
        _same_artifact(child,expected)
        artifact,blob=child,child_blob
    return artifact


def derived(parent, parent_blob, blob, construction):
    """Replay one additive construction, with no invented route-graph claims."""
    import hashlib
    from .frontier_outposts import compile_outpost
    from .shared_cave import SharedCave
    trail=type(construction) is dict and construction.get('kind')=='survey_trail'
    if trail:
        from .trail_projects import compile_trail
        compiled,construction_report=compile_trail(parent_blob,construction)
    else:
        compiled, construction_report = compile_outpost(parent_blob, construction)
    if compiled != blob:
        raise ValueError('construction artifact does not reproduce map')
    before, after = SharedCave(parent_blob), SharedCave(blob)
    landmarks = [dict(site) for site in parent['report']['landmarks']]
    retained, changed = [], []
    for site in landmarks:
        if site['id'] in ('entry', 'exit'):continue
        radius=max(1, site['radius'])
        equal=all(before._rows[y][x]==after._rows[y][x]
                  for y in range(max(0,site['y']-radius),min(127,site['y']+radius+1))
                  for x in range(max(0,site['x']-radius),min(127,site['x']+radius+1)))
        (retained if equal else changed).append(site['id'])
    added=[]
    if not trail:
        identifier='outpost_'+hashlib.sha256(blob).hexdigest()[:12]
        landmarks.append(dict(id=identifier,x=construction['x']+construction['width']//2,
                              y=construction['y']+construction['height']//2,
                              radius=max(construction['width'],construction['height'])//2+1))
        added=[identifier]
    return dict(schema=2,revision=after.identity,parent=before.identity,construction=construction,
                report=dict(landmarks=landmarks,retained=retained,changed=changed,new=added,
                            construction=construction_report))


def derive(server, parent_revision, blob, construction):
    row=server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?',(parent_revision,)).fetchone()
    if row is None:raise ValueError('construction parent unavailable')
    # Legacy maps without a recipe have no landmark identities to inherit.
    if server.db.execute('SELECT 1 FROM route_artifacts WHERE revision=?',(parent_revision,)).fetchone() is None:
        return None
    return derived(load(server,parent_revision),row[0],blob,construction)
