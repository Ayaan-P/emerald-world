"""Read committed public place history through the existing private chat reply."""
import json
import sqlite3
import time

PAGE_SIZE = 3


def _text(value, limit=64):
    # World labels and authored prose are data, never native control sequences.
    value=' '.join(''.join(c if 32 <= ord(c) < 127 else ' ' for c in str(value)).split())
    return value if len(value)<=limit else value[:limit-3]+'...'


def _describe(event):
    """Allowlist public facts; never return complete event payloads or module state."""
    kind=event.get('event')
    if kind=='area_activated':
        return ['Place revision activated: '+_text(event.get('label') or 'Unnamed place'),
                'Earlier revisions remain history, not the current terrain.']
    if kind=='area_named':
        return ['Place renamed to '+_text(event.get('after','Unnamed place'))]
    if kind=='character_changed':
        character=event.get('after',{})
        return [_text(character.get('name','Resident'),32)+' has an authored story change.',
                'Authored motive: '+_text(character.get('reason','No motive recorded'),80)]
    if kind=='guild_goal_completed':
        return [_text(event.get('guild_name','Guild'),40)+' completed a public '+_text(event.get('goal_kind','goal'),16)+'.',
                'Authority award: '+_text(event.get('awarded_guild_xp',0),10)+' guild XP; travel was client-reported.']
    if kind=='landmark_discovery_shared':
        return ['A player explicitly shared a visit to '+_text(event.get('landmark','a landmark'),40)+'.',
                'That arrival was client-reported; private visits are not included.']
    if kind=='trail_opened':
        return ['Trail opened: '+_text(event.get('start',''),32)+' to '+_text(event.get('end',''),32)+'.',
                'Terrain distance: '+_text(event.get('old_steps','?'),8)+' to '+_text(event.get('new_steps','?'),8)+' steps. Player travel is not inferred.']
    if kind=='terrain_changed':
        return ['Shared terrain changed in this place.']
    if kind=='mechanic_changed':
        return ['Shared content changed here. Dialogue is authored, not proof of completed deeds.']
    if kind=='region_opened':
        return ['This place was opened as an immutable destination.']
    return ['A public world change was recorded here.']


def read(server, conn, older=False):
    """Caller holds authority lock. Cursor is connection-local and never client supplied."""
    revision=server.landmark_survey.scope(conn)
    if (revision is None or server.peers.get(conn.get('id')) is not conn or conn.get('closing')
            or not 0<=time.monotonic()-conn.get('state_time',0)<=5):
        return ['Enter an acknowledged generated place to read its public history.']
    try:
        row=server.db.execute('SELECT place_id FROM world_places WHERE revision=?',(revision,)).fetchone()
        if row is None:return ['This destination has no archived place history.']
        place=row[0];world=server.memory.world_id
        cursor=conn.get('place_history_cursor')
        if older:
            if not cursor or (cursor['world'],cursor['place'],cursor['revision'])!=(world,place,revision):
                return ['Use /explore history first in this destination.']
            if cursor['before'] is None:return ['No older recorded changes. Use /explore history to refresh.']
            through,before=cursor['through'],cursor['before']
        else:
            through=server.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            before=through+1
        rows=server.db.execute("""SELECT e.seq,e.data FROM events e
            JOIN world_memory_place_events p ON p.seq=e.seq
            WHERE p.place_id=? AND e.kind='world_memory' AND e.seq<=? AND e.seq<?
            ORDER BY e.seq DESC LIMIT ?""",(place,through,before,PAGE_SIZE+1)).fetchall()
        lines=['Public place history through record '+str(through)+'. Includes earlier revisions.']
        for seq,data in rows[:PAGE_SIZE]:
            event=json.loads(data)
            lines.extend(('Record '+str(seq)+': '+line)[:120] for line in _describe(event))
        if not rows:lines.append('No committed public changes are recorded for this place.')
        more=len(rows)>PAGE_SIZE
        lines.append('Use /explore history older for earlier records.' if more else
                     'End of recorded history. Use /explore history to refresh.')
        conn['place_history_cursor']=dict(world=world,place=place,revision=revision,through=through,
                                         before=rows[PAGE_SIZE-1][0] if more else None)
        return lines
    except (sqlite3.Error,ValueError,TypeError,KeyError):
        return ['Place history could not be read. Try /explore history again.']
