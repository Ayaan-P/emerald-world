"""Private split-party deployment over existing battles and voluntary visits."""
import re


def validate(server,node,cast):
    from .campaign_visits import validate as visit
    from .campaign_preparation import validate as preparation
    if set(node)!={'roles','win','loss'} or type(node['roles']) is not dict or not 2<=len(node['roles'])<=4:
        raise ValueError('Split stage requires 2..4 roles and win/loss routes')
    for role,task in node['roles'].items():
        if type(role) is not str or not re.fullmatch('[a-z][a-z0-9_]{0,15}',role) or type(task) is not dict:
            raise ValueError('Invalid split role')
        if 'visit' in task:
            if set(task)!={'visit'}:raise ValueError('Visit role contains only visit')
            visit(server,dict(task,next=[]))
        else:
            if 'opponent' not in task or set(task)-{'opponent','preparation'}:raise ValueError('Role is an existing battle or ordinary-map visit')
            if type(task['opponent']) is not str or task['opponent'] not in cast or not cast[task['opponent']]['team']:
                raise ValueError('Role opponent requires an existing trainer team')
            preparation(task.get('preparation',{}),cast)


def party_size(doc,size):
    for node in doc['nodes'].values():
        if 'roles' not in node:continue
        roles=node['roles'];optional=sum('revision' in task.get('visit',{}) for task in roles.values())
        if not len(roles)-optional<=size<=len(roles):
            raise ValueError('This campaign requires enough trainers for all non-NPC roles')


def assignment_count(group):
    return len(group.get('roles',{}))+len(group.get('npc_roles',{}))


def stage_status(doc,node):
    return 'deploying' if 'roles' in doc['nodes'][node] else 'ready'


def effective(server,campaign,data):
    from .battle_campaigns import document
    node=document(server,campaign)['nodes'][data['node']]
    if 'roles' not in node:return node
    role=data.get('role')
    if not data.get('shared') or role not in node['roles']:raise ValueError('Choose a shared deployment role first')
    task=dict(node['roles'][role])
    task.update(dict(next=[]) if 'visit' in task else dict(win=[],loss=[]))
    return task


def choose(server,conn,key,group,role):
    from .battle_campaigns import document,active,save
    from .shared_campaigns import member,store,update_members
    if group['status']!='deploying' or member(conn) not in group['members']:raise ValueError('No shared role selection open')
    current=active(server,conn)
    if not current or current[1].get('shared')!=key or current[1]['status']!='deploying':raise ValueError('Current save is not in this deployment')
    node=document(server,group['campaign'])['nodes'][group['node']]
    assignments=group.setdefault('roles',{})
    if role not in node['roles'] or role in list(assignments.values())+list(group.get('npc_roles',{}).values()) or conn['id'] in assignments:
        raise ValueError('Choose an unclaimed role; selected roles remain fixed for this stage')
    with server.db:
        assignments[conn['id']]=role
        data=current[1];data['role']=role;save(server,conn,current[0],data)
        if assignment_count(group)==len(node['roles']):
            group['status']='ready';update_members(server,key,group,status='ready')
        store(server,key,group)


def rows(server,conn,current,group):
    from .battle_campaigns import document
    node=document(server,current[0])['nodes'][group['node']]
    if 'roles' not in node:return []
    assignments=group.get('roles',{});out=[('Split party. Each trainer chooses one distinct task. All must report before regrouping.',None)]
    for role,task in node['roles'].items():
        claimed=next((trainer for trainer,chosen in list(assignments.items())+list(group.get('npc_roles',{}).items()) if chosen==role),None)
        label=task['visit']['label'] if 'visit' in task else 'Battle '+task['opponent']
        action=['role',role] if group['status']=='deploying' and claimed is None and conn['id'] not in assignments else None
        out.append((role+' - '+label+(' - claimed by '+claimed if claimed else ' - available'),action))
    if conn['id'] in assignments:out.append(('Your task: '+assignments[conn['id']],None))
    return out
