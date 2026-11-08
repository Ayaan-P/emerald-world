"""Bounded authoritative cardinal walking for exact-revision generated characters."""
import re


def walk_for(state, identity):
    return state.get('world_character_controls',{}).get(identity,{}).get('walk') if type(state) is dict else None


def walking(state, identity):
    walk=walk_for(state,identity)
    return bool(walk and walk['index']<len(walk['path'])-1)


def validate_walks(server, before, after, objects, *, restoring=False):
    from .region_characters import validate_region_objects
    from .characters import records
    cast=records(after);visible={o['id']:o for o in objects}
    old_controls=before.get('world_character_controls',{}) if type(before) is dict else {}
    controls=after.get('world_character_controls',{}) if type(after) is dict else {}
    for identity,control in controls.items():
        walk=control.get('walk')
        if walk is None:continue
        if (identity not in cast or cast[identity]['status']!='active' or
                type(walk) is not dict or set(walk)!={'id','path','index','last_tick'} or
                type(walk['id']) is not str or not re.fullmatch('[0-9a-f]{24}',walk['id']) or
                type(walk['last_tick']) is not int or walk['last_tick']<0):
            raise ValueError('invalid character walking control')
        path=walk['path'];index=walk['index'];obj=visible.get(identity)
        if (type(path) is not list or not 2<=len(path)<=6 or
                any(type(p) is not list or len(p)!=2 or any(type(v) is not int for v in p) for p in path) or
                len({tuple(p) for p in path})!=len(path) or
                any(abs(a[0]-b[0])+abs(a[1]-b[1])!=1 for a,b in zip(path,path[1:])) or
                type(index) is not int or not 0<=index<len(path) or obj is None or
                'region_revision' not in obj or [obj['x'],obj['y']]!=path[index] or control.get('object')!=obj or
                control.get('character')!=cast[identity]):
            raise ValueError('walking requires a scoped cardinal path and matching authority position')
        old=old_controls.get(identity,{}).get('walk')
        same=old and old.get('id')==walk['id']
        if same and not restoring:
            prior=old_controls[identity]
            if (prior['character']['version']!=cast[identity]['version'] or
                    any(prior['object'].get(k)!=obj.get(k) for k in ('group','num','region_revision'))):
                raise ValueError('walking scope and version must remain stable')
            if index!=old['index'] and (walk['last_tick']==old['last_tick'] or walk['last_tick']!=server.tick):
                raise ValueError('walking advances at most once per authority tick')
            if old['path']!=path or index not in (old['index'],old['index']+1):
                raise ValueError('character walking cannot skip or rewrite steps')
        if not same and not restoring:
            original=next((o for o in server.objects if o['id']==identity),None)
            if (index!=0 or original is None or [original['x'],original['y']]!=path[0] or
                    any(original.get(k)!=obj.get(k) for k in ('group','num','region_revision'))):
                raise ValueError('character walk must begin at its current scoped location')
            previous=records(before).get(identity)
            if previous is None or cast[identity]['version']!=previous['version']+1:
                raise ValueError('new character walk requires an explicit versioned action')
        if not same or restoring:
            for x,y in path:
                projected=[dict(o,x=x,y=y) if o['id']==identity else o for o in objects]
                if len({(o.get('region_revision'),o['group'],o['num'],o['x'],o['y']) for o in projected})!=len(projected):
                    raise ValueError('character path collides with another object')
                validate_region_objects(server,projected,after)
    for identity,old in old_controls.items():
        if old.get('walk') and not controls.get(identity,{}).get('walk'):
            previous=records(before).get(identity);current=cast.get(identity)
            if previous and current and current['version']==previous['version']:
                raise ValueError('stopping a character walk requires a versioned action')
