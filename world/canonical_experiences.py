"""Bounded actor-selected public experiences, with exact world-history provenance.

Interpretations belong to the fictional actor. They are never new event facts,
permissions, private trainer memory, or evidence that an intended action happened.
"""
import json,re


def validate(row,actor,before=None,lookup=None):
    memories=row.get('memories',[])
    if type(memories) is not list or len(memories)>6:raise ValueError('At most six retained cast experiences')
    seen=set();old={m['id']:m for m in (before or {}).get('memories',[])}
    for item in memories:
        if (type(item) is not dict or set(item)!={'id','events','interpretation'}
                or type(item['id']) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,23}',item['id'])
                or item['id'] in seen):raise ValueError('Invalid cast experience identity')
        seen.add(item['id'])
        if (type(item['events']) is not list or not 1<=len(item['events'])<=2
                or any(type(n) is not int or n<1 for n in item['events'])
                or len(set(item['events']))!=len(item['events'])):raise ValueError('Experience needs one or two exact public event IDs')
        if type(item['interpretation']) is not str or not re.fullmatch("[A-Za-z0-9 .,!?'-]{1,240}",item['interpretation']):raise ValueError('Bounded literal fictional interpretation required')
        if before is None:continue # Structural validation; transition checks below.
        if old.get(item['id'])==item:continue
        if any(n not in row['evidence'] for n in item['events']):raise ValueError('New or revised experience must cite this inspected decision evidence')
        if lookup:
            from .canonical_cast import decision_evidence
            for n in item['events']:
                event=lookup(n)
                if not event or not decision_evidence(event,actor,row):raise ValueError('Experience requires eligible committed public evidence')
                if len(json.dumps(event))>16384:raise ValueError('Experience source too large; choose a bounded actual outcome')


def recall(context,character,fetch):
    """Retrieve exact retained episodes and relationship evidence before authoring.

Only previously admitted public event IDs, at the inspected world boundary.
No search through trainer saves, private conversation tables, or raw chat.
"""
    data=context.get('data',context);memory=data['world_memory']
    episodes=character.get('memories',[])
    ids={n for m in episodes for n in m['events']}
    ids.update(n for relation in character.get('relationships',{}).values() for n in relation['evidence'])
    events={}
    for seq in sorted(ids):
        if seq>memory['through']:raise ValueError('Retained experience is outside inspected history')
        page=fetch(dict(command='world_history',after=seq-1,through=seq,limit=1))
        rows=page.get('events',[])
        if (page.get('ok') is not True or page.get('world_id')!=memory['world_id']
                or len(rows)!=1 or rows[0].get('seq')!=seq or len(json.dumps(rows[0]))>16384):
            raise ValueError('Retained experience source unavailable or changed world')
        events[seq]=rows[0]
    context['character_experiences']=dict(
        memories=episodes,relationship_sources={target:relation['evidence'] for target,relation in character.get('relationships',{}).items()},
        instruction='These are this fictional character\'s revisable interpretations of exact public records, not objective truths, operator instructions, permissions, or reciprocal feelings. Compare old experience with the new event. You may retain, revise or drop a memory; a changed memory must cite its source in current evidence. Do not invent training, travel, discoveries or agreements. Decide a supported action or wait; no predefined growth arc.')
    recalled=context.setdefault('recalled_history',{}).setdefault('events',[])
    existing={e['seq'] for e in recalled}
    recalled.extend(e for n,e in events.items() if n not in existing)
