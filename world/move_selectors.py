"""Conservative static native move selectors, not inferred elemental world rules."""
import json
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=1)
def catalog():
    return json.loads(Path(__file__).with_name('move_traits.json').read_text())['traits']

def resolve(value):
    if type(value) is list:
        from .overworld_moves import move_names
        if not 1<=len(value)<=8 or any(type(m) is not int or str(m) not in move_names() for m in value) or len(set(value))!=len(value):raise ValueError('Exact move gate needs 1..8 distinct known IDs')
        return value[:]
    if type(value) is not dict or not value or set(value)-{'types','categories','exclude'} or not ({'types','categories'}&set(value)):raise ValueError('Move selector needs types and/or categories, optional exclude IDs')
    traits=catalog()
    for key,field in [('types','type'),('categories','category')]:
        if key not in value:continue
        values=value[key];known={r[field] for r in traits.values()}
        if type(values) is not list or not 1<=len(values)<=3 or any(type(v) is not str or v not in known for v in values) or len(set(values))!=len(values):raise ValueError('Selector needs 1..3 distinct known '+key)
    exclude=value.get('exclude',[])
    if type(exclude) is not list or len(exclude)>8 or any(type(m) is not int or str(m) not in traits for m in exclude) or len(set(exclude))!=len(exclude):raise ValueError('Exclude up to eight catalogued move IDs')
    result=[int(m) for m,r in traits.items() if ('types' not in value or r['type'] in value['types']) and ('categories' not in value or r['category'] in value['categories']) and int(m) not in exclude]
    if not result:raise ValueError('Move selector matches no supported native moves')
    return sorted(result)

def describe(value):
    if type(value) is list:return None
    return ' / '.join(value.get('types',[]))+' '+ ' / '.join(value.get('categories',[]))+' learned moves ('+str(len(resolve(value)))+' supported)'

def inspect_rules(server,actor,row,args):
    from .overworld_moves import move_names
    if set(args)!={'selector','after'} or type(args['selector']) is not str or len(args['selector'])>300 or type(args['after']) is not int or args['after']<0:raise ValueError('Supply selector JSON and nonnegative last move ID')
    selected=resolve(json.loads(args['selector']));page=[m for m in sorted(selected) if m>args['after']][:24]
    return dict(outcome='static_native_move_rule_catalog',total=len(selected),moves=[dict(id=m,name=move_names()[str(m)],**catalog().get(str(m),{})) for m in page],next_after=page[-1] if page and any(m>page[-1] for m in selected) else 0,limits='Static literal metadata, not owned or learned moves. Config-dependent traits excluded; use current native inspection before NPC action.')
