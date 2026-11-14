"""Author real opt-in field games; private match data is not author context."""
import json


def publish(server,actor,row,args):
    if set(args)!={'arena'} or type(args['arena']) is not str or len(args['arena'])>1500:
        raise ValueError('Supply a bounded flag arena JSON document')
    arena=json.loads(args['arena'])
    result=server.flags.publish(arena,commit=False)
    return dict(outcome='flag_arena_published',arena=result['id'],players=len(server.flags.starts(arena)),
        entry='/guild play start flag '+result['id'],
        basis='Playable authority field game registration; native positions are client-attested, not verified travel. No match, reward or result sharing claimed.')


def catalog(server):
    return [json.loads(raw) for raw, in server.db.execute('SELECT document FROM flag_arenas ORDER BY id LIMIT 64')]
