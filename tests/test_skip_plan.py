"""Planning fast path, conservative local language detection and scope handling."""
import json
import logging
from types import SimpleNamespace as NS
import pytest
import ai_service as ai
import app as module
from planning import is_english
from timing import log

@pytest.mark.parametrize('question', [
    'What is a derivative?', 'How do I find the area under a curve?',
    'What does the chain rule say?', 'What is the weather today?', 'Explain PDF page 12.'
])
def test_local_english(question):
    assert is_english(question)

@pytest.mark.parametrize('question', [
    'Qu’est-ce qu’une dérivée ?', 'Comment trouver la surface sous une courbe?',
    'Quelle est la regle de derivation en chaine?', 'Expliquez une derivee',
    'What is une dérivée?', 'derivation', '这个是什么？'
])
def test_ambiguous_or_french_keeps_planner(question):
    assert not is_english(question)

@pytest.fixture
def setup(monkeypatch):
    index=module.library(module.BASE/'content/manifest.benchmark.json')
    monkeypatch.setattr(module,'library',lambda manifest=None:index)
    application=module.create_app({'TESTING':True,'SECRET_KEY':'skip','RATE_LIMIT':100,'SKIP_PLAN':True})
    client=application.test_client()
    with client.session_transaction() as s: s['csrf']='skip-csrf'
    calls=[]
    def plan(*args):
        calls.append(('plan',args))
        return {'related':True,'language':'fr-CA','query_en':'derivative','query_fr':'dérivée'}
    def answer(*args):
        calls.append(('answer',args))
        return {'related':True,'supported':True,'answer':'Answer. [S1]','evidence':['S1']}
    monkeypatch.setattr(ai,'plan',plan)
    monkeypatch.setattr(ai,'answer',answer)
    monkeypatch.setattr(ai,'web_search',lambda *args: pytest.fail('Web should be off'))
    return application,client,calls

def ask(client,**extra):
    return client.post('/api/ask',json={'question':'What is a derivative?','doc':'active-calculus-pdf','language':'en-CA','web':False,**extra},headers={'X-CSRF-Token':'skip-csrf'})

@pytest.mark.parametrize('language',['en-CA','auto'])
def test_fast_path_uses_raw_question_and_one_model(setup,monkeypatch,language):
    _,client,calls=setup
    index=module.library(); original=index.search; queries=[]
    def search(query,*args):
        queries.append(query)
        return original(query,*args)
    monkeypatch.setattr(index,'search',search)
    result=ask(client,language=language)
    assert result.status_code==200 and result.json['category']=='book'
    assert result.json['language']=='en-CA'
    assert queries==['What is a derivative?']
    assert [c[0] for c in calls]==['answer']
    assert calls[0][1][4][0]['id']=='active-calculus-pdf'

@pytest.mark.parametrize('extra',[
    {'question':'Qu’est-ce qu’une dérivée ?'}, {'language':'fr-CA'},
    {'history':[{'role':'user','content':'Tell me about derivatives.'}]},
])
def test_french_reply_and_history_keep_planner(setup,extra):
    _,client,calls=setup
    assert ask(client,**extra).status_code==200
    assert [c[0] for c in calls]==['plan','answer']

def test_switch_off(setup):
    application,client,calls=setup
    application.config['SKIP_PLAN']=False
    assert ask(client).status_code==200
    assert [c[0] for c in calls]==['plan','answer']

def test_defaults_from_environment(monkeypatch):
    monkeypatch.delenv('SKIP_PLAN',raising=False)
    assert module.create_app().config['SKIP_PLAN'] is False
    monkeypatch.setenv('SKIP_PLAN','on')
    assert module.create_app().config['SKIP_PLAN'] is True
    monkeypatch.setenv('SKIP_PLAN','off')
    assert module.create_app().config['SKIP_PLAN'] is False

@pytest.mark.parametrize('score',[None,0.2,0.999])
def test_low_score_returns_original_unrelated_shape_without_models(setup,monkeypatch,score):
    _,client,calls=setup
    monkeypatch.setattr(module.library(),'search',lambda *a: [] if score is None else [
        {'doc':'active-calculus-pdf','page':1,'id':'p0','text':'Not enough match','score':score}])
    result=ask(client)
    assert result.json['category']=='out_of_scope'
    assert result.json['web'] is None and not result.json.get('web_token')
    assert not calls

def test_unrelated_with_high_score_is_classified_by_answer(setup,monkeypatch):
    _,client,calls=setup
    def answer(*args):
        calls.append(('answer',args))
        return {'related':False,'supported':False,'answer':'','evidence':[]}
    monkeypatch.setattr(ai,'answer',answer)
    result=ask(client,question='What is the weather today?')
    assert result.json['category']=='out_of_scope' and result.json['web'] is None
    assert not result.json.get('web_token') and [c[0] for c in calls]==['answer']

def test_related_but_unsupported_preserves_web_offer(setup,monkeypatch):
    _,client,_=setup
    monkeypatch.setattr(ai,'answer',lambda *a: {'related':True,'supported':False,'answer':'','evidence':[]})
    result=ask(client).json
    assert result['category']=='related_outside' and result['web_token']

def test_explicit_page_does_not_fail_lexical_gate(setup,monkeypatch):
    _,client,calls=setup
    monkeypatch.setattr(module.library(),'search',lambda *a: [])
    assert ask(client,question='Explain PDF page 12.').json['category']=='book'
    assert [c[0] for c in calls]==['answer']

def test_quality_log_marks_skip_and_scope_source(setup):
    application,client,_=setup
    application.config['BENCHMARK_PLAN_QUALITY']=True
    events=[]
    class Capture(logging.Handler):
        def emit(self,record): events.append(json.loads(record.getMessage().removeprefix('[TIMING] ')))
    handler=Capture();log.addHandler(handler)
    try:
        assert ask(client).status_code==200
        quality=next(e for e in events if e['event']=='plan_quality')
        assert quality['plan_skipped'] and quality['scope_source']=='answer'
        assert quality['related'] is True and quality['query_en']=='What is a derivative?' and quality['query_fr']==''
        summary=next(e for e in events if e['event']=='ask')
        assert summary['plan_skipped'] and summary['plan'] is None
    finally: log.removeHandler(handler)

def test_answer_schema_and_subject_context(monkeypatch):
    requests=[]
    def create(**kwargs):
        requests.append(kwargs)
        return NS(status='completed',output_text='{"related":false,"supported":false,"answer":"","evidence":[]}')
    monkeypatch.setattr(ai,'client',lambda: NS(responses=NS(create=create)))
    ai.answer('weather','en-CA',[],[],[{'id':'book','title':'Calculus','subject':'calculus','language':'en-CA','toc':['unused']}])
    request=requests[0]
    assert 'related' in request['text']['format']['schema']['required']
    assert json.loads(request['input'])['subjects']==[{'id':'book','title':'Calculus','subject':'calculus','language':'en-CA'}]

@pytest.mark.parametrize('setting,expected',[('on',['answer']),('off',['plan','answer'])])
def test_benchmark_switch(setup,monkeypatch,capsys,setting,expected):
    import importlib.util
    import sys
    from pathlib import Path
    application,_,calls=setup
    monkeypatch.setattr(module,'app',application)
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('skip_bench',root/'benchmark/run.py')
    bench=importlib.util.module_from_spec(spec);spec.loader.exec_module(bench)
    monkeypatch.setattr(sys,'argv',['run.py','--questions',str(root/'benchmark/questions_plan.json'),'--skip-plan',setting,'--limit','1','--interval','0','--cold-runs','0','--page-runs','0'])
    assert bench.main()==0
    assert [c[0] for c in calls]==expected
    assert 'requests: 1' in capsys.readouterr().out
