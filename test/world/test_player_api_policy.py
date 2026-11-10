"""Fake API replies through real ordinary-player controller boundaries; no live model."""
import base64,json,unittest
from pathlib import Path
from unittest.mock import patch
from test_player import NativeSocket,reply
from test_player_runtime import Clock,observation
from world import player_api_policy as api
from world.player_runtime import APIPolicy,RuntimePlayer,PolicyError
from world.player_mcp import ppm_to_png


def response(provider,value):
 text=json.dumps(value)
 if provider=='anthropic-messages':return dict(type='message',role='assistant',stop_reason='end_turn',content=[dict(type='text',text=text)])
 return dict(status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=text)])])


class PlayerAPITests(unittest.TestCase):
 def context(self):return dict(observation=observation(),game_image=base64.b64encode(ppm_to_png(b'P6\n1 1\n255\n\xff\0\0')).decode(),untrusted=True)
 def test_both_official_payloads_are_vision_tool_free_and_strict(self):
  for provider in ('anthropic-messages','openai-responses'):
   calls=[]
   def transport(payload,timeout):
    calls.append(payload);self.assertEqual(payload['tools'],[]);self.assertFalse(payload['stream'])
    return response(provider,dict(actions=[dict(buttons=['A'],frames=1)]))
   result=api.request(provider,'explicit-model',self.context(),30,transport)
   self.assertEqual(result['actions'][0]['buttons'],['A']);self.assertEqual(len(calls),1)
   wire=json.dumps(calls[0]);self.assertIn(self.context()['game_image'],wire);self.assertIn('UNTRUSTED DATA',wire)
   if provider=='openai-responses':self.assertFalse(calls[0]['store'])
   with self.assertRaises(ValueError):api.request(provider,'explicit-model',self.context(),30,lambda p,t:response(provider,dict(actions=[dict(buttons=['ADMIN'],frames=1)])))
 def test_refusal_tools_incomplete_and_redirect_do_not_become_actions(self):
  bad=[dict(type='message',role='assistant',stop_reason='tool_use',content=[dict(type='tool_use',name='shell')]),dict(type='message',role='assistant',stop_reason='max_tokens',content=[])]
  for value in bad:
   with self.assertRaises(ValueError):api.request('anthropic-messages','explicit-model',self.context(),30,lambda p,t:value)
  with self.assertRaises(ValueError):api.request('openai-responses','explicit-model',self.context(),30,lambda p,t:dict(status='completed',output=[dict(type='function_call',name='shell')]))
 def test_explicit_consent_provider_and_bounded_child_serialization(self):
  with self.assertRaises(ValueError):APIPolicy('anthropic-messages','explicit-model')
  with self.assertRaises(ValueError):APIPolicy('http://custom','explicit-model',share_game_view=True)
  policy=APIPolicy('anthropic-messages','explicit-model',share_game_view=True)
  def invoke(argv,text,timeout,stop,maximum,cwd):
   self.assertIn('anthropic-messages',argv);self.assertEqual(json.loads(text),self.context())
   return b'{"actions":[]}'
  with patch('world.player_runtime._invoke',side_effect=invoke):self.assertEqual(policy(self.context()),dict(actions=[]))
 def test_real_socket_screenshot_to_policy_to_own_button(self):
  for provider in ('anthropic-messages','openai-responses'):
   clock=Clock();calls=[]
   def handler(conn,req):
    if req['op']=='screenshot':
     path=Path(native.path).parent/'screenshot.ppm';path.write_bytes(b'P6\n1 1\n255\n\xff\0\0');reply(conn,req,screenshot=str(path),state=observation()['state'])
    else:reply(conn,req,state=observation()['state'])
   def transport(payload,timeout):calls.append(payload);return response(provider,dict(actions=[dict(buttons=['RIGHT'],frames=1)]))
   class FixturePolicy:
    requires_game_image=True
    def __call__(self,context):
     self_context=context
     self.assert_context=self_context
     return api.request(provider,'explicit-model',context,30,transport)
   policy=FixturePolicy()
   with NativeSocket(handler) as native:
    with RuntimePlayer(native.path,policy,interval=1,min_model_interval=1,clock=clock) as runtime:
     self.assertEqual(runtime.step()['status'],'baseline');clock.now=2
     self.assertEqual(runtime.step(),dict(status='acted',completed=1))
    self.assertEqual([r['op'] for r in native.requests],['observe','observe','screenshot','press'])
    self.assertNotIn(native.temp.name,json.dumps(calls));self.assertEqual(native.requests[-1]['buttons'],['RIGHT'])
 def test_substituted_screenshot_path_never_reaches_provider_or_press(self):
  clock=Clock();calls=[]
  class Policy:
   requires_game_image=True
   def __call__(self,c):calls.append(c);return dict(actions=[])
  def handler(conn,req):reply(conn,req,screenshot='/etc/passwd',state=observation()['state'])
  with NativeSocket(handler) as native:
   with RuntimePlayer(native.path,Policy(),interval=1,min_model_interval=1,clock=clock) as runtime:
    runtime.step();clock.now=2;self.assertEqual(runtime.step()['status'],'policy_failed')
   self.assertFalse(calls);self.assertNotIn('press',[r['op'] for r in native.requests])
 def test_failed_api_request_is_not_retried(self):
  calls=[]
  def transport(p,t):calls.append(p);raise TimeoutError('uncertain provider submission')
  with self.assertRaises(TimeoutError):api.request('anthropic-messages','explicit-model',self.context(),30,transport)
  self.assertEqual(len(calls),1)

class PlayerAPIComponentTests(unittest.TestCase):
 def test_runtime_image_child_payload_and_actions_with_explicit_transport_fixtures(self):
  import tempfile
  from world import player_runtime as runtime_module
  for provider in ('anthropic-messages','openai-responses'):
   with tempfile.TemporaryDirectory() as root:
    endpoint=str(Path(root)/'player.sock');clock=Clock();pressed=[];payloads=[]
    class ClientFixture:
     def __init__(self,*a,**k):pass
     def observe(self):return observation()
     def screenshot(self):
      path=Path(root)/'screenshot.ppm';path.write_bytes(b'P6\n1 1\n255\n\xff\0\0')
      return dict(observation(),screenshot=str(path))
     def press(self,**args):pressed.append(args);return dict(ok=True)
     def close(self):pass
    def invoke(argv,text,timeout,stop,maximum,cwd):
     self.assertEqual(argv[argv.index('--provider')+1],provider)
     def transport(payload,timeout):payloads.append(payload);return response(provider,dict(actions=[dict(buttons=['A'],frames=1)]))
     return json.dumps(api.request(provider,'explicit-model',json.loads(text),timeout,transport)).encode()
    with patch.object(runtime_module,'PlayerClient',ClientFixture),patch.object(runtime_module,'_invoke',side_effect=invoke):
     policy=APIPolicy(provider,'explicit-model',share_game_view=True)
     with RuntimePlayer(endpoint,policy,interval=1,min_model_interval=1,clock=clock) as runtime:
      runtime.step();clock.now=2;self.assertEqual(runtime.step()['status'],'acted')
    self.assertEqual(pressed,[dict(buttons=['A'],frames=1)]);self.assertNotIn(root,json.dumps(payloads));self.assertEqual(len(payloads),1)
 def test_cli_missing_sharing_or_credentials_never_attaches(self):
  from world import player_runtime as module
  with patch.object(module,'RuntimePlayer') as runtime,patch.dict('os.environ',{},clear=True):
   self.assertEqual(module.main(['--endpoint','/not-opened/player.sock','--provider','anthropic-messages','--model','explicit-model']),1)
   self.assertEqual(module.main(['--endpoint','/not-opened/player.sock','--provider','anthropic-messages','--model','explicit-model','--share-game-view']),1)
   runtime.assert_not_called()
 def test_fixed_official_transport_headers_no_redirect_and_bounded_read(self):
  import urllib.request
  class ReplyFixture:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,limit):self.limit=limit;return b'{}'
  for provider in ('anthropic-messages','openai-responses'):
   opened=[];body=ReplyFixture()
   class OpenerFixture:
    def open(self,request,timeout):opened.append(request);return body
   def build(*handlers):
    redirect=next(h for h in handlers if isinstance(h,urllib.request.HTTPRedirectHandler))
    self.assertIsNone(redirect.redirect_request(None,None,None,None,None,None))
    return OpenerFixture()
   key=api.API_BACKENDS[provider][1]
   with patch.dict('os.environ',{key:'fixture-not-a-real-key'},clear=True),patch.object(urllib.request,'build_opener',side_effect=build):
    self.assertEqual(api.post(provider,dict(model='fixture'),3),{})
   request=opened[0];self.assertEqual(request.full_url,api.API_BACKENDS[provider][0]);self.assertEqual(body.limit,api.LIMIT+1)
   self.assertEqual(request.get_header('X-api-key') if provider=='anthropic-messages' else request.get_header('Authorization'),'fixture-not-a-real-key' if provider=='anthropic-messages' else 'Bearer fixture-not-a-real-key')
