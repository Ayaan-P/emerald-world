"""Tool-free official API vision policy for one ordinary native trainer.

Invoked as a bounded, cancellable child by player_runtime, never as a GM.
No live request is made merely by importing or configuring this module.
"""
import argparse,base64,json,os,re,ssl,sys,urllib.request
from pathlib import Path
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from world.player_runtime import PROMPT,validate_actions
from world.player import _json
from world.author_backends import API_BACKENDS,validate
LIMIT=1024*1024


def request(provider,model,context,timeout,transport=None):
    validate(provider,model,timeout)
    if provider not in API_BACKENDS or type(context) is not dict:raise ValueError('Explicit API provider required')
    image=context.get('game_image')
    if type(image) is not str or len(image)>512*1024:raise ValueError('Bounded own-game image required')
    try:png=base64.b64decode(image,validate=True)
    except Exception:raise ValueError('Invalid own-game image') from None
    if not png.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('PNG game image required')
    data={k:v for k,v in context.items() if k!='game_image'}
    prompt=PROMPT+json.dumps(data,allow_nan=False,separators=(',',':'))
    if len(prompt.encode())>512*1024:raise ValueError('Observation too large')
    if provider=='openai-responses':
        payload=dict(model=model,input=[dict(role='user',content=[dict(type='input_text',text=prompt),dict(type='input_image',image_url='data:image/png;base64,'+image)])],tools=[],tool_choice='none',store=False,stream=False,max_output_tokens=2048,text=dict(format=dict(type='json_object')))
    else:
        payload=dict(model=model,messages=[dict(role='user',content=[dict(type='text',text=prompt),dict(type='image',source=dict(type='base64',media_type='image/png',data=image))])],tools=[],tool_choice=dict(type='none'),stream=False,max_tokens=2048)
    response=transport(payload,timeout) if transport else post(provider,payload,timeout)
    parts=[]
    if provider=='openai-responses':
        if type(response) is not dict or response.get('status')!='completed' or response.get('error') or response.get('incomplete_details'):raise ValueError('Incomplete response')
        for item in response.get('output',[]):
            if item.get('type')=='reasoning':continue
            if item.get('type')!='message' or item.get('role')!='assistant':raise ValueError('Provider tool use refused')
            for block in item.get('content',[]):
                if block.get('type')!='output_text' or type(block.get('text')) is not str:raise ValueError('Nontext response refused')
                parts.append(block['text'])
    else:
        if type(response) is not dict or response.get('type')!='message' or response.get('role')!='assistant' or response.get('stop_reason')!='end_turn' or response.get('stop_details'):raise ValueError('Incomplete response')
        for block in response.get('content',[]):
            if block.get('type') in ('thinking','redacted_thinking'):continue
            if block.get('type')!='text' or type(block.get('text')) is not str:raise ValueError('Provider tool use refused')
            parts.append(block['text'])
    text=''.join(parts)
    if not text or len(text.encode())>16384:raise ValueError('Invalid player response size')
    result=_json(text.encode());validate_actions(result)
    return result


def post(provider,payload,timeout):
    endpoint,key_name=API_BACKENDS[provider];key=os.environ.get(key_name)
    if not key:raise ValueError('Host API credential unavailable')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    headers={'Content-Type':'application/json'}
    if provider=='anthropic-messages':headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
    else:headers['Authorization']='Bearer '+key
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers=headers,method='POST')
    with opener.open(req,timeout=timeout) as response:
        raw=response.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('Response too large')
    return json.loads(raw)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--provider',choices=list(API_BACKENDS),required=True);parser.add_argument('--model',required=True);parser.add_argument('--timeout',type=float,required=True);args=parser.parse_args(argv)
    try:
        raw=sys.stdin.buffer.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('Input too large')
        print(json.dumps(request(args.provider,args.model,json.loads(raw),args.timeout)));return 0
    except Exception:
        print('player_api_failed_no_retry',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
