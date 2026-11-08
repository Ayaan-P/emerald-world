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


def validate(artifact, blob=None):
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
    encoded = validate(artifact, blob)
    old = server.db.execute('SELECT artifact FROM route_artifacts WHERE revision=?', (artifact['revision'],)).fetchone()
    if old and old[0] != encoded:
        raise ValueError('route artifact is already fixed for this revision')
    server.db.execute('INSERT OR IGNORE INTO route_artifacts VALUES (?,?)', (artifact['revision'], encoded))


def load(server, revision):
    row = server.db.execute('SELECT artifact FROM route_artifacts WHERE revision=?', (revision,)).fetchone()
    saved = server.db.execute('SELECT template FROM generated_area_archive WHERE identity=?', (revision,)).fetchone()
    if row is None or saved is None:
        raise ValueError('archived route artifact unavailable')
    artifact = json.loads(row[0])
    validate(artifact, saved[0])
    return artifact
