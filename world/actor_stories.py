"""Public authored choices feeding actual actor plans, without private story access."""
import json


def publish(server,actor,row,args):
    if set(args)!={'pack'} or type(args['pack']) is not str or len(args['pack'])>800:raise ValueError('Supply a public story JSON document within the normal tool-step budget')
    pack=json.loads(args['pack'])
    from .opportunities import validate
    validate(pack,server.opportunities.places)
    if any(q['scope']!='place' for q in pack['qualities'].values()) or any(s['once']!='world' or set(s)!={'place','text','requires','once','choices'} for s in pack['scenes'].values()):
        raise ValueError('Agent stories use only public place qualities and world-once player choices; no private, mystery or actor-owned scenes')
    prior=server.db.execute('SELECT actor FROM story_public_authors WHERE pack=?',(pack['id'],)).fetchone()
    exists=server.db.execute('SELECT 1 FROM story_packs WHERE id=?',(pack['id'],)).fetchone()
    if exists and (not prior or prior[0]!=actor):raise ValueError('Existing story belongs to another author or has private scope')
    result=server.opportunities.publish(pack,commit=False)
    server.db.execute('INSERT OR IGNORE INTO story_public_authors VALUES(?,?)',(pack['id'],actor))
    return dict(outcome='public_story_published',pack=pack['id'],digest=result['digest'],after_cursor=0,
                basis='Optional public fictional choices, not events that have occurred or native gameplay effects')


def wait(server,actor,row,args):
    from .actor_runtime import Pending
    if set(args)!={'pack','after_cursor'} or type(args['pack']) is not str or type(args['after_cursor']) is not int or args['after_cursor']<0:raise ValueError('Choose own public story and a nonnegative prior receipt cursor')
    owner=server.db.execute('SELECT actor FROM story_public_authors WHERE pack=?',(args['pack'],)).fetchone()
    if not owner or owner[0]!=actor:raise ValueError('Wait only for your own explicitly public story')
    return Pending(dict(args),lambda:None)


def poll(server,actor,row,pending):
    saved=server.db.execute('SELECT result FROM story_public_results WHERE pack=? AND cursor>? ORDER BY cursor LIMIT 1',(pending['pack'],pending['after_cursor'])).fetchone()
    return json.loads(saved[0]) if saved else None


def catalog(server):
    return [dict(pack=p,author=a,document=json.loads(d)) for p,a,d in server.db.execute('SELECT p.pack,p.actor,s.document FROM story_public_authors p JOIN story_packs s ON s.id=p.pack ORDER BY p.pack LIMIT 64')]


def relevant(event,actor):
    return event.get('event')=='public_story_choice_committed' and event.get('publication')=='explicit_public_story_choice' and event.get('author')==actor
