"""On-demand search reuses trusted planning results and existing API protections."""
import re
import app as module
import ai_service as ai
import pytest

@pytest.fixture
def setup(monkeypatch):
    application=module.create_app({'TESTING':True,'SECRET_KEY':'web-tests','RATE_LIMIT':100})
    client=application.test_client()
    with client.session_transaction() as session: session['csrf']='web-csrf'
    calls=[]
    monkeypatch.setattr(ai,'plan',lambda *a: {'related':True,'language':'en-CA','query_en':'derivative calculus','query_fr':'dérivée'})
    monkeypatch.setattr(ai,'answer',lambda *a: {'supported':True,'answer':'Answer. [S1]','evidence':['S1']})
    monkeypatch.setattr(ai,'web_search',lambda *a: calls.append(a) or {'verified':True,'text':'External','citations':[]})
    return application,client,calls

def post(client,path,data):
    return client.post(path,json=data,headers={'X-CSRF-Token':'web-csrf'})

def ask(client,**extra):
    return post(client,'/api/ask',{'question':'What is a derivative?','doc':'active-calculus-pdf',**extra})

def test_default_off_and_optional_on(setup):
    application,client,calls=setup
    html=client.get('/').get_data(as_text=True)
    assert 'checked' not in re.search(r'<input id="web"[^>]*>',html).group()
    result=ask(client).json
    assert result['web'] is None and result['web_token'] and not calls
    application.config['WEB_SEARCH_DEFAULT']=True
    assert 'checked' in re.search(r'<input id="web"[^>]*>',client.get('/').get_data(as_text=True)).group()
    assert ask(client).json['web']['verified'] and len(calls)==1
    assert ask(client,web=False).json['web'] is None and len(calls)==1

def test_environment_default(monkeypatch):
    monkeypatch.setenv('WEB_SEARCH_DEFAULT','on')
    assert module.create_app().config['WEB_SEARCH_DEFAULT'] is True
    monkeypatch.setenv('WEB_SEARCH_DEFAULT','off')
    assert module.create_app().config['WEB_SEARCH_DEFAULT'] is False

def test_on_demand_reuses_query_without_planning(setup,monkeypatch):
    _,client,calls=setup
    token=ask(client).json['web_token']
    monkeypatch.setattr(ai,'plan',lambda *a: pytest.fail('Must not plan twice'))
    result=post(client,'/api/web-search',{'token':token,'query':'ignored','docs':['other']})
    assert result.status_code==200 and result.json['web']['verified']
    assert calls[0][0:2]==('derivative calculus','en-CA')
    assert 'calculus' in calls[0][2].lower() and len(calls)==1

def test_unrelated_has_no_search_token(setup,monkeypatch):
    _,client,calls=setup
    monkeypatch.setattr(ai,'plan',lambda *a: {'related':False,'language':'en-CA','query_en':'weather','query_fr':'météo'})
    result=ask(client).json
    assert result['category']=='out_of_scope' and not result.get('web_token') and not calls

def test_unsupported_answer_still_offers_search(setup,monkeypatch):
    _,client,calls=setup
    monkeypatch.setattr(ai,'answer',lambda *a: {'supported':False,'answer':'','evidence':[]})
    result=ask(client).json
    assert result['category']=='related_outside' and result['web_token'] and not calls

def test_token_validation_csrf_and_expiry(setup,monkeypatch):
    application,client,calls=setup
    token=ask(client).json['web_token']
    assert post(client,'/api/web-search',{}).status_code==400
    assert post(client,'/api/web-search',{'token':token+'x'}).status_code==403
    assert client.post('/api/web-search',json={'token':token}).status_code==403
    other=application.test_client()
    with other.session_transaction() as session: session['csrf']='web-csrf-other'
    assert other.post('/api/web-search',json={'token':token},headers={'X-CSRF-Token':'web-csrf-other'}).status_code==403
    import time
    now=time.time()
    monkeypatch.setattr(time,'time',lambda:now+901)
    assert post(client,'/api/web-search',{'token':token}).status_code==410
    assert not calls

def test_web_failure_is_sanitized_and_rate_limited(setup,monkeypatch):
    application,client,_=setup
    token=ask(client).json['web_token']
    def fail(*args): raise ValueError('secret provider text')
    monkeypatch.setattr(ai,'web_search',fail)
    response=post(client,'/api/web-search',{'token':token})
    assert response.status_code==502 and 'secret' not in response.json['error']
    application.config['RATE_LIMIT']=2
    assert post(client,'/api/web-search',{'token':token}).status_code==429

def test_no_retrieved_blocks_still_offers_search(setup,monkeypatch):
    _,client,calls=setup
    monkeypatch.setattr(module.library(),'search',lambda *a: [])
    monkeypatch.setattr(ai,'answer',lambda *a: pytest.fail('No answer without evidence'))
    result=ask(client).json
    assert result['results']==[] and result['category']=='related_outside'
    assert result['web_token'] and not calls

def test_browser_web_interactions():
    import shutil
    import subprocess
    from pathlib import Path
    node=shutil.which('node')
    if not node: pytest.skip('Node.js is needed for the browser interaction fixture')
    subprocess.run([node,'tests/web_ui.cjs'],cwd=Path(__file__).resolve().parents[1],check=True)
