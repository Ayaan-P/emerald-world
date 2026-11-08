"""Durable authored characters carried by the existing atomic mechanic state.

These are public fictional NPC records, not human trainer/save information.
Team records are author intent until the native battle adapter confirms support.
"""
import json
from pathlib import Path
import re

KEY = 'world_characters'
FIELDS = {'version', 'name', 'role', 'goals', 'relationships', 'team', 'status',
          'object_id', 'evidence', 'reason'}


def _text(value, maximum):
    if type(value) is not str or not 1 <= len(value) <= maximum or any(ord(c) < 32 for c in value):
        raise ValueError('invalid character text')


def records(state):
    value = state.get(KEY, {}) if type(state) is dict else {}
    if type(value) is not dict or len(value) > 8:
        raise ValueError('at most eight persistent characters')
    species = set(json.loads(Path(__file__).with_name('expansion_species.json').read_text())['species'].values())
    for identity, character in value.items():
        if type(identity) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}', identity):
            raise ValueError('invalid character identity')
        if type(character) is not dict or not FIELDS <= set(character) or set(character)-FIELDS-{'offer'}:
            raise ValueError('invalid character fields')
        if type(character['version']) is not int or not 1 <= character['version'] <= 2**31-1:
            raise ValueError('invalid character version')
        _text(character['name'], 32)
        _text(character['role'], 160)
        _text(character['reason'], 240)
        if character['object_id'] != identity or character['status'] not in ('active', 'away', 'retired'):
            raise ValueError('invalid character presence')
        if character.get('offer') is not None:
            validate_offer(character['offer'])
            if character['status'] != 'active':
                raise ValueError('only active characters may offer an expedition')
        goals = character['goals']
        if type(goals) is not list or len(goals) > 4:
            raise ValueError('invalid character goals')
        for goal in goals:
            _text(goal, 160)
        relations = character['relationships']
        if type(relations) is not dict or len(relations) > 8:
            raise ValueError('invalid character relationships')
        for target, relationship in relations.items():
            if target not in value or target == identity:
                raise ValueError('relationships must reference other public characters')
            _text(relationship, 120)
        team = character['team']
        if type(team) is not list or not 1 <= len(team) <= 6:
            raise ValueError('character team must contain one to six Pokemon')
        for mon in team:
            if type(mon) is not dict or set(mon) != {'species', 'level'}:
                raise ValueError('invalid character team member')
            if type(mon['species']) is not int or mon['species'] not in species:
                raise ValueError('unknown character species')
            if type(mon['level']) is not int or not 1 <= mon['level'] <= 100:
                raise ValueError('invalid character level')
        evidence = character['evidence']
        if (type(evidence) is not list or len(evidence) > 8 or
                any(type(seq) is not int or seq < 1 for seq in evidence) or
                len(set(evidence)) != len(evidence)):
            raise ValueError('invalid character evidence')
    return value


def validate_transition(before, after, objects, db):
    validate_history_cursor(before, after, db)
    old, new = records(before), records(after)
    if old.keys() - new.keys():
        raise ValueError('persistent characters must be retained; retire explicitly')
    visible = {obj['id']: obj for obj in objects}
    changes = []
    for identity, character in new.items():
        if (character['status'] == 'active') != (identity in visible):
            raise ValueError('active characters must have a rendered object; away/retired must not')
        previous = old.get(identity)
        if previous == character:
            continue
        old_offer = previous.get('offer') if previous else None
        new_offer = character.get('offer')
        if old_offer and new_offer and old_offer['id'] == new_offer['id']:
            if new_offer['revision'] < old_offer['revision'] or (new_offer['revision'] == old_offer['revision'] and new_offer != old_offer):
                raise ValueError('changed offer terms require a newer offer revision')
        if character['version'] != (previous['version'] + 1 if previous else 1):
            raise ValueError('character version must advance exactly once')
        if previous and previous['status'] == 'retired' and character['status'] != 'retired':
            raise ValueError('retired character identity cannot be reused')
        for seq in character['evidence']:
            row = db.execute('SELECT kind FROM events WHERE seq=?', (seq,)).fetchone()
            if row is None or row[0] != 'world_memory':
                raise ValueError('character evidence must reference committed public world history')
        changes.append({'character_id': identity, 'before': previous, 'after': character,
                        'interpretation': 'agent_authored_transition_not_proof_of_battle_or_catch'})
    return changes


def author_contract():
    return {
        'state_key': KEY,
        'record_fields': sorted(FIELDS),
        'optional_offer': {'id':'stable offer ID','revision':'positive revision, increase when destination/count changes','kind':'expedition','place_id':'native:canonical map or area:UUID with required region_revision64hex','target':'1..50 guild members','region_revision':'required64hex only for area:UUID destinations'},
        'offer_consent':'CHARQUEST1 native explicit acceptance; guild leader only, existing chronicle ON required, never toggle publication; completion uses existing guild authority',
        'team_member': {'species': 'enabled numeric species ID', 'level': 'integer 1..100'},
        'presence': 'active requires a matching top-level objects entry; away/retired must not render',
        'identity': 'stable ID matches object_id, never delete; retire explicitly; version starts at 1 and increments exactly once per committed changed record, not once per processed history event; coalesce a batch before assigning the version',
        'evidence': 'up to eight exact public world_memory sequence IDs; creation may have none; rationale is authored interpretation, never proof of battles or catches',
        'runtime': 'character_history is an ordered bounded batch after state.character_history_cursor. Process every event once, then acknowledge through in that state key. Empty or has_more does not mean history is absent. Preserve the cursor across script replacements. world_history is only the recent tail.',
        'interaction_order': 'Native dialogue emits INTERACT before battle consent. Keep meet-memory outside the versioned character record if a battle is offered; moving or revising the character during that prompt intentionally invalidates the challenge.',
        'limits': 'eight public fictional characters, four goals, relationships only to other registered NPC identities; never store private player teams or save fields',
        'native_battles': 'not available through this character registry alone; do not claim a battle occurred or a team is native until the battle adapter confirms it',
    }


def challenge(server, conn, fields):
    """Freeze one explicitly requested opponent for exactly this authenticated peer."""
    import time
    region=fields[0]=='CHARACTER_CHALLENGE_REGION'
    if (len(fields) != (5 if region else 4) or not conn.get('character_capable') or
            server.peers.get(conn.get('id')) is not conn or conn.get('closing')):
        raise ValueError('character challenge unavailable')
    try:
        seq, version = int(fields[1]), int(fields[3])
    except ValueError:
        raise ValueError('invalid character challenge') from None
    if str(seq) != fields[1] or str(version) != fields[3] or not conn['seq'] < seq <= 2**31-1:
        raise ValueError('stale character challenge')
    pending = conn.get('character_pending')
    if pending:
        raise ValueError('character challenge already pending')
    character = records(server.module_state).get(fields[2])
    obj = next((obj for obj in server.objects if obj['id'] == fields[2]), None)
    from .character_walks import walking
    if walking(server.module_state,fields[2]):raise ValueError('character is walking')
    from .region_characters import scoped
    if not scoped(server,conn,obj,fields[4] if region else None):raise ValueError('character region mismatch')
    state = conn.get('state')
    if (character is None or character['status'] != 'active' or character['version'] != version or
            obj is None or not state or not state[6] or
            time.monotonic() - conn.get('state_time', 0) > 5 or
            state[:2] != [obj['group'], obj['num']] or
            server.link_protocol.busy(conn['id']) or server.rally.current(conn) is not None):
        raise ValueError('character moved, changed or player unavailable')
    delta = {1:(0,1), 2:(0,-1), 3:(-1,0), 4:(1,0)}.get(state[4])
    if delta is None or (state[2]+delta[0], state[3]+delta[1]) != (obj['x'], obj['y']):
        raise ValueError('character challenge requires adjacent facing player')
    frozen = json.loads(json.dumps({'seq': seq, 'id': fields[2], 'version': version, 'team': character['team']}))
    conn['character_pending'] = frozen
    conn['seq'] = seq
    return 'CHARACTER_BATTLE_V1 ' + ' '.join(map(str, [seq, fields[2], version, len(frozen['team']),
        *[value for mon in frozen['team'] for value in (mon['species'], mon['level'])]])) + '\n'


def report_result(server, conn, fields):
    """Consume an exact pending challenge once; never grant rewards from reports."""
    pending = conn.get('character_pending')
    if (len(fields) != 5 or not conn.get('character_capable') or
            server.peers.get(conn.get('id')) is not conn or conn.get('closing') or not pending or
            fields[1:4] != [str(pending['seq']), pending['id'], str(pending['version'])] or
            not fields[4].isdigit() or not 0 <= int(fields[4]) <= 255):
        raise ValueError('unmatched character result')
    with server.db:
        server._event('character_battle_report', dict(player=conn['id'], character=pending['id'],
            version=pending['version'], outcome=int(fields[4]), evidence='authenticated_client_report_not_verified_outcome'))
    conn.pop('character_pending')
    return 'CHARACTER_RESULT_ACK ' + ' '.join(fields[1:4]) + '\n'


CURSOR_KEY = 'character_history_cursor'
HISTORY_BATCH = 16


def history_cursor(state):
    cursor = state.get(CURSOR_KEY, 0) if type(state) is dict else 0
    if type(cursor) is not int or not 0 <= cursor <= 2**63-1:
        raise ValueError('invalid character history cursor')
    return cursor


def history_feed(db, state):
    """Ordered public events after the durable cursor, never a lossy recent tail.

    Fixed-size summaries avoid replaying huge geometry payloads into the sandbox.
    Full original evidence remains accessible through the existing host history API.
    """
    after = history_cursor(state)
    rows = db.execute("SELECT seq,data FROM events WHERE kind='world_memory' AND seq>? ORDER BY seq LIMIT ?",
                      (after, HISTORY_BATCH + 1)).fetchall()
    events = []
    for seq, raw in rows[:HISTORY_BATCH]:
        original = json.loads(raw)
        event = dict(seq=seq, event=original['event'], evidence=original.get('evidence'),
                     recorded_at=original['recorded_at'], details='bounded_summary_full_event_in_world_history')
        for key in ('place_id', 'label', 'character_id', 'character_offer_id', 'goal_kind', 'guild_name', 'region_revision'):
            value = original.get(key)
            if type(value) is str:
                event[key] = value[:160]
        if original['event']=='landmark_discovery_shared':
            event.update(place_id=original['place_id'],revision=original['revision'],landmark=original['landmark'],
                         x=original['x'],y=original['y'],publication=original['publication'],basis=original['basis'])
        if original['event'] == 'area_named':
            event.update(before=original['before'][:160], after=original['after'][:160])
        elif original['event'] == 'character_changed':
            character = original['after']
            event.update(character_version=character['version'], character_status=character['status'])
            before=(original.get('before') or {}).get('relationships',{})
            after=character.get('relationships',{})
            event['relationship_changes']={target:after.get(target) for target in sorted(before.keys()|after.keys()) if before.get(target)!=after.get(target)}
        elif original['event'] == 'terrain_changed':
            event['changed_cell_count'] = len(original['tiles'])
        elif original['event'] == 'guild_goal_completed':
            if 'character_offer_revision' in original:
                event['character_offer_revision'] = original['character_offer_revision']
            event.update(credited=original['credited'], target=original['target'],
                         awarded_guild_xp=original['awarded_guild_xp'])
        events.append(event)
    return dict(after=after, through=events[-1]['seq'] if events else after,
                events=events, has_more=len(rows)>HISTORY_BATCH,
                cursor_state_key=CURSOR_KEY)


def validate_history_cursor(before, after, db):
    previous, current = history_cursor(before), history_cursor(after)
    feed = history_feed(db, before)
    if current < previous or current not in {previous, *[e['seq'] for e in feed['events']]}:
        raise ValueError('character history cursor must acknowledge this ordered public batch')


def validate_offer(offer):
    from .build_catalog import catalog_maps
    if type(offer) is not dict or set(offer)-{'region_revision'} != {'id','revision','kind','place_id','target'}:
        raise ValueError('invalid character expedition offer')
    if type(offer['id']) is not str or not re.fullmatch('[A-Za-z0-9_-]{1,24}',offer['id']):
        raise ValueError('invalid offer identity')
    if type(offer['revision']) is not int or not 1 <= offer['revision'] <= 2**31-1:
        raise ValueError('invalid offer revision')
    if offer['kind'] != 'expedition' or type(offer['target']) is not int or not 1 <= offer['target'] <= 50:
        raise ValueError('invalid offer objective')
    place=offer['place_id']
    if type(place) is str and place.startswith('area:'):
        if not re.fullmatch(r'area:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',place) or type(offer.get('region_revision')) is not str or not re.fullmatch('[0-9a-f]{64}',offer['region_revision']):
            raise ValueError('generated offer requires exact place and region revision')
        return offer
    if 'region_revision' in offer:raise ValueError('native offers must omit region_revision')
    if type(place) is not str or not place.startswith('native:'):
        raise ValueError('offer destination must be a native map')
    name=place[7:]
    if (not re.fullmatch('[A-Za-z0-9_]{1,63}',name) or name.startswith('GeneratedWorld_')
            or name not in {m['name'] for m in catalog_maps().values()}):
        raise ValueError('unsupported offer destination')
    return offer


class CharacterOfferError(ValueError):
    pass


def accept_offer(server, conn, fields):
    """Explicit native acceptance starts an existing guild objective, never a reward."""
    import time
    from .guilds import GuildError
    region=fields[0]=='CHARACTER_ACCEPT_REGION'
    if (len(fields)!=(7 if region else 6) or not conn.get('character_quest_capable') or
            server.peers.get(conn.get('id')) is not conn or conn.get('closing')):
        raise CharacterOfferError('UNAVAILABLE')
    try:
        seq,version,revision=int(fields[1]),int(fields[3]),int(fields[5])
    except ValueError:
        raise CharacterOfferError('STALE') from None
    if ([str(seq),str(version),str(revision)] != [fields[1],fields[3],fields[5]]
            or not conn['seq'] < seq <= 2**31-1):
        raise CharacterOfferError('STALE')
    character=records(server.module_state).get(fields[2])
    offer=character.get('offer') if character else None
    if (not character or character['status']!='active' or character['version']!=version
            or not offer or offer['id']!=fields[4] or offer['revision']!=revision):
        raise CharacterOfferError('STALE')
    obj=next((obj for obj in server.objects if obj['id']==fields[2]),None)
    from .character_walks import walking
    if walking(server.module_state,fields[2]):raise CharacterOfferError('UNAVAILABLE')
    from .region_characters import scoped
    if not scoped(server,conn,obj,fields[6] if region else None):raise CharacterOfferError('UNAVAILABLE')
    state=conn.get('state')
    if (not obj or not state or not state[6] or time.monotonic()-conn.get('state_time',0)>5
            or state[:2]!=[obj['group'],obj['num']] or conn.get('character_pending')
            or server.link_protocol.busy(conn['id']) or server.rally.current(conn) is not None):
        raise CharacterOfferError('UNAVAILABLE')
    dx,dy={1:(0,1),2:(0,-1),3:(-1,0),4:(1,0)}.get(state[4],(0,0))
    if (state[2]+dx,state[3]+dy)!=(obj['x'],obj['y']):
        raise CharacterOfferError('UNAVAILABLE')
    guild=server.guilds._member(conn['id'])
    if not guild or guild[2]!=conn['id']:
        raise CharacterOfferError('LEADER')
    receipt=(guild[0],fields[2],offer['id'],revision)
    exists=server.db.execute('SELECT 1 FROM guild_character_offer_receipts WHERE guild_id=? AND character_id=? AND offer_id=? AND offer_revision=?',receipt).fetchone()
    if not exists:
        privacy=server.db.execute('SELECT enabled FROM guild_world_history WHERE guild_id=?',(guild[0],)).fetchone()
        if not privacy or not privacy[0]:raise CharacterOfferError('PRIVATE')
        current=server.db.execute('SELECT complete FROM guild_expeditions WHERE guild_id=?',(guild[0],)).fetchone()
        if current and not current[0]:raise CharacterOfferError('ACTIVE')
        count=server.db.execute('SELECT COUNT(*) FROM guild_members WHERE guild_id=?',(guild[0],)).fetchone()[0]
        if offer['target']>count:raise CharacterOfferError('MEMBERS')
    place=None
    if offer['place_id'].startswith('area:'):
        from .generated_goals import resolve_place,destination_available
        if not conn.get('place_quest_capable') or not destination_available(server,conn,offer['place_id'],offer['region_revision']):
            raise CharacterOfferError('UNAVAILABLE')
        try:place=resolve_place(server,offer['place_id'],offer['region_revision'])
        except GuildError:raise CharacterOfferError('UNAVAILABLE') from None
    try:
        server.guilds.expedition(conn['id'],['start','here' if place else offer['place_id'][7:],str(offer['target'])],
                                character_offer=(fields[2],offer['id'],revision),place=place)
    except GuildError as exc:
        raise CharacterOfferError('REFUSED') from exc
    conn['seq']=seq
    if not exists:
        # Existing presence deduplication must notice the newly started goal.
        server.guild_chat.epoch+=1
    return 'CHARACTER_ACCEPTED '+ ' '.join([str(seq),fields[2],offer['id'],str(revision),'ALREADY' if exists else 'STARTED'])+'\n'
