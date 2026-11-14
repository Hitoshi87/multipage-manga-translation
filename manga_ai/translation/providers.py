"""Explicit registry of translation transports; no dynamic code discovery."""
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderResponseError(ValueError):
    def __init__(self, message, metadata):
        super().__init__(message)
        self.metadata = metadata


def key_file(name):
    """Per-user key file written by the Photoshop panel: ~/.manga_typesetter/<NAME>.key"""
    return Path.home() / '.manga_typesetter' / (str(name) + '.key')


def find_key(name):
    """API key from the environment first, then the user's key file; (key, source) or (None, None)."""
    value = os.environ.get(name)
    if value:
        return value, 'env'
    try:
        file = key_file(name)
        if file.is_file():
            text = file.read_text(encoding='utf8').strip()
            if text:
                return text, 'file'
    except OSError:
        pass
    return None, None


def key_status(name):
    """Whether a key is available and from where; never returns the key itself."""
    value, source = find_key(name)
    return {'present': bool(value), 'source': source, 'file': str(key_file(name))}


def openai_compatible(profile, system, payload):
    key, _source = find_key(profile['key_env'])
    if not key:
        raise ValueError('Chưa có API key trong biến môi trường ' + profile['key_env'])
    content=json.dumps(payload,ensure_ascii=False)
    images=profile.get('_vision_images') or []
    if images:content=[{'type':'text','text':content}]+images
    body = {'model':profile['model'], 'messages':[{'role':'system','content':system},
            {'role':'user','content':content}], 'max_tokens':int(profile['max_tokens'])}
    if profile['json_mode']:
        body['response_format'] = {'type':'json_object'}
    temperature = profile.get('temperature', 0.2)  # low: the same name must come out the same on every run; None omits it
    if temperature is not None:
        body['temperature'] = float(temperature)
    if profile['thinking'] != 'default':
        body['thinking'] = {'type':profile['thinking']}
    request = Request(profile['base_url'].rstrip('/') + '/chat/completions',
                      data=json.dumps(body,ensure_ascii=False).encode(),
                      headers={'Content-Type':'application/json','Authorization':'Bearer '+key}, method='POST')
    started = time.monotonic()
    deadline = started + 160  # Photoshop bridge waits 180 seconds per RPC.
    for attempt in range(int(profile['retries']) + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError('Đã hết thời gian thử API; tiếp tục nhóm sau')
        try:
            with urlopen(request, timeout=min(int(profile['timeout']), max(1,remaining))) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError('Response API vượt giới hạn 8 MiB')
            try:
                result = json.loads(raw)
                choice = result['choices'][0]
            except (ValueError, KeyError, IndexError, TypeError):
                # A gateway can answer 200 with an error object or a truncated body.
                # Treat it as transient: retry, then report a readable message.
                detail = ''
                try:
                    err = json.loads(raw).get('error')
                    detail = ': ' + (err.get('message') if isinstance(err, dict) else str(err))[:120]
                except (ValueError, AttributeError, TypeError):
                    pass
                if attempt == int(profile['retries']):
                    raise ValueError('API trả dữ liệu không hợp lệ' + detail) from None
                choice = None
            if choice is None:
                delay = min(2 ** attempt, 4, max(0, deadline - time.monotonic()))
                if delay:
                    time.sleep(delay)
                continue
            # Some gateways return an outage notice as assistant content with
            # HTTP 200 and finish_reason=stop. It is not a translation failure.
            content = choice.get('message', {}).get('content')
            if isinstance(content, str) and content.strip().lower() == 'upstream temporarily unavailable, please retry.':
                raise ValueError('API upstream temporarily unavailable')
            meta = {'model_returned':result.get('model'), 'usage':result.get('usage'),
                    'latency_ms':round((time.monotonic()-started)*1000),
                    'finish_reason':choice.get('finish_reason')}
            if choice.get('finish_reason') != 'stop':
                raise ProviderResponseError('API trả kết quả chưa hoàn tất', meta)
            return choice['message']['content'], meta
        except HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                raise ValueError('API HTTP ' + str(exc.code)) from None
            if attempt == int(profile['retries']):
                raise ValueError('API tạm thời lỗi HTTP ' + str(exc.code)) from None
        except (URLError, TimeoutError) as exc:
            if attempt == int(profile['retries']):
                raise ValueError('Không kết nối được API') from None
        if attempt < int(profile['retries']):
            delay = min(2 ** attempt, 4, max(0,deadline-time.monotonic()))
            if delay:time.sleep(delay)
    raise ValueError('API không phản hồi')



PROVIDERS = {'openai_compatible': openai_compatible}


def call(profile, system, payload):
    name=profile.get('provider_kind', 'openai_compatible')
    if name not in PROVIDERS:raise ValueError('Provider không được hỗ trợ: '+str(name))
    return PROVIDERS[name](profile, system, payload)
