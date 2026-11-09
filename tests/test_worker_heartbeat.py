import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from manga_ai.cli import main
from manga_ai.worker_heartbeat import heartbeat


class WorkerHeartbeatTests(unittest.TestCase):
    def test_heartbeat_advances_and_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'heartbeat'
            with heartbeat(path,interval=.02):
                self.assertTrue(path.exists())
                first=path.stat().st_mtime_ns
                time.sleep(.09)
                self.assertGreater(path.stat().st_mtime_ns,first)
            final=path.stat().st_mtime_ns
            time.sleep(.05)
            self.assertEqual(path.stat().st_mtime_ns,final)

    def test_request_runs_with_heartbeat_and_preserves_response_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);request=folder/'request.json';response=folder/'response.json'
            request.write_text(json.dumps({'operation':'example'}),encoding='utf8')
            def dispatch(payload):
                self.assertEqual(payload['operation'],'example')
                self.assertTrue((folder/'heartbeat').exists())
                return {'ok_value':42}
            with patch('manga_ai.cli.dispatch',side_effect=dispatch):
                self.assertEqual(main(['--request',str(request),'--response',str(response)]),0)
            self.assertEqual(json.loads(response.read_text(encoding='utf8')),
                             {'ok':True,'result':{'ok_value':42}})

    def test_failed_request_still_writes_error_response(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);request=folder/'request.json';response=folder/'response.json'
            request.write_text(json.dumps({'operation':'example'}),encoding='utf8')
            with patch('manga_ai.cli.dispatch',side_effect=ValueError('test failure')):
                self.assertEqual(main(['--request',str(request),'--response',str(response)]),1)
            result=json.loads(response.read_text(encoding='utf8'))
            self.assertFalse(result['ok']);self.assertEqual(result['error'],'test failure')
