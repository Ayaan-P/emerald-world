"""Longer autonomous travel using existing exact-map native walking segments."""
import re


def validate(server,before,after,objects,*,restoring=False):
    from .region_characters import validate_region_objects
    controls=after.get('world_character_controls',{})
    old_controls=before.get('world_character_controls',{})
    for identity,control in controls.items():
        route=control.get('journey')
        if route is None:continue
        walk=control.get('walk');obj=control.get('object')
        if (type(route) is not dict or set(route)-{'meeting','survey'}!={'id','path','segment'}
                or type(route['id']) is not str or not re.fullmatch('[0-9a-f]{24}',route['id'])
                or type(route['path']) is not list or not 2<=len(route['path'])<=65
                or type(route['segment']) is not int or route['segment']<0 or route['segment']%5
                or route['segment']>=len(route['path'])-1 or not walk or not obj):
            raise ValueError('invalid autonomous journey')
        path=route['path'];segment=route['segment']
        if (any(type(p) is not list or len(p)!=2 or any(type(v) is not int for v in p) for p in path)
                or len({tuple(p) for p in path})!=len(path)
                or any(abs(a[0]-b[0])+abs(a[1]-b[1])!=1 for a,b in zip(path,path[1:]))
                or walk['path']!=path[segment:segment+6] or walk['id']!=route['id'][:20]+('%04x'%segment)):
            raise ValueError('journey path or current native segment differs')
        from .character_reconnaissance import validate as validate_survey
        validate_survey(route)
        from .character_encounters import validate_control
        validate_control(route,identity)
        if route.get('meeting') and obj.get('text')!=route['meeting']['text']:raise ValueError('journey visitor dialogue changed before delivery')
        old=old_controls.get(identity,{})
        previous=old.get('journey')
        same=previous and previous['id']==route['id']
        if not restoring:
            if same:
                if previous['path']!=path or previous.get('meeting')!=route.get('meeting') or previous.get('survey')!=route.get('survey') or segment not in (previous['segment'],previous['segment']+5):
                    raise ValueError('journey cannot skip or rewrite segments')
                if segment!=previous['segment'] and (old['walk']['index']!=len(old['walk']['path'])-1 or walk['index']!=0 or walk['last_tick']==old['walk']['last_tick'] or walk['last_tick']!=server.tick):
                    raise ValueError('journey must finish each native segment')
            elif segment!=0 or walk['index']!=0:
                raise ValueError('journey must begin at its current position')
        if not same or restoring:
            for x,y in path:
                projected=[dict(o,x=x,y=y) if o['id']==identity else o for o in objects]
                if len({(o.get('region_revision'),o['group'],o['num'],o['x'],o['y']) for o in projected})!=len(projected):
                    raise ValueError('journey crosses another world object')
                validate_region_objects(server,projected,after)
    for identity,old in old_controls.items():
        if old.get('journey') and not controls.get(identity,{}).get('journey'):
            new=controls.get(identity,{}).get('character')
            if new and new['version']==old['character']['version']:
                raise ValueError('cancelling a journey requires a versioned action')


def completed(control):
    j=control.get('journey');w=control.get('walk')
    return bool(j and w and j['segment']+len(w['path'])==len(j['path']) and w['index']==len(w['path'])-1)


def commit(server,before,after,objects):
    for identity,control in after.get('world_character_controls',{}).items():
        if not completed(control):continue
        old=before.get('world_character_controls',{}).get(identity,{})
        j=control['journey']
        if not old.get('journey') or old['journey']['id']!=j['id'] or completed(old):continue
        if server.db.execute('SELECT 1 FROM character_journey_receipts WHERE actor=? AND journey=?',(identity,j['id'])).fetchone():continue
        obj=control['object'];revision=obj['region_revision'];place=server.memory.place(revision)
        from .world_memory import native_place
        seq=server.memory.append('character_journey_arrived',dict(
            character_id=identity,character_name=control['character']['name'],journey=j['id'],
            revision=revision,place_id=place,places=[p for p in (place,native_place(obj['group'],obj['num'])) if p],
            start=j['path'][0],destination=j['path'][-1],steps=len(j['path'])-1,
            publication='public_world_character_movement',basis='committed_authority_cardinal_steps',
            limits='Authority arrival, not proof every client rendered the journey. No player travel or canonical NPC relocation.'))
        server.db.execute('INSERT INTO character_journey_receipts VALUES(?,?,?)',(identity,j['id'],seq));server.revision=seq
        if j.get('survey'):
            from .character_reconnaissance import commit as commit_survey
            commit_survey(server,identity,control,seq)
        if j.get('meeting'):
            from .character_encounters import commit as commit_encounter
            commit_encounter(server,identity,control,after,objects,seq)


def relevant(event,revisions):
    return (event.get('event')=='character_journey_arrived' and event.get('publication')=='public_world_character_movement'
            and event.get('basis')=='committed_authority_cardinal_steps' and event.get('revision') in revisions)
