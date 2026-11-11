"""Player-controlled private checkpoints of public places and current destinations."""
import hashlib,json,secrets,time,textwrap
from .guilds import GuildError


def setup(db):
    db.execute('CREATE TABLE IF NOT EXISTS player_place_checkpoints(trainer TEXT,place TEXT,snapshot TEXT,PRIMARY KEY(trainer,place))')


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()


def places(server):
    from .build_catalog import catalog_maps
    result={'native:'+v['name']:dict(label=v['name'],map=list(k),revision=None) for k,v in catalog_maps().items()}
    if server.archive_generated_areas:
        for place,revision,label in server.db.execute('SELECT r.place_id,r.revision,a.label FROM world_region_revisions r JOIN generated_area_archive a ON a.identity=r.revision'):
            result[place]=dict(label=label,map=list(server.cave_map),revision=revision)
    return result


def snapshot(server,place):
    from .characters import records
    from .world_memory import native_place
    location=places(server).get(place)
    if not location:raise GuildError('Place is no longer available. No checkpoint was changed.')
    objects=[o for o in server.objects if (o.get('region_revision')==location['revision'] if location['revision'] else not o.get('region_revision') and native_place(o['group'],o['num'])==place)]
    if len(objects)>64:raise GuildError('Place exceeds the complete checkpoint size; nothing was recorded.')
    cast=records(server.module_state);entities={}
    for o in objects:
        item={k:o[k] for k in ('x','y','gfx','text')};item['name']=cast.get(o['id'],{}).get('name',o['id'])
        shop=server.db.execute('SELECT items FROM actor_shops WHERE actor=?',(o['id'],)).fetchone()
        item['shop']=json.loads(shop[0]) if shop else []
        item['kind']='character' if o['id'] in cast else 'object';entities[o['id']]=item
    campaigns={}
    networks=server.module_state.get('world_object_networks',{})
    for key,raw in server.db.execute('SELECT id,document FROM battle_campaigns'):
        doc=json.loads(raw)
        for node in doc['nodes'].values():
            goal=node.get('mechanism',node.get('expedition',{}))
            if node.get('opponent') in entities or any(i in entities for i in networks.get(goal.get('network'),{}).get('objects',[])):
                campaigns[key]=doc['title'];break
    if len(campaigns)>64:raise GuildError('Place exceeds the complete activity checkpoint size.')
    return dict(location=location,entities=entities,campaigns=campaigns)


def changes(before,now):
    result=[]
    if before['location']!=now['location']:result.append('The place label or content revision changed.')
    old=before['entities'];new=now['entities']
    for key in sorted(old.keys()|new.keys()):
        if key not in old:result.append(new[key]['name']+' is now present.')
        elif key not in new:result.append(old[key]['name']+' is no longer present here.')
        else:
            a,b=old[key],new[key]
            if a['shop']!=b['shop']:result.append(b['name']+' changed the available shop catalog.')
            if (a['x'],a['y'])!=(b['x'],b['y']):result.append(b['name']+' moved to tile %s,%s.'%(b['x'],b['y']))
            if (a['gfx'],a['text'],a['name'])!=(b['gfx'],b['text'],b['name']):result.append(b['name']+' changed appearance or greeting.')
    for key in sorted(before['campaigns'].keys()|now['campaigns'].keys()):
        if before['campaigns'].get(key)!=now['campaigns'].get(key):result.append(('Activity now listed: '+now['campaigns'][key]) if key in now['campaigns'] else 'Activity no longer listed: '+before['campaigns'][key])
    return result


def command(server,conn,words):
    if server.peers.get(conn.get('id')) is not conn or conn.get('closing'):raise GuildError('Authenticated player required.')
    setup(server.db)
    try:lines=run(server,conn,words)
    except (ValueError,KeyError,TypeError) as exc:raise GuildError(str(exc) or 'Refresh the place guide.') from None
    return [part for line in lines for part in textwrap.wrap(''.join(c if 32<=ord(c)<127 else '?' for c in line),110)]


def run(server,conn,words):
    trainer=conn['id'];known=places(server)
    if not words:return ['Private place checkpoints. No automatic tracking or public visitor history.',
        '/guild return places PAGE; watch PLACE; list; read PLACE; forget PLACE.',
        'Read compares current public content with your explicit checkpoint, not every event in between.']
    if words[0]=='places' and len(words)==2 and words[1].isdigit():
        page=int(words[1]);rows=sorted(known.items(),key=lambda r:(r[1]['label'],r[0]));pages=max(1,(len(rows)+3)//4)
        if not 1<=page<=pages:raise GuildError('Choose page 1..'+str(pages))
        return [f'Public places {page}/{pages}']+[v['label']+' | '+k for k,v in rows[(page-1)*4:page*4]]
    if words==['list']:
        rows=server.db.execute('SELECT place,snapshot FROM player_place_checkpoints WHERE trainer=? ORDER BY place',(trainer,)).fetchall()
        return ['Your private checkpoints:']+[known.get(k,{}).get('label','Unavailable place')+' | '+k for k,_ in rows] if rows else ['No private checkpoints. Use /guild return watch PLACE.']
    if len(words)==2 and words[0] in ('watch','forget','read'):
        action,place=words;old=server.db.execute('SELECT snapshot FROM player_place_checkpoints WHERE trainer=? AND place=?',(trainer,place)).fetchone()
        if action=='forget':
            with server.db:server.db.execute('DELETE FROM player_place_checkpoints WHERE trainer=? AND place=?',(trainer,place))
            conn.pop('place_guide',None);return ['Removed your checkpoint. World history and other players are unchanged.']
        now=snapshot(server,place)
        if action=='watch':
            if old:raise GuildError('Already bookmarked. Read it before explicitly replacing your checkpoint.')
            if server.db.execute('SELECT count(*) FROM player_place_checkpoints WHERE trainer=?',(trainer,)).fetchone()[0]>=8:raise GuildError('Forget a checkpoint first; eight places per player.')
            with server.db:server.db.execute('INSERT INTO player_place_checkpoints VALUES(?,?,?)',(trainer,place,encode(now)))
            return ['Saved a private checkpoint for '+now['location']['label']+'. No visit or exploration is asserted.']
        if not old:raise GuildError('Watch this place first to compare future changes.')
        report=changes(json.loads(old[0]),now);rows=['Current comparison for '+now['location']['label'],*(report or ['No tracked content differences. Intermediate changes may have happened.']), 'Currently present:']
        from .actor_shops import ITEMS
        for _,v in sorted(now['entities'].items()):
            rows.append(v['name']+' at '+str(v['x'])+','+str(v['y']))
            if v['shop']:rows.append('Shop currently offers '+', '.join(ITEMS.get(i,'item '+str(i)) for i in v['shop']))
        rows.extend('Optional activity '+title+': /guild campaign start '+key for key,title in sorted(now['campaigns'].items()))
        token=secrets.token_hex(6);conn['place_guide']=dict(token=token,place=place,before=old[0],snapshot=now,rows=rows,page=0,until=time.monotonic()+120)
        return page_rows(conn['place_guide'])
    if len(words)==2 and words[0] in ('next','save','go'):
        pending=conn.get('place_guide')
        if not pending or pending['token']!=words[1] or time.monotonic()>pending['until']:raise GuildError('Place guide expired. Read it again.')
        if words[0]=='next':
            if (pending['page']+1)*5>=len(pending['rows']):raise GuildError('Last page reached.')
            pending['page']+=1;return page_rows(pending)
        current=snapshot(server,pending['place'])
        if current!=pending['snapshot']:raise GuildError('The place changed again. Read it again before acting.')
        old=server.db.execute('SELECT snapshot FROM player_place_checkpoints WHERE trainer=? AND place=?',(trainer,pending['place'])).fetchone()
        if old!=(pending['before'],):raise GuildError('Your checkpoint changed. Read again.')
        if words[0]=='save':
            if (pending['page']+1)*5<len(pending['rows']):raise GuildError('Review all pages before replacing your checkpoint.')
            with server.db:server.db.execute('UPDATE player_place_checkpoints SET snapshot=? WHERE trainer=? AND place=?',(encode(current),trainer,pending['place']))
            conn.pop('place_guide',None);return ['Checkpoint updated to the reviewed public state. No visit or completion recorded.']
        if not current['location']['revision']:raise GuildError('Travel to this ordinary map normally; this guide does not warp players.')
        server._select_region(conn,pending['place']);conn.pop('place_guide',None)
        return ['Destination selected. Enter using the ordinary generated-area entrance. Your checkpoint is unchanged.']
    raise GuildError('Use /guild return for commands.')


def page_rows(p):
    start=p['page']*5;out=p['rows'][start:start+5];token=p['token']
    if start+5<len(p['rows']):out.append('/guild return next '+token)
    else:out.append('Replace reviewed checkpoint: /guild return save '+token)
    if p['snapshot']['location']['revision']:out.append('Select this destination: /guild return go '+token)
    return out
