"""Typed Expansion encounter populations for ordinary generated XL geography."""
from .species_cohort import species_id, contains_species_id

MAGIC=b'EWGMAP17'
WEIGHTS=(20,20,10,10,10,10,5,5,4,4,1,1)


def validate_table(table):
    if type(table) is not bytes or len(table)!=37 or not 1<=table[0]<=100:
        raise ValueError('invalid XL encounter table')
    for i in range(12):
        offset=1+3*i
        if not contains_species_id(int.from_bytes(table[offset:offset+2],'little'),'expansion-native') or not 1<=table[offset+2]<=100:
            raise ValueError('invalid enabled Expansion species or encounter level')
    return table


def encode(geometry, encounters):
    from .shared_cave import SharedCave
    cave=SharedCave(geometry)
    if cave.version!=16 or type(encounters) is not dict or set(encounters)!={'rate','wildlife'}:
        raise ValueError('encounters require plain XL geometry, rate and wildlife')
    rate=encounters['rate'];slots=encounters['wildlife']
    if type(rate) is not int or not 1<=rate<=100 or type(slots) is not list or len(slots)!=12:
        raise ValueError('use rate 1..100 and exactly twelve encounter slots')
    table=bytearray([rate])
    for slot in slots:
        if type(slot) is not dict or set(slot)!={'species','level'} or type(slot['level']) is not int or not 1<=slot['level']<=100:
            raise ValueError('invalid encounter slot')
        table.extend(species_id(slot['species'],'expansion-native').to_bytes(2,'little'));table.append(slot['level'])
    validate_table(bytes(table))
    return MAGIC+bytes(table)+geometry[8:]


def population(encounters):
    """Actual native slot weights, not an invented per-step encounter probability."""
    result={}
    for weight,slot in zip(WEIGHTS,encounters['wildlife']):
        key=(slot['species'],slot['level']);result[key]=result.get(key,0)+weight
    return [dict(species=name,level=level,slot_percent=weight) for (name,level),weight in sorted(result.items())]


def context(cave):
    """Derived authored population, never observed catches or private player data."""
    if cave.version!=17:return None
    from .species_cohort import catalogue
    names={value:name for name,value in catalogue('expansion-native').items()}
    wildlife=[]
    for i in range(12):
        offset=1+3*i
        wildlife.append(dict(species=names[int.from_bytes(cave.wildlife[offset:offset+2],'little')],
                             level=cave.wildlife[offset+2]))
    return dict(revision=cave.identity,cohort=cave.cohort,rate=cave.wildlife[0],
                population=population(dict(wildlife=wildlife)),
                basis='authored_table_bound_to_archived_template_not_observed_wildlife_or_catches')
