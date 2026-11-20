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

BASE = Path(__file__).resolve().parent
load_dotenv(BASE / '.env', override=os.getenv('RENDER','').lower()!='true')
import ai_service as ai  # Load model overrides after .env.
from retrieval import LibraryIndex
from reader_backend import page_png, page_data, resolution
from timing import request_timing, stage, plan_quality

@lru_cache(maxsize=1)
def library():
    return LibraryIndex(BASE / 'content' / 'manifest.json')

def reader_url(p):
    return '/reader?' + urlencode({'doc':p['doc'],'page':p['page'],'ids':p['id']})

def create_app(config=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv('SECRET_KEY') or secrets.token_hex(32),
        MAX_CONTENT_LENGTH=48000,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=os.getenv('RENDER','').lower()=='true',
        AI_ENABLED=True, RATE_LIMIT=int(os.getenv('REQUESTS_PER_MINUTE','8')),
        BENCHMARK_PLAN_QUALITY=False)
    if config:
        app.config.update(config)
    rate = defaultdict(deque)
    rate_lock = threading.Lock()

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
        response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'"
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
        index=library()
        return jsonify(status='ok',documents=len(index.docs),pages=len(index.pages))

    @app.get('/')
    def home():
        return render_template('index.html',docs=library().public_docs(),
            answer_model=ai.ASTRA, search_model=ai.SOL)

    @app.get('/reader')
    def reader():
        index=library()
        doc_id=request.args.get('doc',next(iter(index.docs)))
        if doc_id not in index.docs: abort(404)
        number=request.args.get('page',1,type=int)
        try: passages=index.page(doc_id,number)
        except KeyError: abort(404)
        ids=set(request.args.get('ids','').split(','))
        return render_template('reader.html',doc=index.docs[doc_id],doc_id=doc_id,
            docs=index.public_docs(),page=number,passages=passages,selected=ids,
            rects=[r for p in passages if p['id'] in ids for r in p['rects']])

    @app.get('/pdf/<doc_id>')
    def pdf(doc_id):
        doc=library().docs.get(doc_id)
        if not doc: abort(404)
        return send_file(doc['path'],mimetype='application/pdf',conditional=True)

    @app.get('/page-image/<doc_id>/<int:number>')
    def image(doc_id,number):
        index=library()
        if (doc_id,number) not in index.pages: abort(404)
        try:scale=resolution(request.args.get('scale','2.5'))
        except ValueError:abort(400)
        data=page_png(str(index.docs[doc_id]['path']),number,scale,doc_id)
        return send_file(io.BytesIO(data),mimetype='image/png')

    @app.get('/api/reader/<doc_id>/<int:number>')
    def reader_page(doc_id,number):
        index=library()
        if (doc_id,number) not in index.pages:abort(404)
        ids=request.args.get('ids','').split(',')[:20]
        return jsonify(page_data(index,doc_id,number,ids,request.args.get('q','')[:200]))

    @app.get('/api/search')
    def local_search():
        q=request.args.get('q','')[:1500]
        doc_id=request.args.get('doc') or None
        if doc_id and doc_id not in library().docs: abort(404)
        results=[]
        for p in library().search(q,doc_id,12):
            results.append({**p,'title':library().docs[p['doc']]['title'],
                'language':library().docs[p['doc']].get('language','en-CA'),'url':reader_url(p)})
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
        if doc_id and doc_id not in library().docs: return jsonify(error='Unknown document.'),400
        raw_history=data.get('history',[])
        if not isinstance(raw_history,list): raw_history=[]
        history=[{'role':h['role'],'content':h['content'][:2500]} for h in raw_history[-6:]
                 if isinstance(h,dict) and h.get('role') in ('user','assistant') and isinstance(h.get('content'),str)]
        docs=[d for d in library().public_docs() if not doc_id or d['id']==doc_id]
        def operation():
            with stage('plan'):
                search_plan=ai.plan(question,language,docs,history)
            lang=language if language!='auto' else search_plan['language']
            if not search_plan['related']:
                if app.config['BENCHMARK_PLAN_QUALITY']:
                    plan_quality(search_plan, [])
                return jsonify(category='out_of_scope',language=lang,book_answer='',evidence=[],results=[],
                    notice=('Cette demande ne concerne pas les sujets des documents sélectionnés. Essayez une question liée à ces sujets.' if lang=='fr-CA' else 'This request is outside the subjects of the selected documents. Try a question related to those subjects.'),web=None)
            query=question+' '+search_plan['query_en']+' '+search_plan['query_fr']
            with stage('retrieve'):
                hits=library().search(query,doc_id,10)
            # Explicit page requests are bound to a single chosen document, not guessed across books.
            match=re.search(r'\b(?:pdf\s*)?(?:page|p\.)\s*(\d{1,4})\b',question,re.I)
            if match and len(docs)==1:
                page=int(match.group(1))
                if (docs[0]['id'],page) in library().pages:
                    hits=library().page(docs[0]['id'],page)
            if app.config['BENCHMARK_PLAN_QUALITY']:
                plan_quality(search_plan, hits)
            offered=[{**p,'key':f'S{i+1}'} for i,p in enumerate(hits)]
            payload=[{k:p[k] for k in ('key','doc','page','id','text')} for p in offered]
            result={}
            if payload:
                with stage('answer'):
                    result=ai.answer(question,lang,payload,history)
            text,evidence=ai.validate_answer(result,offered)
            notice='' if text else ('Je ne peux pas confirmer la réponse à partir des passages trouvés. Cela ne signifie pas que le livre ne traite pas du sujet.' if lang=='fr-CA' else 'I could not verify an answer from the retrieved passages. This does not establish that the book omits the topic.')
            def present(p):
                return {**{k:v for k,v in p.items() if k!='rects'},'title':library().docs[p['doc']]['title'],
                    'language':library().docs[p['doc']].get('language','en-CA'),'url':reader_url(p)}
            web=None
            if data.get('web',True) is True:
                try:
                    with stage('web'):
                        web=ai.web_search(search_plan['query_en'],lang,'; '.join(d['subject'] for d in docs))
                except Exception as e:
                    logging.warning('External search unavailable: %s',type(e).__name__)
                    web={'text':'','citations':[],'verified':False,'error':True}
            return jsonify(category='book' if text else 'related_outside',language=lang,
                book_answer=text or '',notice=notice,evidence=[present(p) for p in evidence],
                results=[present(p) for p in offered],web=web)
        with request_timing(doc_id):
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
