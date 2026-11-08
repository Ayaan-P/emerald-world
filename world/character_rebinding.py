"""Explicit same-place revision migration for unchanged persistent NPC locations.

A source wrapper preserves the migration on later authored mechanic ticks.
No global place alias or cross-map character lookup is introduced.
"""
from copy import deepcopy
import hashlib
import json
from .mechanics import Candidate, validate_objects


def prepare(server, previous, revision):
    affected = [obj for obj in server.objects if obj.get('region_revision') == previous]
    if server.db.execute('SELECT 1 FROM world_region_revisions WHERE revision=?', (previous,)).fetchone():
        raise ValueError('opened immutable region characters cannot migrate with the shared slot')
    if server.job is not None or server.deployment is not None:
        raise ValueError('wait for pending mechanic work before rebinding characters')
    if any(peer.get('character_pending') for peer in server.peers.values()):
        raise ValueError('finish pending character interactions before construction')
    if not affected:
        return None
    if server.candidate is None or hashlib.sha256(server.candidate.source.encode()).hexdigest() != server.candidate.sha256:
        raise ValueError('character source is unavailable or changed')
    row = server.db.execute('SELECT sha256,objects FROM module WHERE singleton=1').fetchone()
    if row is None or row[0] != server.candidate.sha256 or json.loads(row[1]) != server.objects:
        raise ValueError('character placements are not durably committed')
    from .characters import validate_transition
    from .region_characters import validate_region_objects
    validate_transition(server.module_state, server.module_state, server.objects, server.db)
    validate_region_objects(server, server.objects, server.module_state)
    from .character_walks import validate_walks, walking
    validate_walks(server, server.module_state, server.module_state, server.objects, restoring=True)
    if any(walking(server.module_state, obj['id']) for obj in affected):
        raise ValueError('finish character walks before construction')
    state = deepcopy(server.module_state)
    for obj in affected:
        control = state.get('world_character_controls', {}).get(obj['id'])
        if control and control.get('object') is not None:
            control['object']['region_revision'] = revision
    positions = {obj['id']: [obj[key] for key in ('group', 'num', 'x', 'y')] for obj in affected}
    objects = [dict(obj, region_revision=revision) if obj in affected else dict(obj) for obj in server.objects]
    validate_objects(objects)
    # Capture the previous callable in the default argument. A later migration
    # can append another wrapper without global-name recursion or source edits.
    suffix = '''

def update(context, state, _previous=update):
    result = _previous(context, state)
    objects = []
    for original in result.get('objects', []):
        obj = dict(original)
        positions = %r
        if obj.get('id') in positions and obj.get('region_revision') == %r:
            if [obj[key] for key in ('group', 'num', 'x', 'y')] != positions[obj['id']]:
                raise ValueError('rebound character moved in obsolete geometry; author its current revision explicitly')
            obj['region_revision'] = %r
        objects.append(obj)
    import copy
    result = copy.deepcopy(result)
    result['objects'] = objects
    # Action reducers retain their own object, including completed walks.
    # Keep that durable control in the same revision as its rendered object.
    for obj in objects:
        if obj['id'] in positions:
            control = result['state'].get('world_character_controls', {}).get(obj['id'])
            if control and control.get('object') is not None and control['object'].get('region_revision') == %r:
                control['object'] = dict(obj)
    return result
''' % (positions, previous, revision, previous)
    source = server.candidate.source + suffix
    if len(source.encode()) > 256 * 1024:
        raise ValueError('continued character source exceeds mechanic size limit')
    compile(source, '<character-continuation>', 'exec')
    return dict(candidate=Candidate(source, hashlib.sha256(source.encode()).hexdigest()),
                objects=objects, state=state, previous_hash=server.candidate.sha256, ids=sorted(positions))


def persist(server, continuation, place_id, previous, revision):
    """Called only inside the same transaction that archives the new geometry."""
    from .region_characters import validate_region_objects
    from .characters import validate_transition
    objects = continuation['objects']; candidate = continuation['candidate']
    state = continuation.get('state', server.module_state)
    tiles = continuation.get('tiles', server.tiles)
    cursor = continuation.get('cursor', server.interaction_cursor)
    validate_region_objects(server, objects, state)
    from .character_walks import validate_walks
    # The additive geometry handoff retains completed walk receipts and paths.
    # Check their full new scope as a restore, not as a new motion step.
    validate_walks(server, state, state, objects, restoring=True)
    changes = validate_transition(server.module_state, state, objects, server.db)
    current = server.db.execute('SELECT sha256 FROM module WHERE singleton=1').fetchone()
    if (current[0] if current else None) != continuation['previous_hash']:
        raise ValueError('character source changed during construction')
    if current:
        server.db.execute('UPDATE module SET source=?,sha256=?,state=?,tiles=?,objects=?,interaction_cursor=? WHERE singleton=1',
            (candidate.source, candidate.sha256, json.dumps(state), json.dumps(tiles), json.dumps(objects), cursor))
    else:
        server.db.execute('INSERT INTO module(singleton,source,sha256,state,tiles,objects,interaction_cursor) VALUES(1,?,?,?,?,?,?)',
            (candidate.source, candidate.sha256, json.dumps(state), json.dumps(tiles), json.dumps(objects), cursor))
    if continuation.get('clear_error'):
        server.db.execute('INSERT OR REPLACE INTO status VALUES(1,NULL)')
    server.memory.append('mechanic_changed', dict(module_hash=candidate.sha256,
        previous_module_hash=continuation['previous_hash'], cause='place_continued',
        interaction_cursor=cursor, places=[place_id],
        before=dict(tiles=server.tiles, objects=server.objects),
        after=dict(tiles=tiles, objects=objects),
        previous_revision=previous, revision=revision, rebound_characters=continuation['ids']))
    from .world_memory import overlay_places
    for change in changes:
        change['places'] = overlay_places([], [obj for obj in server.objects + objects
            if obj['id'] == change['character_id']], server.db)
        server.memory.append('character_changed', change)
