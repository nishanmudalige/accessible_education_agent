import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import ai_service
import app
from timing import usage

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(('limit', 'count', 'totals'), [
    (None, 12, 'input=370 output=61 total=431'),
    (1, 1, 'input=30 output=5 total=35'),
    (3, 3, 'input=90 output=15 total=105'),
])
@pytest.mark.parametrize('defer_web', [False, True])
def test_benchmark_mocked_end_to_end(monkeypatch, capsys, limit, count, totals, defer_web):
    spec = importlib.util.spec_from_file_location('benchmark_run', ROOT / 'benchmark/run.py')
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    monkeypatch.setitem(app.app.config, 'RATE_LIMIT', 100)
    monkeypatch.setitem(app.app.config, 'SKIP_PLAN', False)
    def plan(question, language, docs, history):
        usage(SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=2)), 'fake', 'plan')
        return {'related': 'weather' not in question, 'language': language, 'query_en': 'derivative', 'query_fr': 'dérivée', 'reason': ''}
    def answer(question, language, hits, history, docs):
        usage(SimpleNamespace(usage=SimpleNamespace(input_tokens=20, output_tokens=3)), 'fake', 'answer')
        return {'answer':'Derivative. [S1]', 'supported':True, 'evidence':['S1']}
    def web(*args):
        usage(SimpleNamespace(usage=SimpleNamespace(input_tokens=30, output_tokens=4)), 'fake', 'web')
        return {'text':'', 'citations':[], 'verified':False}
    monkeypatch.setattr(ai_service, 'plan', plan)
    monkeypatch.setattr(ai_service, 'answer', answer)
    monkeypatch.setattr(ai_service, 'web_search', web)
    args = ['run.py', '--interval', '0', '--cold-runs', '0', '--page-runs', '0']
    if limit is not None:
        args += ['--limit', str(limit)]
    if defer_web:
        args += ['--defer-web']
    monkeypatch.setattr(sys, 'argv', args)
    assert bench.main() == 0
    out = capsys.readouterr().out
    assert f'Planned /api/ask requests: {count}' in out
    assert totals in out
    assert out.count('Request en/') + out.count('Request fr/') == count
    assert 'failed requests=0' in out
    if defer_web and limit is None:
        assert 'Separate web request:' in out


def test_dry_run_does_not_call_app(monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location('benchmark_dry', ROOT / 'benchmark/run.py')
    bench = importlib.util.module_from_spec(spec); spec.loader.exec_module(bench)
    monkeypatch.setattr(sys, 'argv', ['run.py', '--dry-run'])
    assert bench.main() == 0
    assert 'requests: 12' in capsys.readouterr().out
    monkeypatch.setattr(sys, 'argv', ['run.py', '--dry-run', '--limit', '1'])
    assert bench.main() == 0
    assert 'requests: 1' in capsys.readouterr().out


def test_quality_logging_is_opt_in_and_records_hits(monkeypatch):
    import logging
    from timing import log
    records = []
    class Capture(logging.Handler):
        def emit(self, record):
            records.append(json.loads(record.getMessage().removeprefix('[TIMING] ')))
    handler = Capture()
    log.addHandler(handler)
    try:
        application = app.create_app({'TESTING': True, 'SECRET_KEY': 'test', 'RATE_LIMIT': 100, 'SKIP_PLAN': False})
        client = application.test_client()
        with client.session_transaction() as session:
            session['csrf'] = 'test-csrf'
        plan = {'related': True, 'language': 'en-CA', 'query_en': 'derivative', 'query_fr': 'dérivée', 'reason': ''}
        monkeypatch.setattr(ai_service, 'plan', lambda *args: plan)
        monkeypatch.setattr(ai_service, 'answer', lambda *args: {'answer': 'Answer. [S1]', 'supported': True, 'evidence': ['S1']})
        payload = {'question': 'What is a derivative?', 'doc': 'active-calculus-pdf', 'language': 'en-CA', 'web': False}
        def ask():
            return client.post('/api/ask', json=payload, headers={'X-CSRF-Token': 'test-csrf'})
        assert ask().status_code == 200
        assert not any(x.get('event') == 'plan_quality' for x in records)
        application.config['BENCHMARK_PLAN_QUALITY'] = True
        assert ask().status_code == 200
        event = next(x for x in records if x.get('event') == 'plan_quality')
        assert (event['related'], event['language'], event['query_en'], event['query_fr']) == (True, 'en-CA', 'derivative', 'dérivée')
        assert event['request_id'] and event['hits']
        assert all(set(hit) == {'doc', 'page', 'id'} for hit in event['hits'])
        plan['related'] = False
        assert ask().status_code == 200
        assert [x for x in records if x.get('event') == 'plan_quality'][-1]['hits'] == []
    finally:
        log.removeHandler(handler)


def test_reasoning_tokens_are_logged_when_available():
    import logging
    from timing import log
    events = []
    class Capture(logging.Handler):
        def emit(self, record):
            events.append(json.loads(record.getMessage().removeprefix('[TIMING] ')))
    handler = Capture()
    log.addHandler(handler)
    try:
        value = SimpleNamespace(input_tokens=10, output_tokens=7, output_tokens_details=SimpleNamespace(reasoning_tokens=4))
        usage(SimpleNamespace(usage=value), 'fake', 'search_plan')
        assert events[-1]['reasoning_tokens'] == 4
        usage(SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=7)), 'fake', 'search_plan')
        assert events[-1]['reasoning_tokens'] is None
    finally:
        log.removeHandler(handler)
