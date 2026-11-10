"""Private story choices through the already authenticated native chat surface."""
import secrets
import sqlite3
import time


class OpportunityChat:
    def __init__(self,server,validate_coords,freshness):self.server=server;self.validate_coords=validate_coords;self.freshness=freshness

    def handle(self,conn,message):
        words=message.split()
        if not words or words[0]!='/story':return False
        s=self.server
        try:
            with s.lock:
                state=conn.get('state');updated=conn.get('state_time')
                if (not state or not state[6] or updated is None or time.monotonic()-updated>self.freshness
                        or tuple(state[:2]) in (s.cave_map,s.wilds_map)):
                    raise ValueError('Stand ready on a standard map to read its stories.')
                place=self.validate_coords(*state[:4])['name']
                if len(words)==7 and words[1] in ('pick','pick-public'):
                    result=s.opportunities.choose(conn['id'],place,*words[2:5],int(words[5]),words[6],public=words[1]=='pick-public')
                    if 'public_receipt' in result:s.revision=result['public_receipt']
                    lines=[result['text'],'Read /story to see what changed.']
                elif len(words)<=2:
                    packs=s.opportunities.offers(conn['id'],place,words[1] if len(words)==2 else None)
                    lines=[]
                    for pack in packs[:1]:
                        lines.append(pack['title']+' ['+pack['id']+']')
                        if pack.get('public_author'):lines.append('PUBLIC choices and changes enter world history for agents and players; your trainer name is omitted.')
                        for scene in pack['scenes'][:2]:
                            lines.append(scene['text'])
                            for choice in scene['choices']:
                                lines.append(choice['text'])
                                lines.append(f"/story {'pick-public' if pack.get('public_author') else 'pick'} {pack['id']} {scene['id']} {choice['id']} {pack['revision']} r{secrets.token_hex(6)}")
                    if len(packs)>1:lines.append('Other stories: '+', '.join('/story '+p['id'] for p in packs[1:4]))
                    if not lines:lines=['No story opportunities are available here.']
                else:raise ValueError('Use /story, /story PACK, or the displayed choice line.')
        except (ValueError,TypeError,sqlite3.Error) as exc:
            lines=[str(exc) if isinstance(exc,ValueError) else 'Story transaction failed. Read /story before retrying.']
        for line in lines[:16]:s.guild_chat.message(conn,conn['id'],line[:120])
        conn['chat_status']='sent';s._queue(conn,s._snapshot(conn));return True
