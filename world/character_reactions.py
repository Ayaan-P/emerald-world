"""Opt-in, result-driven author turns for already registered world characters.

No arc, timer, fabricated outcome, native script replacement or automatic model
startup. Only public completion of this character's exact offered expedition
can schedule another bounded action through the configured developer GM.
"""
import json
import re
import time
import uuid


def setup(queue):
    queue.db.execute('''CREATE TABLE IF NOT EXISTS character_reactions(
        id TEXT PRIMARY KEY, purpose TEXT NOT NULL, world TEXT NOT NULL,
        cursor INTEGER NOT NULL)''')
    queue.db.commit()


def configure(queue, inspection, identity, purpose):
    from .characters import records
    data = inspection.get('data', inspection)
    if inspection.get('ok') is not True or identity not in records(data.get('state', {})):
        raise ValueError('follow requires an inspected existing world character')
    memory = data.get('world_memory', {})
    if (not re.fullmatch('[A-Za-z0-9_-]{1,24}', identity)
            or type(purpose) is not str or not 1 <= len(purpose) <= 1024
            or type(memory.get('through')) is not int or not memory.get('world_id')):
        raise ValueError('invalid character reaction enrollment')
    with queue.db:
        if queue.db.execute('SELECT count(*) FROM character_reactions').fetchone()[0] >= 8 and not queue.db.execute('SELECT 1 FROM character_reactions WHERE id=?', (identity,)).fetchone():
            raise ValueError('at most eight followed characters')
        # Reconfiguration starts at the inspected boundary, never replays old wins.
        queue.db.execute('INSERT OR REPLACE INTO character_reactions VALUES(?,?,?,?)',
                         (identity, purpose, memory['world_id'], memory['through']))
        cancel_queued(queue, identity)


def cancel_queued(queue, identity):
    queue.db.execute("UPDATE requests SET status='interrupted',finished=?,result=? WHERE kind='character' AND player=? AND status='queued'",
                     (time.time(), json.dumps({'ok': False, 'reason': 'character enrollment changed'}), identity))


def unfollow(queue, identity):
    with queue.db:
        queue.db.execute('DELETE FROM character_reactions WHERE id=?', (identity,))
        cancel_queued(queue, identity)


def subscriptions(queue):
    return [dict(row) for row in queue.db.execute('SELECT * FROM character_reactions ORDER BY id')]


def observe(queue, inspection, fetch, *, enqueue=True):
    """Consume bounded authoritative pages without losing events in a busy world."""
    selected = subscriptions(queue)
    if not selected:
        return []
    from .characters import records
    data = inspection.get('data', inspection)
    cast = records(data.get('state', {}))
    memory = data.get('world_memory', {})
    queued = []
    for sub in selected:
        if sub['world'] != memory.get('world_id'):
            raise ValueError('followed character belongs to another world')
        page = fetch(dict(command='world_history', after=sub['cursor'], limit=32,
                          through=memory['through']))
        if (page.get('ok') is not True or page.get('world_id') != sub['world']
                or page.get('through') != memory['through']
                or type(page.get('cursor')) is not int
                or not sub['cursor'] <= page['cursor'] <= memory['through']
                or type(page.get('events')) is not list):
            raise ValueError('character history page does not match inspection')
        character = cast.get(sub['id'], {})
        offer = character.get('offer') or {}
        previous = sub['cursor']
        for event in page['events']:
            if type(event.get('seq')) is not int or not previous < event['seq'] <= page['cursor']:
                raise ValueError('invalid character history ordering')
            previous = event['seq']
        with queue.db:
            queue.db.execute('BEGIN IMMEDIATE')
            current = queue.db.execute('SELECT * FROM character_reactions WHERE id=?', (sub['id'],)).fetchone()
            if current is None or dict(current) != sub:
                continue  # host changed/cancelled enrollment during history fetch
            # Never coalesce by dropping earlier results. Leave the page pending
            # until an existing actor turn is terminal; other actors still run.
            if queue.db.execute("SELECT 1 FROM requests WHERE kind='character' AND player=? AND status IN ('queued','running')", (sub['id'],)).fetchone():
                continue
            through = page['cursor']
            for event in page['events']:
                if (not enqueue or character.get('status') != 'active'
                        or event.get('event') != 'guild_goal_completed'
                        or event.get('publication') != 'guild_leader_opt_in'
                        or event.get('character_id') != sub['id']
                        or event.get('character_offer_id') != offer.get('id')
                        or event.get('character_offer_revision') != offer.get('revision')
                        or not offer):
                    continue
                identifier = uuid.uuid4().hex
                reaction = dict(world_id=sub['world'], id=sub['id'], expected_version=character['version'],
                                evidence=event['seq'], purpose=sub['purpose'])
                queue.db.execute('INSERT INTO requests(id,player,text,kind,status,created,result) VALUES(?,?,?,?,?,?,?)',
                                 (identifier, sub['id'], 'Choose one next action for this existing character after its publicly completed expedition. Do not invent a predetermined arc, duplicate a canonical NPC, or claim unobserved achievements.',
                                  'character', 'queued', time.time(), json.dumps(reaction)))
                queued.append(identifier)
                through = event['seq']
                break
            queue.db.execute('UPDATE character_reactions SET cursor=? WHERE id=?', (through, sub['id']))
            queue.db.execute("DELETE FROM requests WHERE kind='character' AND status NOT IN ('queued','running') AND seq NOT IN (SELECT seq FROM requests WHERE kind='character' AND status NOT IN ('queued','running') ORDER BY seq DESC LIMIT 64)")
    return queued


def prepare(context, fetch):
    """Re-read exact public evidence; a queued packet cannot authorize a stale action."""
    runtime = context.get('runtime', {})
    if runtime.get('kind') != 'character':
        return None
    reaction = runtime.get('observed_event', {})
    data = context.get('data', context)
    character = data.get('state', {}).get('world_characters', {}).get(reaction.get('id'))
    memory = data.get('world_memory', {})
    if (not character or character['version'] != reaction.get('expected_version')
            or memory.get('world_id') != reaction.get('world_id')
            or type(reaction.get('evidence')) is not int or reaction['evidence'] > memory['through']):
        raise ValueError('character changed before its reaction turn')
    seq = reaction['evidence']
    page = fetch(dict(command='world_history', after=seq-1, through=seq, limit=1))
    events = page.get('events', [])
    offer = character.get('offer') or {}
    if (page.get('ok') is not True or page.get('world_id') != reaction['world_id']
            or len(events) != 1 or events[0].get('seq') != seq
            or events[0].get('event') != 'guild_goal_completed'
            or events[0].get('publication') != 'guild_leader_opt_in'
            or events[0].get('character_id') != reaction['id']
            or events[0].get('character_offer_id') != offer.get('id')
            or events[0].get('character_offer_revision') != offer.get('revision')):
        raise ValueError('character reaction lacks exact public offer completion')
    context.setdefault('recalled_history', {}).setdefault('events', []).extend(events)
    context['character_reaction'] = dict(reaction, instruction='Return character_actions/tests with exactly this actor, or an empty action list to wait. Use the exact evidence. Only supported current map/dialogue/team/offer changes; no canonical script or save flag replacement.')
    return reaction


def check_response(response, reaction):
    if not reaction:
        return
    if type(response) is not dict or set(response) != {'character_actions', 'tests'}:
        raise ValueError('character reactions require bounded typed actions, not arbitrary source')
    actions = response['character_actions']
    if type(actions) is not list or len(actions) > 1:
        raise ValueError('one character reaction action or an explicit wait required')
    if actions and (actions[0].get('id') != reaction['id']
                    or actions[0].get('expected_version') != reaction['expected_version']
                    or reaction['evidence'] not in actions[0].get('evidence', [])):
        raise ValueError('character action does not match selected actor, version and evidence')
