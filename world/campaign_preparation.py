"""Save-specific campaign offers using existing native shop/tutor transactions."""
import json
from .actor_shops import ITEMS
from .actor_tutors import MOVES


def install(db):
    db.execute('''CREATE TABLE IF NOT EXISTS campaign_preparation_choices(
      revision INTEGER PRIMARY KEY AUTOINCREMENT, trainer TEXT, lineage TEXT,
      campaign TEXT, node TEXT, choice TEXT,
      UNIQUE(trainer,lineage,campaign,node,choice))''')


def validate(options,cast):
    import re
    if type(options) is not dict or len(options)>4:raise ValueError('Use up to four preparation choices')
    for key,p in options.items():
        if not re.fullmatch('[a-z][a-z0-9_]{0,15}',key) or type(p) is not dict or set(p)!={'actor','items','move'}:raise ValueError('Preparation uses actor/items/move')
        if type(p['actor']) is not str or p['actor'] not in cast:raise ValueError('Preparation requires an existing world character')
        items=p['items'];move=p['move']
        if type(items) is not list or len(items)>8 or any(type(i) is not int or i not in ITEMS for i in items) or len(set(items))!=len(items):raise ValueError('Use reviewed native retail items')
        if type(move) is not int or move not in (0,*MOVES):raise ValueError('Use a reviewed native tutor move')
        if not items and not move:raise ValueError('Preparation must offer a real service')


def choose(server,conn,current,key):
    from .battle_campaigns import document,save
    if not current or current[1]['status']!='ready':raise ValueError('Choose a battle route before preparing')
    campaign,data=current
    from .parallel_campaigns import effective
    options=effective(server,campaign,data).get('preparation',{})
    if key not in options:raise ValueError('Choose a listed preparation option')
    option=options[key]
    if option['items'] and not conn.get('character_shop_capable'):raise ValueError('This preparation requires a matched native shop client')
    if option['move'] and not conn.get('character_tutor_capable'):raise ValueError('This preparation requires a matched native tutor client')
    with server.db:
        server.db.execute('INSERT OR IGNORE INTO campaign_preparation_choices(trainer,lineage,campaign,node,choice) VALUES(?,?,?,?,?)',
                          (conn['id'],conn['campaign_run'],campaign,data['node'],key))
        data['preparation']=key
        save(server,conn,campaign,data)


def offer(server,conn,actor):
    from .battle_campaigns import active,document
    current=active(server,conn)
    if not current or current[1]['status']!='ready':return None
    campaign,data=current;key=data.get('preparation')
    from .parallel_campaigns import effective
    option=effective(server,campaign,data).get('preparation',{}).get(key)
    if not option or option['actor']!=actor:return None
    row=server.db.execute('SELECT revision FROM campaign_preparation_choices WHERE trainer=? AND lineage=? AND campaign=? AND node=? AND choice=?',
                          (conn['id'],conn['campaign_run'],campaign,data['node'],key)).fetchone()
    if not row or not 0<row[0]<=2147483647:return None
    return dict(option,revision=row[0])


def describe(server,data,node):
    options=node.get('preparation',{})
    if not options:return []
    lines=['Preparation: /guild campaign prepare OPTION']
    for key,p in options.items():
        service=('Shop '+','.join(ITEMS[i] for i in p['items'])) if p['items'] else ''
        if p['move']:service+=(' / ' if service else '')+'Tutor '+MOVES[p['move']]
        lines.append((key+': '+service)[:113])
    selected=options.get(data.get('preparation'))
    if selected:
        actor=selected['actor'];obj=next((o for o in server.objects if o['id']==actor),None)
        lines.append('Selected '+data['preparation']+'. Visit '+actor+'.')
        lines.append(('Camp map %s/%s tile %s,%s'%(obj['group'],obj['num'],obj['x'],obj['y'])) if obj else 'Camp actor currently away. Choice retained.')
        if obj and obj.get('region_revision'):lines.append('Region: '+obj['region_revision'])
    return lines
