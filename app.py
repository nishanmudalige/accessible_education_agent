"""AccessÉdu — English / Canadian French accessibility demonstration."""
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path
import hmac
import io
import logging
import os
import re
import secrets
import threading
import time
from urllib.parse import urlencode
import fitz
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, send_file, session, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env', override=os.getenv('RENDER','').lower()!='true')
import ai_service as ai  # Load model overrides after .env.
from retrieval import LibraryIndex
from reader_backend import page_png, page_data, resolution
from timing import request_timing, stage, plan_quality
from planning import is_english

ASSET_FILENAME=r'[a-f0-9]{24}\.(?:svg|png|jpg|jpeg|gif|webp|avif)'

@lru_cache(maxsize=2)
def library(manifest=None):
    return LibraryIndex(manifest or BASE / 'content' / 'manifest.json')

def reader_url(p):
    if p.get('format')=='html':
        return f"/book/{p['doc']}/{p['chapter']}?"+urlencode({'hl':p['id']})
    return '/reader?' + urlencode({'doc':p['doc'],'page':p['page'],'ids':p['id']})

def answer_figures(selected, evidence):
    cited={p['key']:p for p in evidence if p.get('format')=='html'}
    figures=[]
    seen=set()
    used=0
    for key in selected:
        passage=cited.pop(key, None)
        if not passage:
            continue
        before=len(figures)
        for image in passage.get('images', []):
            url=image.get('local_url', '')
            if not image.get('available') or url in seen:
                continue
            if not re.fullmatch(r'/book-assets/'+re.escape(passage['doc'])+'/'+ASSET_FILENAME, url):
                continue
            seen.add(url)
            figures.append(dict(local_url=url, alt=image['alt'], key=key, url=reader_url(passage)))
        if len(figures)>before:
            used+=1
            if used==2:
                break
    return figures

def create_app(config=None, index_provider=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=48000,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('RENDER','').lower()=='true',
        AI_ENABLED=True, RATE_LIMIT=int(os.getenv('REQUESTS_PER_MINUTE','8')),
        WEB_SEARCH_DEFAULT=os.getenv('WEB_SEARCH_DEFAULT','off').lower()=='on',
        SKIP_PLAN=os.getenv('SKIP_PLAN','off').lower()=='on',
        SKIP_PLAN_MIN_SCORE=float(os.getenv('SKIP_PLAN_MIN_SCORE','1.0')),
        BENCHMARK_PLAN_QUALITY=False)
    if config:
        app.config.update(config)
    def get_library():
        return index_provider() if index_provider is not None else library()

    rate = defaultdict(deque)
    rate_lock = threading.Lock()
    web_tokens = URLSafeTimedSerializer(app.config['SECRET_KEY'], salt='related-web-search')

    def web_binding():
        return hmac.new(app.secret_key.encode(), session.get('csrf','').encode(), 'sha256').hexdigest()

    def csrf():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)
        return session['csrf']

    @app.context_processor
    def common():
        return {'csrf_token':csrf()}

    @app.before_request
    def access_control():
        if request.path == '/health' or request.path.startswith('/static/'):
            return
        if request.method == 'POST':
            sent = request.headers.get('X-CSRF-Token') or request.form.get('csrf','')
            if not session.get('csrf') or not hmac.compare_digest(sent.encode(),session['csrf'].encode()):
                return jsonify(error='Session expired. Reload the page and try again.'),403
        if request.path.startswith('/api/') and request.method == 'POST':
            if not app.config['AI_ENABLED']:
                return jsonify(error='AI requests are disabled.'),503
            # Direct peer address: do not trust arbitrary client-supplied X-Forwarded-For.
            peer = request.remote_addr or 'unknown'
            now = time.monotonic()
            with rate_lock:
                for old in [k for k,v in rate.items() if not v or now-v[-1]>60]:
                    del rate[old]
                bucket = rate[peer]
                while bucket and now-bucket[0]>60:
                    bucket.popleft()
                if len(bucket)>=app.config['RATE_LIMIT']:
                    return jsonify(error='Please wait a minute before another AI request.'),429
                bucket.append(now)

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
        response.headers['X-Frame-Options']='SAMEORIGIN'
        response.headers.setdefault('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'")
        if not request.path.startswith('/static/'):
            response.headers['Cache-Control']='no-store'
        return response

    @app.route('/login',methods=['GET','POST'])
    def login():
        return redirect('/')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect('/')

    @app.get('/health')
    def health():
        index=get_library()
        return jsonify(status='ok',documents=len(index.docs),pages=len(index.pages))

    @app.get('/')
    def home():
        return render_template('index.html',docs=get_library().public_docs(),
            answer_model=ai.ASTRA, search_model=ai.SOL,
            web_search_default=app.config['WEB_SEARCH_DEFAULT'])

    @app.get('/book-assets/<doc_id>/<filename>')
    def html_image(doc_id,filename):
        doc=get_library().docs.get(doc_id)
        if not doc or doc.get('format')!='html' or not re.fullmatch(ASSET_FILENAME,filename):
            abort(404)
        path=doc['path'].parent/'assets'/filename
        if not path.is_file(): abort(404)
        response=send_file(path,conditional=True)
        response.headers['Content-Security-Policy']="sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        return response

    @app.get('/book/<doc_id>/<chapter_id>')
    def html_chapter(doc_id,chapter_id):
        doc=get_library().docs.get(doc_id)
        if not doc or doc.get('format')!='html': abort(404)
        chapter=next((c for c in doc['chapters'] if c['id']==chapter_id),None)
        if chapter is None: abort(404)
        content=(doc['path'].parent/chapter['file']).read_text(encoding='utf-8')
        response=app.make_response(render_template('book.html',doc=doc,chapter=chapter,content=content))
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
        return response

    @app.get('/reader')
    def reader():
        index=get_library()
        doc_id=request.args.get('doc',next(iter(index.docs)))
        if doc_id not in index.docs: abort(404)
        if index.docs[doc_id].get('format')=='html':
            return redirect(index.docs[doc_id]['toc'][0]['url'])
        number=request.args.get('page',1,type=int)
        try: passages=index.page(doc_id,number)
        except KeyError: abort(404)
        ids=set(request.args.get('ids','').split(','))
        return render_template('reader.html',doc=index.docs[doc_id],doc_id=doc_id,
            docs=index.public_docs(),page=number,passages=passages,selected=ids,
            rects=[r for p in passages if p['id'] in ids for r in p['rects']])

    @app.get('/pdf/<doc_id>')
    def pdf(doc_id):
        doc=get_library().docs.get(doc_id)
        if not doc or doc.get('format','pdf')!='pdf': abort(404)
        return send_file(doc['path'],mimetype='application/pdf',conditional=True)

    @app.get('/page-image/<doc_id>/<int:number>')
    def image(doc_id,number):
        index=get_library()
        if (doc_id,number) not in index.pages or index.docs[doc_id].get('format','pdf')!='pdf': abort(404)
        try:scale=resolution(request.args.get('scale','2.5'))
        except ValueError:abort(400)
        data=page_png(str(index.docs[doc_id]['path']),number,scale,doc_id)
        return send_file(io.BytesIO(data),mimetype='image/png')

    @app.get('/api/reader/<doc_id>/<int:number>')
    def reader_page(doc_id,number):
        index=get_library()
        if (doc_id,number) not in index.pages:abort(404)
        ids=request.args.get('ids','').split(',')[:20]
        return jsonify(page_data(index,doc_id,number,ids,request.args.get('q','')[:200]))

    @app.get('/api/search')
    def local_search():
        q=request.args.get('q','')[:1500]
        doc_id=request.args.get('doc') or None
        if doc_id and doc_id not in get_library().docs: abort(404)
        results=[]
        for p in get_library().search(q,doc_id,12):
            results.append({**p,'title':get_library().docs[p['doc']]['title'],
                'language':get_library().docs[p['doc']].get('language','en-CA'),'url':reader_url(p)})
        return jsonify(results=results)

    def body():
        data=request.get_json(silent=True)
        if not isinstance(data,dict): abort(400,description='Expected a JSON object')
        return data

    def run_ai(fn):
        try: return fn()
        except Exception as e:
            # Do not log question text, passages, credentials or raw provider errors.
            logging.warning('AI request failed: %s',type(e).__name__)
            msg=ai.error_summary(e)
            return jsonify(error=msg),502

    @app.post('/api/ask')
    def ask():
        data=body()
        question=data.get('question','')
        if not isinstance(question,str) or not 1<=len(question.strip())<=3000:
            return jsonify(error='Enter a question of 1–3000 characters.'),400
        question=question.strip()
        language=data.get('language','auto')
        if language not in ('auto','en-CA','fr-CA'): return jsonify(error='Invalid language.'),400
        doc_id=data.get('doc') or None
        if doc_id and doc_id not in get_library().docs: return jsonify(error='Unknown document.'),400
        raw_history=data.get('history',[])
        if not isinstance(raw_history,list): raw_history=[]
        history=[{'role':h['role'],'content':h['content'][:2500]} for h in raw_history[-6:]
                 if isinstance(h,dict) and h.get('role') in ('user','assistant') and isinstance(h.get('content'),str)]
        docs=[d for d in get_library().public_docs() if not doc_id or d['id']==doc_id]
        skip_plan=app.config['SKIP_PLAN'] and language in ('auto','en-CA') and not raw_history and is_english(question)
        def outside(lang):
            return jsonify(category='out_of_scope',language=lang,book_answer='',evidence=[],figures=[],results=[],
                notice=('Cette demande ne concerne pas les sujets des documents sélectionnés. Essayez une question liée à ces sujets.' if lang=='fr-CA' else 'This request is outside the subjects of the selected documents. Try a question related to those subjects.'),web=None)
        def operation():
            if skip_plan:
                search_plan={'related':None,'language':'en-CA','query_en':question,'query_fr':''}
            else:
                with stage('plan'):
                    search_plan=ai.plan(question,language,docs,history)
            lang=language if language!='auto' else search_plan['language']
            if not skip_plan and not search_plan['related']:
                if app.config['BENCHMARK_PLAN_QUALITY']:
                    plan_quality(search_plan, [], plan_skipped=False)
                return outside(lang)
            query=question if skip_plan else question+' '+search_plan['query_en']+' '+search_plan['query_fr']
            with stage('retrieve'):
                hits=get_library().search(query,doc_id,10)
            # Explicit page requests are bound to a single chosen document, not guessed across books.
            top_score=hits[0]['score'] if hits else 0.0
            explicit_page=False
            match=re.search(r'\b(?:pdf\s*)?(?:page|p\.)\s*(\d{1,4})\b',question,re.I)
            if match and len(docs)==1 and docs[0].get('format','pdf')=='pdf':
                page=int(match.group(1))
                if (docs[0]['id'],page) in get_library().pages:
                    hits=get_library().page(docs[0]['id'],page)
                    explicit_page=True
            if skip_plan and not explicit_page and top_score < app.config['SKIP_PLAN_MIN_SCORE']:
                search_plan['related']=False
                if app.config['BENCHMARK_PLAN_QUALITY']:
                    plan_quality(search_plan, hits, plan_skipped=True, top_score=top_score, scope_source='bm25_gate')
                return outside(lang)
            offered=[{**p,'key':f'S{i+1}'} for i,p in enumerate(hits)]
            payload=[{k:p[k] for k in ('key','doc','page','id','text')} for p in offered]
            for fragment, passage in zip(payload, offered):
                if passage.get('format')=='html' and passage.get('images'):
                    fragment.update(has_figure=True, figure_alts=[i.get('alt','') for i in passage['images']])
            result={}
            if payload:
                with stage('answer'):
                    result=ai.answer(question,lang,payload,history,docs)
            if skip_plan:
                search_plan['related']=result.get('related')
            if app.config['BENCHMARK_PLAN_QUALITY']:
                plan_quality(search_plan, hits, plan_skipped=skip_plan, top_score=top_score,
                    scope_source='answer' if skip_plan else 'planner')
            if result.get('related') is False:
                return outside(lang)
            text,evidence=ai.validate_answer(result,offered)
            notice='' if text else ('Je ne peux pas confirmer la réponse à partir des passages trouvés. Cela ne signifie pas que le livre ne traite pas du sujet.' if lang=='fr-CA' else 'I could not verify an answer from the retrieved passages. This does not establish that the book omits the topic.')
            def present(p):
                return {**{k:v for k,v in p.items() if k!='rects'},'title':get_library().docs[p['doc']]['title'],
                    'language':get_library().docs[p['doc']].get('language','en-CA'),'url':reader_url(p)}
            web=None
            if data.get('web',app.config['WEB_SEARCH_DEFAULT']) is True:
                try:
                    with stage('web'):
                        web=ai.web_search(search_plan['query_en'],lang,'; '.join(d['subject'] for d in docs))
                except Exception as e:
                    logging.warning('External search unavailable: %s',type(e).__name__)
                    web={'text':'','citations':[],'verified':False,'error':True}
            return jsonify(category='book' if text else 'related_outside',language=lang,
                book_answer=text or '',notice=notice,evidence=[present(p) for p in evidence],
                results=[present(p) for p in offered],web=web,
                figures=answer_figures(result.get('figure_ids', []), evidence),
                web_token=web_tokens.dumps({'query':search_plan['query_en'], 'language':lang,
                    'docs':[d['id'] for d in docs], 'binding':web_binding()}))
        with request_timing(doc_id) as timing:
            timing['plan_skipped']=skip_plan
            return run_ai(operation)

    @app.post('/api/web-search')
    def related_web_search():
        token=body().get('token')
        if not isinstance(token,str) or not token:
            return jsonify(error='Missing web search request. Ask the question again.'),400
        try:
            saved=web_tokens.loads(token,max_age=900)
        except SignatureExpired:
            return jsonify(error='This web search request expired. Ask the question again.'),410
        except BadSignature:
            return jsonify(error='Invalid web search request. Ask the question again.'),403
        if not hmac.compare_digest(saved['binding'],web_binding()):
            return jsonify(error='This web search belongs to another session. Ask the question again.'),403
        docs=[get_library().docs.get(doc) for doc in saved['docs']]
        if not docs or any(d is None for d in docs):
            return jsonify(error='The document collection changed. Ask the question again.'),400
        def operation():
            with stage('web'):
                web=ai.web_search(saved['query'],saved['language'],'; '.join(d['subject'] for d in docs))
            return jsonify(web=web,language=saved['language'])
        with request_timing(','.join(saved['docs']),event='web_search'):
            return run_ai(operation)

    @app.post('/api/translate')
    def translate():
        data=body()
        text=data.get('text','')
        target=data.get('target','fr-CA')
        if not isinstance(text,str) or not 1<=len(text.strip())<=14000:
            return jsonify(error='Select 1–14000 characters; translate longer material one passage at a time.'),400
        if target not in ('en-CA','fr-CA'): return jsonify(error='Invalid translation language.'),400
        return run_ai(lambda:jsonify(text=ai.translation(text,target),language=target,
            notice='Unofficial AI translation / Traduction automatique non officielle. CC BY-SA 3.0 applies to adaptations of OpenIntro text.'))

    return app

app=create_app()
if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
