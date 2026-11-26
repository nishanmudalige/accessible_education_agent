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


def test_exponential_family_reproduction_and_legend():
    from plots import curve
    import numpy as np
    xs=np.array([-1.,0.,1.])
    spec=function('2**x')
    spec['expr']=['2**x','3**x','(1/2)**x','(1/3)**x']
    for source,base in zip(spec['expr']+['0.5**x','exp(x)'],[2,3,.5,1/3,.5,np.e]):
        _,ys=curve(source,xs)
        np.testing.assert_allclose(ys,base**xs)
    plot=generated_plot(spec,'en-CA')
    svg=base64.b64decode(plot['local_url'].split(',')[1]).decode()
    assert 'id="legend_1"' in svg
    for label in ['2^x','3^x','(1/2)^x','(1/3)^x']:
        assert 'y = '+label in svg


@pytest.mark.parametrize('expr,mask',[
    ('ln(x)',[True,True,False]),('log(x)',[True,True,False]),
    ('sqrt(x)',[True,False,False]),('exp(log(x))',[True,True,False])])
def test_only_real_domain_is_plotted(expr,mask):
    from plots import curve
    import numpy as np
    _,ys=curve(expr,np.array([-1.,0.,1.]))
    assert np.ma.getmaskarray(ys).tolist()==mask
    assert generated_plot(function(expr),'fr-CA')


def test_plot_failure_logs_and_preserves_answer(monkeypatch,caplog):
    import plots
    monkeypatch.setattr(plots.log,"propagate",True)
    import app as module
    monkeypatch.setattr(module.ai,'plan',lambda *args:dict(related=True,language='fr-CA',intent='generate',query_en='logarithm',query_fr='logarithme'))
    spec=function('(-2)**x')
    monkeypatch.setattr(module.ai,'generate',lambda *args:dict(supported=True,answer='Exemple. [S1]',evidence=['S1'],plot=spec))
    client=module.create_app({'TESTING':True,'SECRET_KEY':'demo'}).test_client()
    with client.session_transaction() as session:
        session['csrf']='demo'
    result=client.post('/api/ask',headers={'X-CSRF-Token':'demo'},
                       json={'question':'Tracez une courbe.','doc':'active-calculus-html'}).json
    assert result['book_answer']=='Exemple. [S1]' and result['figures']==[] and result['plot_failed']
    logs=caplog.text
    assert '(-2)**x' in logs and 'positive constant base' in logs


@pytest.mark.parametrize('mode,cuts,intervals',[
    ('left',[-1.96],[(-5,-1.96)]),('right',[2],[(2,5)]),
    ('middle',[-1.96,1.96],[(-1.96,1.96)]),
    ('two_tails',[-2.1,2.1],[(-5,-2.1),(2.1,5)])])
def test_density_shading_and_critical_lines(mode,cuts,intervals):
    import math
    from matplotlib.figure import Figure
    import numpy as np
    from plots import distribution
    ax=Figure().subplots()
    alt=distribution(ax,dict(type='distribution',family='t',df=5,critical=cuts,
                             shade=mode,compare_normal=True),False,str)
    lines=ax.lines
    center=np.argmin(abs(lines[0].get_xdata()))
    expected=math.gamma(3)/(math.sqrt(5*math.pi)*math.gamma(2.5))
    assert lines[0].get_ydata()[center]==pytest.approx(expected)
    assert lines[1].get_ydata()[center]==pytest.approx(1/math.sqrt(2*math.pi))
    assert [line.get_xdata()[0] for line in lines[2:]]==cuts
    assert len(ax.collections)==len(intervals) and 'heavier tails' in alt
    for shaded,(lo,hi) in zip(ax.collections,intervals):
        xs=shaded.get_paths()[0].vertices[:,0]
        if lo in cuts: assert xs.min()==pytest.approx(lo)
        if hi in cuts: assert xs.max()==pytest.approx(hi)


@pytest.mark.parametrize('highlight',[[],[3],[2,5]])
def test_binomial_bars_and_highlights(highlight):
    from matplotlib.figure import Figure
    from plots import binomial
    ax=Figure().subplots()
    binomial(ax,dict(n=10,p=.3,highlight=highlight,family='binomial'),True,str)
    assert sum(bar.get_height() for bar in ax.patches)==pytest.approx(1)
    assert ax.patches[3].get_height()==pytest.approx(.266827932)
    selected=[k for k,bar in enumerate(ax.patches) if bar.get_hatch()]
    assert selected==(list(range(highlight[0],highlight[-1]+1)) if highlight else [])


@pytest.mark.parametrize('kind,f,a,b,h,slope',[
    ('tangent','x**3',1,None,None,3),('secant','x**2',1,3,None,4),
    ('secant','x**2',3,None,-2,4)])
def test_computed_line(kind,f,a,b,h,slope):
    import numpy as np
    from matplotlib.figure import Figure
    from plots import calculus
    ax=Figure().subplots()
    calculus(ax,dict(type=kind,f=f,a=a,b=b,h=h,x_range=[-1,4]),False,str)
    xs,ys=ax.lines[1].get_data()
    ya=a**(3 if kind=='tangent' else 2)
    np.testing.assert_allclose(ys,ya+slope*(xs-a))
    assert len(ax.collections)==(1 if kind=='tangent' else 2)


def test_area_shades_exact_requested_interval():
    from matplotlib.figure import Figure
    from plots import calculus
    ax=Figure().subplots()
    alt=calculus(ax,dict(type='area',f='x**2',a=0,b=2,x_range=[-1,3]),True,str)
    xs=ax.collections[0].get_paths()[0].vertices[:,0]
    assert xs.min()==0 and xs.max()==2 and 'Aire ombrée' in alt
