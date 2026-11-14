"""Reserved command namespace. Never fall back to room/whisper publication."""
STORY=1
MYSTERY=2
GUILD=4
EXPLORE=8


def reserved(text):
    stripped=text.lstrip(' ')
    if not stripped.startswith('/'):return None
    head,separator,tail=stripped.partition(' ')
    return head.lower()+(separator+tail if separator else '')


def reject(server,conn,message):
    server.guild_chat.message(conn,conn['id'],message)
    conn['chat_status']='sent'
    server._queue(conn,server._snapshot(conn))


def route(server,conn,target,text):
    command=reserved(text)
    if command is None:return False
    if target!='*':
        reject(server,conn,'Commands are private actions, not messages to another trainer.')
        return True
    name=command.split(' ',1)[0]
    if name in ('/story','/mystery'):
        feature=getattr(server,'opportunity_chat' if name=='/story' else 'mysteries',None)
        if not conn.get('private_commands') or feature is None:
            reject(server,conn,'Private command unavailable. Update the paired client and server; nothing was shared.')
        else:feature.handle(conn,command)
        return True
    if name=='/explore':
        from .character_guides import handle as handle_character_guide
        if handle_character_guide(server,conn,command):
            return True
        if not server.landmark_survey.handle(conn,command):
            reject(server,conn,'Exploration command unavailable. Nothing was shared with the room.')
        return True
    if name in ('/guild','/g'):
        server.guild_chat.handle(conn,command)
        return True
    reject(server,conn,'Unknown private command. Nothing was shared with the room.')
    return True
