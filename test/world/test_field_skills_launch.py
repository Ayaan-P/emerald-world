import tempfile, unittest
from unittest.mock import patch
from world import launcher, expansion

class FieldSkillsLaunchTest(unittest.TestCase):
    def test_opt_in_and_default(self):
        with tempfile.TemporaryDirectory() as state:
            paths=launcher.profile_paths(state,'Ash',engine='expansion-native')
            base=launcher.game_command('/bin/true',state,paths,engine='expansion-native',online=False)
            enabled=launcher.game_command('/bin/true',state,paths,engine='expansion-native',online=False,field_skills=True)
            self.assertNotIn('--field-skills',base)
            self.assertEqual(enabled.count('--field-skills'),1)
            self.assertGreater(enabled.index('--field-skills'),enabled.index('--'))
            self.assertEqual([x for x in enabled if x!='--field-skills'],base)

    def test_no_vanilla_or_truthy_coercion(self):
        with tempfile.TemporaryDirectory() as state:
            for engine,value in [('vanilla',True),('expansion-native','yes'),('expansion-native',1)]:
                with self.assertRaises(ValueError):
                    launcher.game_command('/bin/true',state,launcher.profile_paths(state,'Ash',engine=engine),engine=engine,field_skills=value)

    def test_join_and_offline_cli(self):
        for command in ('join','offline'):
            with patch('world.expansion.run',return_value=0) as run:
                self.assertEqual(launcher.main(['--state-dir','/unused',command,'Ash','--engine','expansion-native','--field-skills']),0)
                self.assertTrue(run.call_args.args[0].field_skills)

    def test_session_dispatch(self):
        from argparse import Namespace
        args=Namespace(state_dir='/unused',trainer='Ash',command='join',binary=None,display=None,replay=None,frames=None,print_command=True,field_skills=True)
        with patch('world.expansion.ExpansionSession') as session:
            expansion.run(args)
            self.assertIs(session.return_value.run.call_args.kwargs['field_skills'],True)

if __name__=='__main__':unittest.main()
