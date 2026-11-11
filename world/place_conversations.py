"""Explicitly show a nearby character an actual changed shared mechanism."""
import json,secrets,time
from .guilds import GuildError
from .actor_objects import digest


def snapshot(server,conn,actor,network_id):
    from .npc_conversations import nearby
    from .actor_observation import observe
    from .campaign_mechanisms import definition,fingerprint,install
    character,obj=nearby(server,conn,actor)
    seen=observe(server,actor,character,dict(radius=4))
    if not any(c['x']==conn['state'][2] and c['y']==conn['state'][3] and c['walkable'] for c in seen['cells']):
        raise GuildError('Stand on connected ground beside this character.')
    network=definition(server,network_id);bound=fingerprint(server,network)
    entities={e['id']:e for e in seen['entities']}
    if any(i not in entities for i in network['objects']):raise GuildError('Bring the character within connected range of the whole mechanism.')
    status,row=committed_state(server,network_id,bound)
    # No player identities, contribution ledger or native party information.
    objects=[{k:entities[i][k] for k in ('id','x','y','gfx','text')} for i in network['objects']]
    facts=dict(network=network_id,definition=bound,phase=status['phase'],revision=seen['revision'],objects=objects,
               transition_receipt=row[1],basis='current_authority_state_and_committed_object_transition',
               limits='Current public state and its exact admitted transition. The visitor is not certified as its author; the character did not witness the original action. Reobserve before acting.')
    return character,obj,facts


def committed_state(server,network_id,bound):
    """Reconcile durable admitted evidence against current public control state."""
    from .campaign_mechanisms import install
    status=server.module_state.get('world_object_network_state',{}).get(network_id,{})
    install(server.db)
    row=server.db.execute('SELECT request,seq FROM campaign_mechanism_receipts WHERE network=? AND definition=? AND phase=? ORDER BY seq DESC LIMIT 1',(network_id,bound,status.get('phase'))).fetchone()
    if not row:raise GuildError('No committed action established this current mechanism phase.')
    archived=server.db.execute('SELECT data FROM object_transition_archive WHERE id=? AND seq=?',(row[0],row[1])).fetchone()
    if not archived:raise GuildError('The original admitted transition is unavailable.')
    receipt=json.loads(archived[0]);control=server.module_state.get('world_object_controls',{}).get(receipt['object'],{}).get('state',{})
    if receipt['state_digest']!=digest(control):raise GuildError('The mechanism changed after that receipt. Show a newly committed phase instead.')
    return status,row


def inspect_change(server,actor,row,args):
    """The actor discovers current evidence without a player demonstration or replay."""
    from .actor_observation import observe
    from .campaign_mechanisms import definition,fingerprint
    if set(args)!={'network','definition'} or any(type(v) is not str for v in args.values()):
        raise ValueError('Supply exact network and definition from discovery')
    network=definition(server,args['network']);bound=fingerprint(server,network)
    if bound!=args['definition']:raise ValueError('Mechanism definition changed')
    seen=observe(server,actor,row,dict(radius=4))
    entities={e['id']:e for e in seen['entities']}
    if any(i not in entities for i in network['objects']):raise ValueError('Observe the entire mechanism on connected nearby ground')
    try:status,receipt=committed_state(server,args['network'],bound)
    except GuildError:
        return dict(outcome='no_current_committed_change',committed=False,network=args['network'],definition=bound)
    return dict(outcome='current_committed_change',committed=True,network=args['network'],definition=bound,
        phase=status['phase'],transition_receipt=receipt[1],revision=seen['revision'],
        objects=[{k:entities[i][k] for k in ('id','x','y','gfx','text')} for i in network['objects']],
        basis='fresh_local_state_reconciled_with_admitted_transition',
        limits='No personal action credit or original eyewitness claim. A subsequent response is the actor choice; reobserve for current-state decisions.')


def command(server,conn,words):
    from .npc_conversations import deliver
    if len(words)==2 and words[0]=='show-place':
        from .npc_conversations import nearby
        nearby(server,conn,words[1])
        found=[]
        for key in sorted(server.module_state.get('world_object_networks',{})):
            try:_,_,facts=snapshot(server,conn,words[1],key)
            except (ValueError,GuildError):continue
            found.append('/guild npc show-place '+words[1]+' '+key)
            if len(found)==4:break
        return ['Nearby committed changes you can review:']+(found or ['None currently verifiable within connected range.'])
    if len(words) not in (3,4) or words[0]!='show-place':raise GuildError('Use /guild npc show-place NPC NETWORK to review a public demonstration.')
    actor,network=words[1:3]
    try:character,obj,facts=snapshot(server,conn,actor,network)
    except ValueError as exc:raise GuildError(str(exc)) from None
    signature=digest([character['version'],facts])
    if len(words)==3:
        token=secrets.token_hex(6);conn['place_conversation_offer']=dict(actor=actor,network=network,signature=signature,token=token,expires=time.monotonic()+60)
        return ['Show '+network+' in phase '+facts['phase']+' to '+actor+'?']+[o['id']+': '+o['text']+' ('+str(o['x'])+','+str(o['y'])+')' for o in facts['objects']]+[
            'Publishes its current objects and committed transition in world history. No credit or eyewitness claim.',
            'No personal-memory linking. The character chooses whether and how to respond.',
            '/guild npc show-place '+actor+' '+network+' '+token]
    offer=conn.get('place_conversation_offer',{})
    if (offer.get('actor')!=actor or offer.get('network')!=network or offer.get('signature')!=signature
        or offer.get('token')!=words[3] or time.monotonic()>offer.get('expires',0)):
        raise GuildError('Demonstration changed or expired. Review it again.')
    conn.pop('place_conversation_offer',None)
    return deliver(server,conn,character,obj,'Please look at the changed '+network+'.',place_evidence=facts)
