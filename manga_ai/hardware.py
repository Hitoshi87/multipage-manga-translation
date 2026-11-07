"""Conservative, capability-driven ONNX Runtime provider selection.

CoreML may assign only part of a graph and may use CPU, GPU or ANE. Availability
is not proof of hardware execution. Set MANGA_ACCEL=cpu to roll back.
"""

from .runtime.resources import sha256_file
import logging
import os
import platform
from pathlib import Path

LOG=logging.getLogger(__name__)
COREML_VALIDATED_MODELS=frozenset(('balloon','ctd','head'))
SESSION_REPORTS={}


class ResilientSession:
    def __init__(self, session, ort, path, options, model, accelerated):
        self._session=session;self._ort=ort;self._path=path;self._options=options;self._model=model;self._accelerated=accelerated

    def __getattr__(self, name):return getattr(self._session,name)

    def run(self, *args, **kwargs):
        try:return self._session.run(*args,**kwargs)
        except Exception as exc:
            if not self._accelerated:raise
            LOG.warning('%s accelerated inference failed; retrying on CPU',self._model,exc_info=True)
            # Drop the failed device session before allocating CPU weights.
            self._session=None
            self._session=self._ort.InferenceSession(str(self._path),sess_options=self._options,providers=['CPUExecutionProvider']);self._accelerated=False
            SESSION_REPORTS[self._model]={'requested':'accelerated','registered':self._session.get_providers(),'fallback':True,'reason':str(exc)[:2048]}
            return self._session.run(*args,**kwargs)


def select_providers(system, machine, available, model, policy='auto'):
    available=set(available);machine=machine.lower();system=system.lower();policy=policy.lower()
    if policy not in ('auto','cpu','coreml','cuda'):raise ValueError('MANGA_ACCEL phải là auto, cpu, coreml hoặc cuda')
    if policy=='cpu':return ['CPUExecutionProvider']
    if policy=='coreml':
        # Only models validated on CoreML: forcing the rest through it makes
        # partitioned graphs + per-process recompiles slower than plain CPU.
        if 'CoreMLExecutionProvider' in available and model in COREML_VALIDATED_MODELS:
            return [('CoreMLExecutionProvider',{'ModelFormat':'MLProgram','MLComputeUnits':'ALL'}),'CPUExecutionProvider']
        return ['CPUExecutionProvider']
    if policy=='cuda':
        if 'CUDAExecutionProvider' in available:
            return ['CUDAExecutionProvider','CPUExecutionProvider']
        return ['CPUExecutionProvider']
    if system=='darwin' and machine in ('arm64','aarch64'):
        if 'CoreMLExecutionProvider' in available and model in COREML_VALIDATED_MODELS:
            return [('CoreMLExecutionProvider',{'ModelFormat':'MLProgram','MLComputeUnits':'ALL'}),'CPUExecutionProvider']
        return ['CPUExecutionProvider']
    if 'CUDAExecutionProvider' in available:
        return ['CUDAExecutionProvider','CPUExecutionProvider']
    return ['CPUExecutionProvider']


def get_torch_device(policy=None):
    if policy is None:
        policy=os.environ.get('MANGA_ACCEL','auto')
    policy=str(policy).lower()
    if policy=='cpu':return 'cpu'
    try:
        import torch
        if policy in ('cuda','auto') and torch.cuda.is_available():
            return 'cuda'
    except Exception:pass
    return 'cpu'


def runtime_info():
    import onnxruntime as ort
    system=platform.system();machine=platform.machine();available=ort.get_available_providers();policy=os.environ.get('MANGA_ACCEL','auto').lower()
    return {'system':system,'machine':machine,'available_onnx_providers':available,'policy':policy,
            'selection_by_model':{m:select_providers(system,machine,available,m,policy) for m in ('balloon','text','ctd','head','lama','koharu')},
            'note':'Provider registration does not prove execution on GPU/ANE; individual nodes may fall back.'}


_CUDA_PRELOADED=False
def _preload_cuda_libs():
    global _CUDA_PRELOADED
    if _CUDA_PRELOADED:return
    _CUDA_PRELOADED=True
    try:
        import sys, glob, ctypes
        prefix=sys.prefix
        libs=glob.glob(os.path.join(prefix,'lib','python*','site-packages','nvidia','*','lib','*.so*'))
        for lib in sorted(libs):
            try:ctypes.CDLL(lib,mode=ctypes.RTLD_GLOBAL)
            except Exception:pass
    except Exception:pass


def create_session(ort, model_path, options, model):
    selected=select_providers(platform.system(),platform.machine(),ort.get_available_providers(),model,os.environ.get('MANGA_ACCEL','auto').lower())
    if any((p[0] if isinstance(p,tuple) else p)=='CUDAExecutionProvider' for p in selected):
        _preload_cuda_libs()
    if isinstance(selected[0],tuple) and selected[0][0]=='CoreMLExecutionProvider':
        digest=sha256_file(model_path)
        cache=Path.home()/'Library/Caches/MangaTypesetterLite/CoreML'/str(ort.__version__)/(platform.release()+'-'+platform.machine())/digest
        selected[0][1]['ModelCacheDirectory']=str(cache)
    try:
        result=ort.InferenceSession(str(model_path),sess_options=options,providers=selected)
        requested=selected[0][0] if isinstance(selected[0],tuple) else selected[0]
        if requested!='CPUExecutionProvider' and requested not in result.get_providers():
            LOG.warning('%s provider %s unavailable after initialization; CPU fallback',model,requested)
        SESSION_REPORTS[model]={'requested':requested,'registered':result.get_providers(),'fallback':requested not in result.get_providers()}
        return ResilientSession(result,ort,model_path,options,model,requested!='CPUExecutionProvider' and requested in result.get_providers())
    except Exception as exc:
        if selected==['CPUExecutionProvider']:raise
        LOG.warning('%s accelerated initialization failed; retrying on CPU',model,exc_info=True)
        result=ort.InferenceSession(str(model_path),sess_options=options,providers=['CPUExecutionProvider'])
        SESSION_REPORTS[model]={'requested':selected[0][0] if isinstance(selected[0],tuple) else selected[0],'registered':result.get_providers(),'fallback':True,'reason':str(exc)[:2048]}
        return result
