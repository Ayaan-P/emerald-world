"""Official API contracts with fake transports, no credentials/network/model use."""
import copy,json,tempfile,unittest
from unittest.mock import patch,MagicMock
from world import author_backends as b, runtime_gm as runtime,private_cast_worker as private
import test_canonical_cast as fixture


def openai(result):return dict(status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text=json.dumps(result))])])
def anthropic(result):return dict(type='message',role='assistant',stop_reason='end_turn',content=[dict(type='text',text=json.dumps(result))])

class BackendTests(unittest.TestCase):
 def test_two_provider_results_enter_actual_canonical_compiler_and_authority(self):
  for provider,wrapper in [('openai-responses',openai),('anthropic-messages',anthropic)]:
   with self.subTest(provider=provider):
    f=fixture.CanonicalCastTests();f.setUp()
    try:
     response=dict(canonical_actions=[f.action()],tests='assert True');calls=[]
     def transport(payload,timeout):calls.append(payload);return wrapper(response)
     result=b.request('explicit-model', 'Return JSON for this public fictional cast.',120,provider=provider,transport=transport)
     f.apply(result['canonical_actions'][0]);self.assertIn('canon_rydel',f.s.module_state['canonical_cast'])
     self.assertEqual(len(calls),1);self.assertEqual(calls[0]['tools'],[])
     self.assertEqual(calls[0]['tool_choice'],'none' if provider=='openai-responses' else {'type':'none'})
     self.assertNotIn('previous_response_id',calls[0]);self.assertNotIn('container',calls[0])
     if provider=='openai-responses':self.assertFalse(calls[0]['store'])
    finally:f.doCleanups()
 def test_tools_truncation_refusal_and_arbitrary_schema_fail_closed(self):
  good=dict(source='source',tests='tests')
  for response in [dict(status='incomplete',output=[]),dict(status='completed',output=[dict(type='function_call')]),openai(dict(command='shell'))]:
   with self.assertRaises(ValueError):b.decode(response)
  for response in [dict(type='message',role='assistant',stop_reason='tool_use',content=[]),dict(type='message',role='assistant',stop_reason='end_turn',content=[dict(type='tool_use')])]:
   with self.assertRaises(ValueError):b.decode_anthropic(response)
 def test_private_grants_do_not_change_recipient(self):
  claim=MagicMock()
  with self.assertRaises(ValueError):private.step('unused','explicit-model',provider='anthropic-messages',request=claim)
  claim.assert_not_called()
  with self.assertRaises(ValueError):b.request('explicit-model','JSON',120,provider='anthropic-messages',private=True,transport=claim)
  claim.assert_not_called()
  self.assertEqual(b.decode(openai(dict(reply='Hello',interpretation='Tentative')),True)['reply'],'Hello')
 def test_no_retry_and_model_provider_configuration_is_explicit(self):
  transport=MagicMock(side_effect=TimeoutError('uncertain'))
  with self.assertRaises(TimeoutError):b.request('explicit-model','JSON',120,transport=transport)
  self.assertEqual(transport.call_count,1)
  for model in ('openai-codex/gpt-6-luna','https://other','', 'model\n'):
   with self.assertRaises(ValueError):b.validate('openai-responses',model,120)
  with self.assertRaises(ValueError):b.validate('unreviewed-provider','model',120)
  with tempfile.TemporaryDirectory() as tmp:
   with runtime.RuntimeGM(tmp,'unused',model='explicit-model',provider='anthropic-messages') as worker:
    self.assertEqual(worker.provider,'anthropic-messages')
    command=b.argv(worker.provider,worker.model,worker.timeout)
    self.assertNotIn('codex',command);self.assertIn('anthropic-messages',command)
 def test_preflight_has_no_network_or_secret_output(self):
  with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'synthetic-test-key'},clear=True),patch.object(b,'post') as post:
   result=b.preflight('anthropic-messages','explicit-model')
  self.assertNotIn('synthetic-test-key',json.dumps(result));post.assert_not_called()
  with patch.dict('os.environ',{},clear=True),self.assertRaises(ValueError):b.preflight('openai-responses','explicit-model')
 def test_fixed_destinations_disabled_proxy_redirect_and_output_limit(self):
  response=MagicMock();response.__enter__.return_value=response;response.read.return_value=json.dumps(anthropic(dict(source='s',tests='t'))).encode()
  opener=MagicMock();opener.open.return_value=response
  with patch.dict('os.environ',{'ANTHROPIC_API_KEY':'synthetic-test-key'},clear=True),patch('urllib.request.build_opener',return_value=opener) as build:
   b.post({},120,provider='anthropic-messages')
  req=opener.open.call_args.args[0];self.assertEqual(req.full_url,'https://api.anthropic.com/v1/messages')
  self.assertEqual(req.get_header('Anthropic-version'),'2026-10-21')
  handlers=build.call_args.args;self.assertEqual(handlers[0].proxies,{})
  self.assertIsNone(handlers[1].redirect_request(None,None,None,None,None,None))
  response.read.return_value=b'x'*(b.LIMIT+1)
  with patch.dict('os.environ',{'OPENAI_API_KEY':'synthetic-test-key'},clear=True),patch('urllib.request.build_opener',return_value=opener),self.assertRaises(ValueError):b.post({},120)
