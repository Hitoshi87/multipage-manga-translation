import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from manga_ai.hardware import ResilientSession,select_providers,create_session,SESSION_REPORTS

class FakeSession:
 def __init__(self,providers,fail=False):self.providers=providers;self.fail=fail
 def get_providers(self):return self.providers
 def run(self,*args,**kw):
  if self.fail:raise RuntimeError('device error')
  return ['cpu result']
class FakeOrt:
 __version__='1.0'
 def __init__(self,fail_init=False):self.calls=[];self.fail_init=fail_init
 def get_available_providers(self):return ['CUDAExecutionProvider','CPUExecutionProvider']
 def InferenceSession(self,path,sess_options,providers):
  self.calls.append(providers)
  if self.fail_init and providers[0]=='CUDAExecutionProvider':raise RuntimeError('cuda init failure')
  return FakeSession(providers,fail=providers[0]=='CUDAExecutionProvider')

class HardwareDispatchTests(unittest.TestCase):
 def test_detection_is_capability_based_and_cpu_safe(self):
  p=['CoreMLExecutionProvider','CPUExecutionProvider'];self.assertEqual(select_providers('Darwin','arm64',p,'text'),['CPUExecutionProvider']);self.assertEqual(select_providers('Darwin','arm64',p,'balloon')[0][0],'CoreMLExecutionProvider')
  self.assertEqual(select_providers('Darwin','x86_64',p,'balloon'),['CPUExecutionProvider'])
  self.assertEqual(select_providers('Windows','AMD64',['CUDAExecutionProvider','CPUExecutionProvider'],'ctd')[0],'CUDAExecutionProvider')
  self.assertEqual(select_providers('Linux','x86_64',['CPUExecutionProvider'],'ctd'),['CPUExecutionProvider'])
  self.assertEqual(select_providers('Linux','x86_64',['CUDAExecutionProvider','CPUExecutionProvider'],'ctd','cpu'),['CPUExecutionProvider'])
 def test_failed_cuda_initialization_and_inference_retry_on_cpu(self):
  for init in (True,False):
   ort=FakeOrt(init)
   with patch.dict('os.environ',{'MANGA_ACCEL':'auto'}),patch('manga_ai.hardware.platform.system',return_value='Linux'),patch('manga_ai.hardware.platform.machine',return_value='x86_64'):
    sess=create_session(ort,'model',None,'ctd');self.assertEqual(sess.run(None,{}),['cpu result']);self.assertEqual(ort.calls[-1],['CPUExecutionProvider']);self.assertTrue(SESSION_REPORTS['ctd']['fallback'])
