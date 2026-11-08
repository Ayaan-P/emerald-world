"""Read-only discovery of real steward completions for opt-in agent growth."""
import json


def candidates(server, after=0, limit=16, *, expected_world_id=None, expected_place_id=None):
    if type(after) is not int or not 0 <= after <= 2**63-1 or type(limit) is not int or not 1<=limit<=32:
        raise ValueError('invalid growth cursor')
    memory=server.memory.context(server); active=memory['active_area']
    if expected_world_id is not None and (expected_world_id!=memory['world_id'] or expected_place_id!=active.get('place_id')):
        raise ValueError('growth inspection world or place changed')
    result=dict(ok=True,world_id=memory['world_id'],through=memory['through'],cursor=memory['through'],
                place_id=active.get('place_id'),candidates=[],blocked=None)
    if not server.archive_generated_areas or active.get('template_version')!=16:
        result['blocked']='active durable XL area required';result['cursor']=after;return result
    from .characters import records
    if len(records(server.module_state))>=8:
        result['blocked']='persistent character capacity reached';result['cursor']=after;return result
    rows=server.db.execute('''SELECT e.seq,e.data FROM events e
        JOIN settlement_foundings f ON json_extract(e.data,'$.character_id')=f.resident_id
          AND json_extract(e.data,'$.character_offer_id')=f.offer_id
          AND json_extract(e.data,'$.character_offer_revision')=f.offer_revision
        LEFT JOIN settlement_foundings used ON used.outcome_seq=e.seq
        WHERE e.kind='world_memory' AND json_extract(e.data,'$.event')='guild_goal_completed'
          AND e.seq>? AND f.place_id=? AND used.outcome_seq IS NULL ORDER BY e.seq LIMIT ?''',
        (after,active['place_id'],limit)).fetchall()
    # A committed completion remains evidence when its resident is now away.
    # Per-place consumer cursors keep other archived places pending.
    result['cursor']=rows[-1][0] if len(rows)==limit else memory['through']
    result['candidates']=[dict(seq=seq,character_id=json.loads(data)['character_id']) for seq,data in rows]
    return result
