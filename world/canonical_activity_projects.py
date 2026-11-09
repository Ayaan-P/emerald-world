"""Real shared project outcomes control optional native cast activities.

No new story flags, rewards, fabricated battles, or client save changes.
"""
import json


def validate(rules, row):
    if rules is None:return
    if type(rules) is not dict or not rules or set(rules)-{'companion','scene'}:
        raise ValueError('Activity projects support existing companion or scene activities only')
    project=row.get('initiative')
    if not project:raise ValueError('Activity projects require the actor own immutable initiative')
    for activity,rule in rules.items():
        if not row.get(activity):raise ValueError('Activity project needs a supported authored activity')
        if type(rule) is not dict or set(rule)!={'scene','requires'}:
            raise ValueError('Activity project needs a committed actor scene and shared requirements')
        scene=project['scenes'].get(rule['scene']) if type(rule['scene']) is str else None
        if not scene or 'actors' not in scene:raise ValueError('Activity project requires an actual actor turn')
        req=rule['requires']
        if type(req) is not dict or not 1<=len(req)<=8:raise ValueError('Activity project needs bounded shared requirements')
        for key,bounds in req.items():
            q=project['qualities'].get(key)
            if (not q or q['scope']!='place' or type(bounds) is not list or len(bounds)!=2
                    or any(type(n) is not int for n in bounds) or not 0<=bounds[0]<=bounds[1]<=q['max']):
                raise ValueError('Activity project requires public bounded qualities')


def available(server,identity,row,activity):
    if not row or not row.get(activity):return False
    rule=row.get('activity_projects',{}).get(activity)
    if not rule:return True # Existing authored invitations preserve their behavior.
    project=row['initiative'];scene=project['scenes'][rule['scene']]
    owner=server.db.execute('SELECT actor FROM canonical_initiatives WHERE pack=?',(project['id'],)).fetchone()
    if owner!=(identity,):return False
    record=server.db.execute('SELECT state,played FROM story_places WHERE pack=? AND place=?',(project['id'],scene['place'])).fetchone()
    if not record:return False
    state,played=map(json.loads,record)
    return rule['scene'] in played and all(low<=state.get(key,-1)<=high for key,(low,high) in rule['requires'].items())


def visible(server,identity,row):
    if not row:return row
    result=dict(row)
    for activity in row.get('activity_projects',{}):
        if not available(server,identity,row,activity):result.pop(activity,None)
    return result
