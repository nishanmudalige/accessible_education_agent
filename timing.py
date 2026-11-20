"""Request-local, privacy-preserving timing and token instrumentation."""
from contextlib import contextmanager
from contextvars import ContextVar
import json
import logging
import time
import uuid

current = ContextVar('timing_current', default=None)
log = logging.getLogger('benchmark.timing')
log.setLevel(logging.INFO)
log.propagate = False
log.addHandler(logging.StreamHandler())

def emit(**fields):
    log.info('[TIMING] %s', json.dumps(fields, ensure_ascii=False, sort_keys=True))

@contextmanager
def request_timing(book):
    data = {'event': 'ask', 'request_id': uuid.uuid4().hex, 'book': book or 'all',
            'plan': None, 'retrieve': None, 'answer': None, 'web': None,
            'tokens_in': 0, 'tokens_out': 0, 'usage_unknown': False}
    token = current.set(data)
    started = time.perf_counter()
    try:
        yield data
    finally:
        data['total'] = time.perf_counter() - started
        emit(**data)
        current.reset(token)

@contextmanager
def stage(name):
    started = time.perf_counter()
    try:
        yield
    except Exception:
        data = current.get()
        if data is not None and name in ('plan', 'answer', 'web'):
            data['usage_unknown'] = True
        raise
    finally:
        data = current.get()
        if data is not None:
            data[name] = time.perf_counter() - started

def usage(response, model, operation):
    value = getattr(response, 'usage', None)
    tokens_in = getattr(value, 'input_tokens', None)
    tokens_out = getattr(value, 'output_tokens', None)
    details = getattr(value, 'output_tokens_details', None)
    reasoning_tokens = getattr(details, 'reasoning_tokens', None)
    data = current.get()
    emit(event='model', request_id=data['request_id'] if data else None,
         book=data['book'] if data else None, model=model, operation=operation,
         tokens_in=tokens_in, tokens_out=tokens_out, reasoning_tokens=reasoning_tokens)
    if data is not None:
        if tokens_in is None or tokens_out is None:
            data['usage_unknown'] = True
        else:
            data['tokens_in'] += tokens_in
            data['tokens_out'] += tokens_out

def plan_quality(plan, hits):
    data = current.get()
    emit(event='plan_quality', request_id=data['request_id'] if data else None,
         book=data['book'] if data else None,
         related=plan['related'], language=plan['language'],
         query_en=plan['query_en'], query_fr=plan['query_fr'],
         hits=[{'doc': p['doc'], 'page': p['page'], 'id': p['id']} for p in hits])
