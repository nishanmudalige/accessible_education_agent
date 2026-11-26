import base64
from xml.etree import ElementTree

import pytest

from plots import generated_plot


def function(expr):
    return {'type':'function','expr':[expr],'x_range':[-3,3],'title':'Quadratic','mark_points':[[0,0]]}


def test_function_svg_and_french_description():
    spec=function('x**2')
    spec['expr'].append('sin(x)+1')
    plot=generated_plot(spec,'fr-CA')
    svg=ElementTree.fromstring(base64.b64decode(plot['local_url'].split(',')[1]))
    assert svg.tag.endswith('}svg') and plot['kind']=='generated'
    assert 'Graphique de y = x²' in plot['alt'] and 'Point marqué' in plot['alt']


def test_normal_shading_description():
    spec={'type':'normal','mean':0,'sd':1,'shade':[-1.96,1.96],'title':'Central 95%'}
    assert 'shaded from −1.96 to 1.96' in generated_plot(spec,'en-CA')['alt']
    spec['sd']=0
    assert generated_plot(spec,'en-CA') is None


@pytest.mark.parametrize('expr',['x.real','unknown(x)','[x]*5','x**1000','sin(x,x)','inf','x+'*100,'sqrt(-1)'])
def test_invalid_plot_leaves_answer_available(expr):
    assert generated_plot(function(expr),'en-CA') is None


def test_named_pdf_figure_links_to_verified_caption(monkeypatch):
    import app as module
    monkeypatch.setattr(module.ai,'plan',lambda *args:dict(related=True,language='en-CA',query_en='Figure 1.8',query_fr=''))
    client=module.create_app({'TESTING':True,'SECRET_KEY':'demo'}).test_client()
    with client.session_transaction() as session:
        session['csrf']='demo'
    result=client.post('/api/ask',headers={'X-CSRF-Token':'demo'},
                       json={'question':'Show me Figure 1.8','doc':'openintro-statistics-4e'}).json
    assert result['figures']==[] and 'page 16' in result['book_answer']
    assert 'page=16' in result['evidence'][0]['url']
