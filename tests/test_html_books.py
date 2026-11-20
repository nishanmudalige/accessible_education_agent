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
