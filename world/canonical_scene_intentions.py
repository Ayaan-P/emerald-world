"""Actor plans invite at real encounters; only completed native barriers are evidence."""
def task(server,actor,row):
    for item in row.get('intentions',[]):
        if item['kind']=='scene' and item['target']==row.get('scene'):
            if not server.db.execute('SELECT 1 FROM canonical_intent_receipts WHERE actor=? AND intention=?',(actor,item['id'])).fetchone():return item
    return None


def invite(scenes):
    if scenes.debt or scenes.offer:return
    from .canonical_cast import records
    from .canonical_activity_projects import visible
    for peer in list(scenes.s.peers.values()):
        reached=peer.get('canonical_location') or {};actor=reached.get('actor')
        row=visible(scenes.s,actor,records(scenes.s.module_state).get(actor,{}))
        item=task(scenes.s,actor,row)
        if not item or not scenes.fresh(peer):continue
        key=(actor,item['id'])
        # One optional invitation per intention and connection, never a repeated
        # popup after declining. A new session may encounter the same plan.
        if key in peer.get('cast_scene_offered',set()):continue
        try:scenes.handle(peer,['ASK',peer.get('core_active_run',''),actor.removeprefix('canon_')])
        except ValueError:continue
        if scenes.offer:
            scenes.offer['intention']=item['id']
            for p in scenes.offer['cohort']:p.setdefault('cast_scene_offered',set()).add(key)
        return


def record(scenes):
    live=scenes.live;server=scenes.s
    if not live or not live.get('completed') or not live.get('intention'):return
    actor=live['actor'];intention=live['intention']
    if server.db.execute('SELECT 1 FROM canonical_intent_receipts WHERE actor=? AND intention=?',(actor,intention)).fetchone():return
    from .canonical_scene_paths import binding
    path=binding(actor,live['path'])
    with server.db:
        seq=server.memory.append('canonical_scene_observed',dict(character_id=actor,
            character_version=live['version'],intention=intention,path=live['path'],
            places=['native:'+path['map']],steps=len(path['points'])-1,
            publication='public_cast_activity',outcome='native_path_observed_and_restored',
            source='cohort_native_attestation',
            limits='All participating native controllers reported each reviewed step and original home restoration. Not proof of research, travel, training, rewards, player attitudes or anti-cheat.'))
        server.db.execute('INSERT INTO canonical_intent_receipts VALUES(?,?,?)',(actor,intention,seq))
    server.revision=seq


def relevant(event,actor,row):
    return (event.get('event')=='canonical_scene_observed'
        and event.get('publication')=='public_cast_activity'
        and event.get('outcome')=='native_path_observed_and_restored'
        and (event.get('character_id')==actor or event.get('character_id') in row.get('relationships',{})))
