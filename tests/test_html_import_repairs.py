import base64
import importlib.util
import json
import re
from pathlib import Path
from zipfile import ZipFile
import pytest
from bs4 import BeautifulSoup
import app as application
import ai_service as ai
from html_media import MediaStore, image_suffix

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('repaired_import',ROOT/'scripts/import_html.py')
importer=importlib.util.module_from_spec(spec);spec.loader.exec_module(importer)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j7XcAAAAASUVORK5CYII=')

class NoFetch:
    def get_bytes(self,url): pytest.fail('Archive/cached images must not hit the network')


def test_lazy_picture_srcset_and_relative_images_are_local_and_indexed(tmp_path):
    archive=tmp_path/'media.epub'
    with ZipFile(archive,'w') as z:
        for name in ('large.png','lazy.png','normal.png'): z.writestr('EPUB/assets/'+name,PNG)
    media=MediaStore(tmp_path,'test',NoFetch(),archive)
    raw='''<title>Grammar</title><div class="entry-content"><h2>Sentence fragments</h2>
    <picture><source srcset="../large.png 1600w, ../small.png 400w"><img src="data:image/gif;base64,AAAA" alt="Incorrect: A fragment. Correct: This is a sentence."></picture>
    <p><img src="placeholder.gif" data-src="../lazy.png" data-srcset="../lazy.png 2x" alt="Add a subject and a verb."></p>
    <img src="normal.png" srcset="normal.png 1x" alt="A complete sentence."></div>'''
    _,html,blocks=importer.clean_chapter(raw,'https://book.org/chapter/one/','pressbooks',media)
    soup=BeautifulSoup(html,'html.parser')
    assert len(soup.select('img'))==3
    for img in soup.select('img'):
        assert img['src'].startswith('/book-assets/test/')
        assert not any(key in img.attrs for key in ('srcset','data-src','data-srcset'))
    text=' '.join(b['text'] for b in blocks)
    assert 'Incorrect: A fragment. Correct: This is a sentence.' in text
    assert 'Add a subject and a verb.' in text
    assert all((tmp_path/'assets'/Path(i['src']).name).exists() for i in soup.select('img'))
    media.save()
    assert len(media.records)==3


def test_tables_and_boxes_are_atomic_not_disconnected_cells():
    raw='''<title>Text</title><div class="ptx-content"><h1>Verb and calculus</h1>
    <p>Present tense of être.</p><table id="etre"><caption>être</caption><tr><th>Subject</th><th>Form</th></tr><tr><td>je</td><td>suis</td></tr><tr><td>nous</td><td>sommes</td></tr></table>
    <article class="assemblage" id="product"><h2>Product rule</h2><div class="para" id="condition">For differentiable f and g.</div><div class="displaymath">P'=fg'+gf'</div></article>
    <article class="definition" id="definition"><h3>Definition</h3><p>First condition.</p><p>Second condition.</p></article>
    <article class="example" id="worked"><h3>Example</h3><p>Find a derivative.</p><details><summary>Solution</summary><p>Use the product rule.</p></details></article>
    <div class="textbox" id="writing"><h2>Grammar</h2><p>Incorrect.</p><p>Correct.</p></div>
    <div class="calibre4">A grammar note outside a paragraph must also be retained.</div></div>'''
    _,_,blocks=importer.clean_chapter(raw,'https://book.org/one.html','pretext')
    by_id={b['id']:b for b in blocks}
    assert by_id['etre']['kind']=='table' and 'je | suis' in by_id['etre']['text'] and 'nous | sommes' in by_id['etre']['text']
    assert 'Present tense of être.' in by_id['etre']['text']
    assert 'condition' not in by_id
    assert 'differentiable' in by_id['product']['text'] and "P'=fg'+gf'" in by_id['product']['text']
    assert 'Second condition.' in by_id['definition']['text']
    assert 'Use the product rule.' in by_id['worked']['text']
    assert 'Incorrect.' in by_id['writing']['text'] and 'Correct.' in by_id['writing']['text']
    assert any('outside a paragraph' in b['text'] for b in blocks)


def test_image_error_pages_are_not_saved_as_real_images(tmp_path):
    class BadFetch:
        def get_bytes(self,url): return b'<html>403 Forbidden</html>'
    media=MediaStore(tmp_path,'test',BadFetch())
    local,source=media.localize(['https://example.org/missing.png'],'Incorrect: a fragment. Correct: It is a sentence.')
    assert media.records[source]['status']=='unavailable'
    data=(tmp_path/'assets'/Path(local).name).read_bytes()
    assert image_suffix(data)=='.svg' and b'Original image unavailable' in data
    assert b'Incorrect: a fragment.' in data
    with pytest.raises(ValueError): image_suffix(b'<html>404</html>')


def proof(book,text):
    if book=='active-calculus-html':return "f(x) g'(x) + g(x) f'(x)" in text
    if book=='writing-for-success-html':return 'fix a fragment by adding the missing subject or verb' in text
    return all(form in text for form in ('je suis','tu es','nous sommes','vous êtes','ils/elles sont'))


@pytest.mark.parametrize('book,question',[
    ('active-calculus-html','How do I use the product rule?'),
    ('writing-for-success-html','What is a sentence fragment, and how do I fix one?'),
    ('liberte1-html','How do I conjugate the verb être in the present tense?'),
])
def test_requested_questions_send_complete_evidence_and_open_local_citations(monkeypatch,book,question):
    index=application.library()
    hits=index.search(question,book,10)
    assert any(proof(book,p['text']) for p in hits)
    app=application.create_app({'TESTING':True,'SECRET_KEY':'regression','SKIP_PLAN':False})
    client=app.test_client()
    with client.session_transaction() as session:session['csrf']='regression'
    monkeypatch.setattr(ai,'plan',lambda *a:{'related':True,'language':'en-CA','query_en':question,'query_fr':''})
    def answer(q,lang,passages,*args):
        evidence=next(p for p in passages if proof(book,p['text']))
        return {'related':True,'supported':True,'answer':'Verified fixture. ['+evidence['key']+']','evidence':[evidence['key']]}
    monkeypatch.setattr(ai,'answer',answer)
    response=client.post('/api/ask',json={'doc':book,'question':question,'language':'en-CA','web':False},headers={'X-CSRF-Token':'regression'})
    assert response.status_code==200 and response.json['category']=='book'
    evidence=response.json['evidence'][0]
    assert proof(book,evidence['text'])
    page=client.get(evidence['url'])
    assert page.status_code==200 and evidence['id'] in page.get_data(as_text=True)


def test_sentence_examples_in_alt_text_are_searchable():
    hits=application.library().search('After walking over two miles','writing-for-success-html',10)
    assert any('Incorrect:' in p['text'] and 'Correct:' in p['text'] and p.get('images') for p in hits)


def test_all_snapshot_images_have_local_valid_files_and_alt_is_indexed():
    client=application.create_app({'TESTING':True,'SECRET_KEY':'assets'}).test_client()
    for book in ('active-calculus-html','writing-for-success-html','liberte1-html'):
        root=ROOT/'content'/book;snapshot=json.loads((root/'book.json').read_text());seen=set()
        for chapter in snapshot['chapters']:
            soup=BeautifulSoup((root/chapter['file']).read_text(),'html.parser')
            text=' '.join(p['text'] for p in chapter['passages'])
            for image in soup.select('img'):
                url=image['src'];assert url.startswith('/book-assets/'+book+'/')
                alt=importer.normalized(image.get('alt',''))
                if alt:assert alt in text,(book,chapter['id'],alt)
                assert 'srcset' not in image.attrs and 'data-src' not in image.attrs
                if url not in seen:
                    response=client.get(url);assert response.status_code==200
                    image_suffix(response.data);assert response.mimetype.startswith('image/')
                    seen.add(url)
        assert seen
    assert client.get('/book-assets/active-calculus-html/not-an-image.html').status_code==404
    assert client.get('/book-assets/unknown/'+'a'*24+'.png').status_code==404


def test_every_imported_table_and_teaching_box_is_complete_in_one_block():
    count=0
    for book in ('active-calculus-html','writing-for-success-html','liberte1-html'):
        root=ROOT/'content'/book
        for chapter in json.loads((root/'book.json').read_text())['chapters']:
            soup=BeautifulSoup((root/chapter['file']).read_text(),'html.parser')
            records=chapter['passages'];ids={n['id'] for n in soup.select('[id]')}
            assert all(p['id'] in ids for p in records)
            for block in soup.select(importer.ATOMIC):
                text=importer.evidence_text(block).strip()
                if text:
                    assert any(re.sub(r'\s+','',text) in re.sub(r'\s+','',p['text']) for p in records),(book,chapter['id'],block.name,block.get('id'))
                    count+=1
    assert count>392  # Includes all tables plus definitions, examples and textboxes.
