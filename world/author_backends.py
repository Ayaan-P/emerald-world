"""Bounded tool-free author backends. Selection is explicit; never fall back."""
import argparse,json,math,os,re,sys
from pathlib import Path
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parent.parent))

API_BACKENDS={
    'openai-responses':('https://api.openai.com/v1/responses','OPENAI_API_KEY'),
    'anthropic-messages':('https://api.anthropic.com/v1/messages','ANTHROPIC_API_KEY'),
}
PROVIDERS=('codex',*API_BACKENDS)
LIMIT=2*1024*1024


def validate(provider,model,timeout):
    if provider not in PROVIDERS:raise ValueError('Unknown author backend')
    if provider=='codex':
        from world.runtime_gm import validate_config
        validate_config(model,timeout,2)
    elif type(model) is not str or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',model):
        raise ValueError('Choose an explicit API model ID, not a provider/CLI alias')
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0<timeout<=3600:raise ValueError('Invalid author timeout')


def preflight(provider,model,timeout=120):
    validate(provider,model,timeout)
    if provider=='codex':
        from world.runtime_gm import preflight_author
        return preflight_author()
    # Only check presence. Never read credential files, echo keys, or probe the network.
    if not os.environ.get(API_BACKENDS[provider][1]):raise ValueError('Selected API backend needs its host-provided credential; no work claimed')
    return dict(ok=True,provider=provider,model=model,scope='local_prerequisites_only',live_model_verified=False)


def argv(provider,model,timeout,*,private=False):
    validate(provider,model,timeout)
    if private and provider=='anthropic-messages':raise ValueError("Existing private grants name OpenAI; Anthropic private processing is not authorized")
    if provider=='codex':
        from world.runtime_gm import luna_author_argv
        return luna_author_argv(model,timeout)+(['--private-cast'] if private else [])
    return [sys.executable,str(Path(__file__).resolve()),'--provider',provider,'--model',model,'--timeout',str(timeout)]+(['--private-cast'] if private else [])


def check_result(result,private=False):
    if type(result) is not dict:raise ValueError('Author must return a JSON object')
    allowed=({'reply','interpretation'},) if private else ({'source','tests'},{'character_plan','tests'},{'character_actions','tests'},{'canonical_actions','tests'})
    if set(result) not in allowed:raise ValueError('Unexpected author result schema')
    return result


def decode(response,private=False):
    if type(response) is not dict or response.get('status')!='completed' or response.get('error') or response.get('incomplete_details'):
        raise ValueError('Author response incomplete or failed')
    parts=[]
    for item in response.get('output',[]):
        if item.get('type')=='reasoning':continue
        if item.get('type')!='message' or item.get('role')!='assistant':raise ValueError('Tool or unexpected output refused')
        for content in item.get('content',[]):
            if content.get('type')!='output_text' or type(content.get('text')) is not str:raise ValueError('Nontext/refused author output')
            parts.append(content['text'])
    if not parts:raise ValueError('Missing author output')
    return check_result(json.loads(''.join(parts)),private)


def request(model,prompt,timeout,*,private=False,transport=None,provider="openai-responses"):
    validate(provider,model,timeout)
    if provider not in API_BACKENDS:raise ValueError("API backend required")
    if private and provider=="anthropic-messages":raise ValueError("Private grants name OpenAI")
    if type(prompt) is not str or len(prompt.encode())>LIMIT:raise ValueError('Author prompt too large')
    payload=dict(model=model,input=prompt,tools=[],tool_choice='none',store=False,stream=False,
                 max_output_tokens=16384,text=dict(format=dict(type='json_object')))
    if provider=='anthropic-messages':
        payload=dict(model=model,messages=[dict(role='user',content=prompt)],tools=[],tool_choice=dict(type='none'),stream=False,max_tokens=16384)
    # One attempt only, including HTTP errors and uncertain timeouts.
    response=transport(payload,timeout) if transport else post(payload,timeout,provider=provider)
    return decode_anthropic(response) if provider=='anthropic-messages' else decode(response,private)


def decode_anthropic(response):
    if (type(response) is not dict or response.get('type')!='message' or response.get('role')!='assistant'
            or response.get('stop_reason')!='end_turn' or response.get('stop_details')):raise ValueError('Claude response incomplete or refused')
    parts=[]
    for item in response.get('content',[]):
        if item.get('type') in ('thinking','redacted_thinking'):continue
        if item.get('type')!='text' or type(item.get('text')) is not str:raise ValueError('Claude tools or nontext output refused')
        parts.append(item['text'])
    if not parts:raise ValueError('Missing Claude output')
    return check_result(json.loads(''.join(parts)))


def post(payload,timeout,*,provider='openai-responses'):
    import urllib.request,ssl
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    endpoint,key_name=API_BACKENDS[provider]
    key=os.environ.get(key_name)
    if not key:raise ValueError('Host API credential unavailable')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    headers={'Content-Type':'application/json','Authorization':'Bearer '+key}
    if provider=='anthropic-messages':headers['anthropic-version']='2026-10-21'
    req=urllib.request.Request(endpoint,data=json.dumps(payload).encode(),headers=headers,method='POST')
    with opener.open(req,timeout=timeout) as response:
        raw=response.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('Author response exceeds byte limit')
    return json.loads(raw)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provider',choices=list(API_BACKENDS),required=True)
    p.add_argument('--model',required=True);p.add_argument('--timeout',type=float,default=120);p.add_argument('--private-cast',action='store_true')
    a=p.parse_args(argv)
    try:
        preflight(a.provider,a.model,a.timeout)
        raw=sys.stdin.buffer.read(LIMIT+1)
        if len(raw)>LIMIT:raise ValueError('Prompt limit')
        print(json.dumps(request(a.model,raw.decode(),a.timeout,private=a.private_cast,provider=a.provider)));return 0
    except Exception:
        # Neither provider response/headers nor credential/error details escape.
        print(json.dumps(dict(error='author_failed_no_retry')),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
