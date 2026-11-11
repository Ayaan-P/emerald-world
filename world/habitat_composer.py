"""Compose real encounter tables from bounded, sourced native species traits.

Type/stat filtering is authoring, not a claim of simulated ecological history.
"""
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from .species_cohort import catalogue

TYPES={'normal','fighting','flying','poison','ground','rock','bug','ghost','steel','fire','water','grass','electric','psychic','ice','dragon','dark','fairy'}

@lru_cache(maxsize=1)
def traits():
 data=json.loads(Path(__file__).with_name('encounter_traits.json').read_text())
 manifest=json.loads((Path(__file__).resolve().parents[1]/'engines/living-cast-candidate.json').read_text())
 if data['engine_commit']!=manifest['native_revision']:raise ValueError('Regenerate encounter traits for the selected native candidate')
 enabled=catalogue('expansion-native')
 return tuple(r for r in data['species'] if enabled.get(r['name'])==r['species'])


def parse(value):
 if type(value) is not str or len(value)>500:raise ValueError('Use bounded criteria JSON')
 try:q=json.loads(value)
 except ValueError:raise ValueError('Invalid criteria JSON')
 if type(q) is not dict or set(q)!={'types','generations','bst','levels','seed'}:raise ValueError('Criteria require types, generations, bst, levels, seed')
 if (type(q['types']) is not list or not 1<=len(q['types'])<=4 or
     any(type(t) is not str or t not in TYPES for t in q['types']) or len(set(q['types']))!=len(q['types'])):raise ValueError('Choose 1..4 distinct native types')
 if (type(q['generations']) is not list or not 1<=len(q['generations'])<=9 or
     any(type(g) is not int or not 1<=g<=9 for g in q['generations']) or len(set(q['generations']))!=len(q['generations'])):raise ValueError('Choose distinct generations 1..9')
 for key,lo,hi in [('bst',150,720),('levels',1,100)]:
  if type(q[key]) is not list or len(q[key])!=2 or any(type(x) is not int for x in q[key]) or not lo<=q[key][0]<=q[key][1]<=hi:raise ValueError('Invalid '+key+' range')
 if type(q['seed']) is not int or not 0<=q['seed']<=2**32-1:raise ValueError('Use an unsigned seed')
 return q


def matches(q):
 return [r for r in traits() if not r['special'] and r['generation'] in q['generations']
         and set(r['types'])&set(q['types']) and q['bst'][0]<=r['bst']<=q['bst'][1] and r['catch_rate']>0]


def compose(value):
 q=parse(value);pool=matches(q)
 if len(pool)<12:raise ValueError('Fewer than twelve supported matching species; broaden criteria')
 selected=sorted(pool,key=lambda r:hashlib.sha256(f"{q['seed']}:{r['name']}".encode()).digest())[:12]
 selected.sort(key=lambda r:(r['bst'],r['species']))
 lo,hi=q['levels'];slots=[]
 for i,r in enumerate(selected):slots.append([r['name'],lo+(hi-lo)*i//11])
 return dict(criteria=q,matching_species=len(pool),slots=slots,traits=selected)


def inspect_species(server,actor,row,args):
 if set(args)!={'criteria','page'} or type(args['page']) is not int or args['page']<0:raise ValueError('Supply criteria and nonnegative page')
 q=parse(args['criteria']);pool=sorted(matches(q),key=lambda r:r['species']);start=args['page']*12
 if start and start>=len(pool):raise ValueError('Species page unavailable')
 return dict(species=pool[start:start+12],total=len(pool),next_page=args['page']+1 if start+12<len(pool) else None,
             limits='Native traits for supported base species only. Type similarity is not habitat evidence; no encounter observed.')


def create(server,actor,row,args):
 from .actor_places import create_habitat
 if set(args)!={'label','blueprint','profile','rate','criteria'}:raise ValueError('Supply label, blueprint, profile, rate, criteria')
 population=compose(args['criteria'])
 # The existing compiler/admission owns actual profile, rate, species and map validation.
 return create_habitat(server,actor,row,dict(label=args['label'],blueprint=args['blueprint'],
        population=json.dumps(dict(profile=args['profile'],rate=args['rate'],slots=population['slots']),separators=(',',':'))))
