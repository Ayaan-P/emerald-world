"""Prepare optional opponent lineups from already owned persistent companions."""
import hashlib,json


def prepare(server, actor, row, args):
    from .actor_runtime import Pending
    from .characters import records
    from .character_companions import roster
    from .character_actions import compile_actions
    if set(args)!={'lineup','text'} or type(args['lineup']) is not str or len(args['lineup'])>200:
        raise ValueError('Supply a bounded JSON list of owned companion IDs and invitation text')
    try:ids=json.loads(args['lineup'])
    except ValueError:raise ValueError('Invalid lineup JSON')
    if type(ids) is not list or not 1<=len(ids)<=6 or any(type(i) is not str for i in ids) or len(set(ids))!=len(ids):raise ValueError('Choose one to six distinct companions')
    text=args['text']
    if type(text) is not str or not 1<=len(text)<=28 or any(not 32<=ord(c)<=126 for c in text):raise ValueError('Use literal invitation text up to 28 characters')
    character=records(server.module_state).get(actor);obj=next((o for o in server.objects if o['id']==actor),None)
    if not character or character['status']!='active' or not obj:raise ValueError('An active world-owned trainer is required')
    owned={m['individual']:m for m in roster(server,actor)}
    if any(i not in owned for i in ids):raise ValueError('Lineup must use actual owned identified companions')
    team=[dict(individual=i,species=owned[i]['species'],level=owned[i]['authored_level']) for i in ids]
    if server.job is not None or server.deployment is not None or not server.candidate:raise ValueError('Current idle mechanic required')
    obj=dict(obj,text=text)
    action=dict(id=actor,expected_version=character['version'],evidence=list(row['evidence']),reason='Prepared an optional challenge with owned companions; no battle outcome claimed.',changes=dict(team=team),object=obj)
    context=server.inspect();context['runtime']=dict(previous_source=server.candidate.source)
    context['recalled_history']=dict(events=server.memory.history()['events'])
    source=compile_actions([action],context)
    if len(source.encode())>256*1024:raise ValueError('Consolidate mechanic source before preparing challenge')
    sha=hashlib.sha256(source.encode()).hexdigest();path=server.runtime.candidates/('challenge_'+sha+'.py')
    try:
        with path.open('x') as f:f.write(source)
    except FileExistsError:
        if path.is_symlink() or path.read_text()!=source:raise ValueError('Challenge candidate conflict')
    def dispatch():server.deployment=(None,path,None)
    return Pending(dict(version=character['version']+1,team=team,object=obj),dispatch)


def poll(server,actor,row,pending):
    from .characters import records
    current=records(server.module_state).get(actor,{})
    obj=next((o for o in server.objects if o['id']==actor),None)
    if current.get('version')!=pending['version'] or current.get('team')!=pending['team'] or obj!=pending['object']:raise ValueError('Challenge preparation was not admitted')
    return dict(outcome='optional_challenge_prepared',character_id=actor,version=current['version'],lineup=[m['individual'] for m in current['team']],requires='Player approaches and explicitly chooses the existing native trainer battle. No battle started or victory inferred.')
