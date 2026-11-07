import unittest
from unittest.mock import patch

from manga_ai.engines import EngineDescriptor, list_engines, run_engine


class RegistryContractTests(unittest.TestCase):
    def test_registry_has_unique_stable_ids_and_capabilities(self):
        data=list_engines();engines=data['engines'];ids=[e['id'] for e in engines]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(data['default'],'baseline')
        self.assertIn('1107',ids)
        self.assertTrue(all(e['version'] and e['api_version']==data['api_version'] for e in engines))

    def test_dispatch_and_version_are_never_silently_changed(self):
        with self.assertRaises(ValueError):run_engine('unknown','x',[])
        with self.assertRaises(ValueError):run_engine('1107','x',[],version='other')
        with patch('manga_ai.engine.render_clean',return_value={'overlay':'o','applied':[],'skipped':[],'blocked':{}}) as render:
            result=run_engine('baseline','manifest',[],version='baseline-1')
        self.assertEqual(result['engine_id'],'baseline');self.assertEqual(result['version'],'baseline-1')
        render.assert_called_once()

    def test_invalid_engine_result_fails_closed(self):
        with patch('manga_ai.engine.render_clean',return_value={}):
            with self.assertRaises(ValueError):run_engine('baseline','manifest',[])

    def test_dropdown_version_matches_the_live_handler(self):
        from manga_ai.engine_1107 import VERSION
        engine = next(row for row in list_engines()['engines'] if row['id'] == '1107')
        self.assertEqual(engine['version'], VERSION)

    def test_registered_engine_needs_no_dispatch_branch(self):
        from types import SimpleNamespace
        descriptor=EngineDescriptor('demo','v1','Demo',(),True,'trusted.demo','run')
        fn=lambda *args:{'overlay':'o','applied':[],'skipped':[],'blocked':{}}
        with patch.dict('manga_ai.engines._ENGINES',{'demo':descriptor}), patch('manga_ai.engines.import_module',return_value=SimpleNamespace(run=fn)):
            self.assertEqual(run_engine('demo','manifest',[],version='v1')['engine_id'],'demo')
