from pathlib import Path
from types import SimpleNamespace as NS
import json
import re
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as module
import ai_service as ai
from retrieval import LibraryIndex

@pytest.fixture
def client():
    app=module.create_app({'TESTING':True,'SECRET_KEY':'test-secret','APP_PASSWORD':'test-password','RATE_LIMIT':100})
    c=app.test_client()
    with c.session_transaction() as s:s['authenticated']=True;s['csrf']='test-csrf'
    return c

def post(c,path,data):return c.post(path,json=data,headers={'X-CSRF-Token':'test-csrf'})

def fake_ai(monkeypatch,related=True,supported=True,bad_key=False):
    calls=[]
    monkeypatch.setattr(ai,'plan',lambda *args:dict(related=related,language='fr-CA',query_en='confidence interval',query_fr='intervalle de confiance',reason=''))
    def answer(q,lang,hits,history):
        calls.append(hits)
        return {'supported':supported,'answer':'Un intervalle de confiance. [S999]' if bad_key else 'Un intervalle de confiance. [S1]', 'evidence':['S999' if bad_key else 'S1']}
    monkeypatch.setattr(ai,'answer',answer)
    monkeypatch.setattr(ai,'web_search',lambda *args:dict(text='External example',citations=[dict(start=0,end=8,url='https://www.openintro.org/',title='OpenIntro')],verified=True))
    return calls

def test_full_pdf_and_french_retrieval():
    index=module.library()
    assert index.docs['openintro-statistics-4e']['page_count']==422
    assert len(index.docs['openintro-statistics-4e']['toc'])==12
    for q,term in [('intervalle de confiance','confidence'),('écart-type','standard'),('loi de poisson','poisson')]:
        hits=index.search(q,limit=6)
        assert any(term in p['text'].lower() for p in hits)

def test_reader_citation_and_image_share_exact_block(client):
    p=module.library().search('confidence interval',limit=1)[0]
    html=client.get(module.reader_url(p)).get_data(as_text=True)
    assert f'id="{p["id"]}" class="source-block evidence"' in html
    assert 'overlay-mark' in html
    image=client.get(f'/page-image/{p["doc"]}/{p["page"]}')
    assert image.status_code==200 and image.mimetype=='image/png'

def test_invalid_pages_and_paths(client):
    assert client.get('/reader?page=9999').status_code==404
    assert client.get('/reader?doc=unknown').status_code==404
    assert client.get('/page-image/unknown/1').status_code==404
    assert client.get('/api/search?q=mean&doc=unknown').status_code==404

def test_login_protects_pdf_and_api():
    a=module.create_app({'TESTING':True,'SECRET_KEY':'x','APP_PASSWORD':'secret'})
    c=a.test_client()
    assert c.get('/').status_code==302
    assert c.get('/pdf/openintro-statistics-4e').status_code==302
    assert c.get('/api/search?q=mean').status_code==401
    assert c.get('/health').json['pages']>=422
    html=c.get('/login').get_data(as_text=True)
    csrf=re.search(r'name="csrf" value="([^"]+)"',html).group(1)
    assert c.post('/login',data={'csrf':csrf,'password':'wrong'}).status_code==200
    assert c.post('/login',data={'csrf':csrf,'password':'secret'}).status_code==302
    assert c.get('/').status_code==200

def test_csrf_and_validation(client):
    assert client.post('/api/ask',json={'question':'hello'}).status_code==403
    assert post(client,'/api/ask',{'question':''}).status_code==400
    assert post(client,'/api/translate',{'text':'abc','target':'fi'}).status_code==400
    assert post(client,'/api/translate',{'text':'x'*14001}).status_code==400

def test_no_password_blocks_spend_but_not_local_reading():
    a=module.create_app({'TESTING':True,'SECRET_KEY':'x','APP_PASSWORD':''})
    c=a.test_client();c.get('/')
    with c.session_transaction() as s:token=s['csrf']
    assert c.get('/api/search?q=normal').status_code==200
    assert c.post('/api/ask',json={'question':'normal'},headers={'X-CSRF-Token':token}).status_code==503

def test_out_of_scope_does_not_answer_or_search_web(client,monkeypatch):
    calls=fake_ai(monkeypatch,related=False)
    monkeypatch.setattr(ai,'web_search',lambda *a:pytest.fail('No web search for unrelated request'))
    r=post(client,'/api/ask',{'question':'Suggest a beach vacation','web':True}).json
    assert r['category']=='out_of_scope' and r['web'] is None and not calls

def test_book_answer_evidence_links_and_separate_web(client,monkeypatch):
    fake_ai(monkeypatch)
    r=post(client,'/api/ask',{'question':'Expliquez un intervalle de confiance','web':True}).json
    assert r['category']=='book' and r['language']=='fr-CA'
    assert r['evidence'][0]['key']=='S1'
    assert 'ids=p' in r['evidence'][0]['url']
    assert r['web']['verified'] is True and 'External' not in r['book_answer']

def test_bad_citation_rejected_and_no_web_when_disabled(client,monkeypatch):
    fake_ai(monkeypatch,bad_key=True)
    monkeypatch.setattr(ai,'web_search',lambda *a:pytest.fail('Web explicitly disabled'))
    r=post(client,'/api/ask',{'question':'confidence interval','web':False}).json
    assert r['category']=='related_outside' and r['book_answer']=='' and r['evidence']==[]

def test_external_failure_preserves_book(client,monkeypatch):
    fake_ai(monkeypatch)
    def fail(*args):raise RuntimeError('private provider details')
    monkeypatch.setattr(ai,'web_search',fail)
    r=post(client,'/api/ask',{'question':'confidence interval'}).json
    assert r['book_answer'] and r['web']['error'] and 'private' not in str(r)

def test_translation_language_and_output(client,monkeypatch):
    seen=[]
    monkeypatch.setattr(ai,'translation',lambda text,target:seen.append((text,target)) or 'Écart-type')
    r=post(client,'/api/translate',{'text':'Standard deviation','target':'fr-CA'})
    assert r.json['text']=='Écart-type' and seen==[('Standard deviation','fr-CA')]

def test_multidocument_index_and_path_boundary(tmp_path):
    import fitz
    for name,text in [('one','Statistics explores probability, sampling and confidence intervals.'),('two','Biology explores photosynthesis, chlorophyll and plants.')]:
        pdf=fitz.open();page=pdf.new_page();page.insert_text((72,72),text);pdf.save(tmp_path/(name+'.pdf'));pdf.close()
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'documents':[{'id':n,'file':n+'.pdf','title':n,'subject':n} for n in ['one','two']]}))
    index=LibraryIndex(manifest)
    assert index.search('chlorophyll')[0]['doc']=='two'
    assert not index.search('chlorophyll',doc_id='one')
    manifest.write_text(json.dumps({'documents':[{'id':'bad','file':'../escape.pdf'}]}))
    with pytest.raises(ValueError):LibraryIndex(manifest)

def test_responses_contract_and_exact_model_names(monkeypatch):
    calls=[]
    class Responses:
        def create(self,**kwargs):
            calls.append(kwargs)
            return NS(status='completed',output_text='{"related":true,"language":"fr-CA","query_en":"mean","query_fr":"moyenne","reason":""}')
    monkeypatch.setattr(ai,'client',lambda:NS(responses=Responses()))
    ai.plan('moyenne','fr-CA',[],[])
    assert calls[0]['model']=='gpt-6.1-sol'
    assert calls[0]['store'] is False and calls[0]['text']['format']['strict']
    assert calls[0]['reasoning']['effort']=='low'

def test_web_requires_real_search_and_safe_citations(monkeypatch):
    response=NS(status='completed',output=[NS(type='message',content=[NS(type='output_text',text='Invented answer',annotations=[])])])
    class Responses:
        def create(self,**kw):
            assert kw['tool_choice']=='required' and kw['tools']==[{'type':'web_search'}]
            return response
    monkeypatch.setattr(ai,'client',lambda:NS(responses=Responses()))
    assert ai.web_search('q','en-CA','statistics')['verified'] is False
    assert not ai.safe_url('javascript:alert(1)')
    assert not ai.safe_url('file:///etc/passwd')
    assert ai.safe_url('https://www.openintro.org/')

def test_unsupported_provider_error_is_sanitized(client,monkeypatch):
    def fail(*a):raise ValueError('secret must not appear')
    monkeypatch.setattr(ai,'plan',fail)
    r=post(client,'/api/ask',{'question':'mean'})
    assert r.status_code==502 and 'secret' not in r.json['error']

def test_ai_rate_limit(monkeypatch):
    a=module.create_app({'TESTING':True,'SECRET_KEY':'x','APP_PASSWORD':'secret','RATE_LIMIT':1})
    c=a.test_client()
    with c.session_transaction() as s:s['authenticated']=True;s['csrf']='test-csrf'
    fake_ai(monkeypatch,related=False)
    assert post(c,'/api/ask',{'question':'vacation'}).status_code==200
    assert post(c,'/api/ask',{'question':'vacation'}).status_code==429

@pytest.mark.parametrize('status,code,expected',[
    (401,'invalid_api_key','authentication failed'),
    (403,'insufficient_permissions','denied this request'),
    (404,'model_not_found','requested model'),
    (429,'insufficient_quota','quota or rate limit')])
def test_precise_local_provider_errors(client,monkeypatch,status,code,expected):
    monkeypatch.delenv('RENDER',raising=False)
    class Failure(Exception):pass
    error=Failure('sk-do-not-print-this-key')
    error.status_code=status
    error.body={'code':code,'message':'secret provider details'}
    def fail(*args):raise error
    monkeypatch.setattr(ai,'plan',fail)
    r=post(client,'/api/ask',{'question':'sample mean'})
    message=r.json['error']
    assert expected in message and code in message
    assert 'Render' not in message and 'secret' not in message and 'sk-' not in message

def test_render_provider_error_location(monkeypatch):
    monkeypatch.setenv('RENDER','true')
    error=Exception('private');error.status_code=401
    assert 'Render Environment' in ai.error_summary(error)

def test_local_diagnostic_prefers_dotenv_without_printing_key(tmp_path,monkeypatch,capsys):
    import importlib.util
    spec=importlib.util.spec_from_file_location('access_diagnose',Path(__file__).resolve().parents[1]/'scripts/diagnose_openai.py')
    diagnostic=importlib.util.module_from_spec(spec);spec.loader.exec_module(diagnostic)
    monkeypatch.setattr(diagnostic,'ROOT',tmp_path)
    monkeypatch.setattr(sys,'argv',['diagnose_openai.py'])
    monkeypatch.delenv('RENDER',raising=False)
    monkeypatch.setenv('OPENAI_API_KEY','sk-old-exported-example')
    (tmp_path/'.env').write_text('OPENAI_API_KEY=sk-local-file-example\n')
    assert diagnostic.main()==0
    import os
    assert os.getenv('OPENAI_API_KEY')=='sk-local-file-example'
    text=capsys.readouterr().out
    assert 'differs from .env' in text and 'No API request made' in text
    assert 'sk-old' not in text and 'sk-local' not in text
