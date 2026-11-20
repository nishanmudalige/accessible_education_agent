import importlib.util
import json
from pathlib import Path
import pytest
import app as module
import ai_service as ai
from retrieval import LibraryIndex

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('html_import',ROOT/'scripts/import_html.py')
importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)

@pytest.mark.parametrize('kind,wrapper',[('pretext','ptx-content'),('pressbooks','entry-content')])
def test_importer_extracts_clean_paragraphs_math_and_stable_anchors(kind,wrapper):
    source=f'''<title>Test</title><main><h1>Chapter One</h1><div class="{wrapper}"><nav>Do not index menu</nav><p id="original">A derivative measures a rate of change. <span class="autopermalink">LINK ICON</span></p><p>Formula \\( \\frac{{1}}{{2}} \\)</p><p>Formula \\( \\frac{{1}}{{2}} \\)</p><img src="diagram.svg" onerror="bad()"><script>bad()</script><a href="javascript:bad()">unsafe</a><footer>FOOTER</footer></div></main>'''
    title,html,blocks=importer.clean_chapter(source,'https://example.org/book/chapter/',kind)
    assert title=='Chapter One'
    assert 'Do not index menu' not in html and 'LINK ICON' not in html and 'FOOTER' not in html
    assert '<script' not in html and 'onerror' not in html and 'javascript:' not in html
    assert blocks[0]['id']=='original' and blocks[0]['source_anchor']=='original'
    assert 'original' not in blocks[0]['text']
    assert blocks[1]['source_anchor'] is None and blocks[1]['id']!=blocks[2]['id']
    assert '\\frac' in blocks[1]['text'] and 'https://example.org/book/chapter/diagram.svg' in html
    assert importer.clean_chapter(source,'https://example.org/book/chapter/',kind)[2]==blocks


def test_pretext_directory_stays_in_book():
    soup=importer.BeautifulSoup('<nav id="ptx-toc"><a href="a.html">A</a><a href="a.html#x">Same</a><a href="b.html">B</a><a href="https://other.org/a.html">External</a></nav>','html.parser')
    assert list(importer.chapter_links(soup,'https://example.org/book/frontmatter.html','pretext'))==['https://example.org/book/a.html','https://example.org/book/b.html']


def test_active_html_retrieval_citation_and_attribution(monkeypatch):
    index=module.library()
    assert len(index.docs['active-calculus-html']['chapters'])==69
    hit=index.search('limit','active-calculus-html',1)[0]
    assert hit['chapter_title'] and hit['source_url'] and hit['format']=='html'
    application=module.create_app({'TESTING':True,'SECRET_KEY':'html','SKIP_PLAN':False})
    client=application.test_client()
    with client.session_transaction() as s:s['csrf']='html-csrf'
    monkeypatch.setattr(ai,'plan',lambda *a: {'related':True,'language':'en-CA','query_en':'limit','query_fr':'limite'})
    monkeypatch.setattr(ai,'answer',lambda *a: {'related':True,'supported':True,'answer':'A limit. [S1]','evidence':['S1']})
    data=client.post('/api/ask',json={'question':'What is a limit?','doc':'active-calculus-html','web':False},headers={'X-CSRF-Token':'html-csrf'}).json
    url=data['evidence'][0]['url']
    assert url.startswith('/book/active-calculus-html/') and '?hl=' in url
    response=client.get(url)
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert hit['id'] in html and 'CC BY-SA 4.0' in html and 'Matthew Boelkins' in html
    assert 'tex-chtml-full.js' in html and 'book.js' in html
    assert "font-src 'self'" in response.headers['Content-Security-Policy']
    assert client.get('/pdf/active-calculus-html').status_code==404
    assert client.get('/book/active-calculus-html/unknown').status_code==404
    assert client.get('/static/vendor/mathjax/es5/tex-chtml-full.js').status_code==200


def test_html_snapshot_paths_are_checked(tmp_path):
    (tmp_path/'book.json').write_text(json.dumps({'chapters':[{'file':'../unsafe.html'}]}))
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'documents':[{'id':'test','format':'html','file':'book.json'}]}))
    with pytest.raises(ValueError):LibraryIndex(manifest)


def test_html_only_index_does_not_load_pdf():
    index=LibraryIndex(ROOT/'content/manifest.json',doc_id='active-calculus-html')
    assert list(index.docs)==['active-calculus-html']
    assert index.search('derivative')[0]['format']=='html'


def test_official_pressbooks_export_preserves_toc_and_canonical_links():
    source='''<div id="toc"><a href="#chapter-first">First</a><a href="#chapter-second">Second</a></div><div class="chapter" id="chapter-first" title="First"><h2>First</h2><p id="existing">A thesis statement is an argument.</p><a href="#chapter-second">Next</a></div><div class="chapter" id="chapter-second" title="Second"><h2>Second</h2><p>Supporting evidence.</p></div>'''
    chapters=list(importer.export_chapters(source,'https://example.org/book/'))
    assert [url for url,_ in chapters]==['https://example.org/book/chapter/first/','https://example.org/book/chapter/second/']
    assert 'https://example.org/book/chapter/second/' in chapters[0][1]
    assert importer.clean_chapter(chapters[0][1],chapters[0][0],'pressbooks')[2][0]['id']=='existing'


def test_writing_snapshot_search_and_local_citation(monkeypatch):
    index=module.library()
    assert len(index.docs['writing-for-success-html']['chapters'])==14
    hit=index.search('thesis statement','writing-for-success-html',1)[0]
    assert 'thesis' in hit['text'].lower()
    client=module.create_app({'TESTING':True,'SECRET_KEY':'writing'}).test_client()
    response=client.get(module.reader_url(hit))
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert hit['id'] in html and 'Tara Horkoff' in html and 'CC BY-NC-SA 4.0' in html
    assert 'https://opentextbc.ca/writingforsuccess/' in html
    with client.session_transaction() as session: session['csrf']='writing-csrf'
    monkeypatch.setattr(ai,'plan',lambda *a: {'related':True,'language':'en-CA','query_en':'thesis statement','query_fr':'énoncé de thèse'})
    monkeypatch.setattr(ai,'answer',lambda *a: {'related':True,'supported':True,'answer':'A thesis statement. [S1]','evidence':['S1']})
    answer=client.post('/api/ask',json={'question':'What is a thesis statement?','doc':'writing-for-success-html','web':False},headers={'X-CSRF-Token':'writing-csrf'}).json
    assert answer['category']=='book' and answer['evidence'][0]['url'].startswith('/book/writing-for-success-html/')


def test_liberte_french_search_answer_and_citation(monkeypatch):
    index=module.library()
    assert len(index.docs['liberte1-html']['chapters'])==30
    hits=index.search('être present tense conjugation','liberte1-html',5)
    assert hits and any('être' in h['text'] or 'present' in h['text'].lower() for h in hits)
    client=module.create_app({'TESTING':True,'SECRET_KEY':'liberte','SKIP_PLAN':False}).test_client()
    with client.session_transaction() as session:session['csrf']='liberte-csrf'
    monkeypatch.setattr(ai,'plan',lambda *a:{'related':True,'language':'fr-CA','query_en':'être present tense conjugation','query_fr':'être présent'})
    monkeypatch.setattr(ai,'answer',lambda *a:{'related':True,'supported':True,'answer':'Je suis. [S1]','evidence':['S1']})
    result=client.post('/api/ask',json={'question':'Comment conjuguer le verbe être au présent ?','doc':'liberte1-html','language':'fr-CA','web':False},headers={'X-CSRF-Token':'liberte-csrf'}).json
    assert result['category']=='book' and result['language']=='fr-CA'
    page=client.get(result['evidence'][0]['url'])
    assert page.status_code==200
    text=page.get_data(as_text=True)
    assert 'lang="fr-CA"' in text and 'CC BY-NC-SA 4.0' in text and 'Alexandra Tsedryk' in text
    assert result['evidence'][0]['id'] in text


def test_all_smoke_questions_have_local_evidence():
    index=module.library()
    questions=json.loads((ROOT/'benchmark/questions_html_smoke.json').read_text())
    assert len(questions)==6
    for q in questions:
        hits=index.search(q['question'],q['book'],3)
        assert hits, q
        assert module.reader_url(hits[0]).startswith('/book/')


def test_html_citation_focus_and_disclosure_script():
    import shutil
    import subprocess
    node=shutil.which('node')
    if not node: pytest.skip('Node.js needed for citation UI fixture')
    subprocess.run([node,'tests/book_ui.cjs'],cwd=ROOT,check=True)
