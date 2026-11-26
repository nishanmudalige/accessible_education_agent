"""Bounded, declarative textbook illustrations. Only fixed operations accept model input."""
import ast
import base64
import io
import json
import logging
import math
import re
import threading

# One small figure at a time across the Gunicorn worker's threads.
_render_lock = threading.Lock()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler())
log.propagate = False
line_styles = ['-', '--', '-.', ':', (0, (5, 2, 1, 2)), (0, (3, 2, 1, 2, 1, 2))]


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e6:
        raise ValueError('Expected a bounded finite number')
    return float(value)


def pair(values, ordered=False):
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError('Expected two coordinates')
    a, b = map(number, values)
    if ordered and b - a < 1e-8:
        raise ValueError('Empty interval')
    return a, b


def curve(source, xs):
    import numpy as np
    import sympy as sp

    if not isinstance(source, str) or len(source) > 100:
        raise ValueError('Invalid expression length')
    root = ast.parse(source.strip(), mode='eval').body
    if sum(1 for _ in ast.walk(root)) > 40:
        raise ValueError('Expression too complex')
    x = sp.Symbol('x', real=True)
    functions = {'sin': (sp.sin, np.sin), 'cos': (sp.cos, np.cos),
                 'exp': (sp.exp, np.exp), 'log': (sp.log, np.ma.log), 'ln': (sp.log, np.ma.log),
                 'sqrt': (sp.sqrt, np.ma.sqrt), 'abs': (sp.Abs, np.abs)}

    def visit(node):
        if isinstance(node, ast.Constant):
            value = number(node.value)
            literal=sp.Integer(value) if value.is_integer() else sp.Float(value)
            return literal, value
        if isinstance(node, ast.Name) and node.id == 'x':
            return x, xs
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            expr, values = visit(node.operand)
            if isinstance(node.op, ast.USub):
                return sp.Mul(-1, expr, evaluate=False), -values
            return expr, values
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and len(node.args)==1 and not node.keywords:
            if node.func.id not in functions:
                raise ValueError(f'Unsupported function {node.func.id!r}')
            symbolic, numeric = functions[node.func.id]
            expr, values = visit(node.args[0])
            return symbolic(expr, evaluate=False), numeric(values)
        if isinstance(node, ast.BinOp):
            a, av = visit(node.left)
            b, bv = visit(node.right)
            if isinstance(node.op, ast.Add):
                return sp.Add(a,b,evaluate=False), np.add(av,bv)
            if isinstance(node.op, ast.Sub):
                return sp.Add(a,sp.Mul(-1,b,evaluate=False),evaluate=False), np.subtract(av,bv)
            if isinstance(node.op, ast.Mult):
                return sp.Mul(a,b,evaluate=False), np.multiply(av,bv)
            if isinstance(node.op, ast.Div):
                return sp.Mul(a,sp.Pow(b,-1,evaluate=False),evaluate=False), np.divide(av,bv)
            if isinstance(node.op, ast.Pow):
                constant_power = np.isscalar(bv) and np.isfinite(bv) and abs(bv)<=12
                exponential = (isinstance(node.right, ast.Name) and node.right.id=='x'
                               and np.isscalar(av) and np.isfinite(av) and av>0)
                if not (constant_power or exponential):
                    raise ValueError('Power requires a small constant exponent or a positive constant base raised to x')
                return sp.Pow(a,b,evaluate=False), np.power(av,bv)
        raise ValueError('Unsupported expression')

    with np.errstate(all='ignore'):
        expr, ys = visit(root)
    if np.ndim(ys)==0:
        ys = np.ma.repeat(ys, xs.size)
    return expr, np.ma.masked_invalid(ys)


def distribution(ax, spec, fr, fmt):
    import numpy as np

    legacy = spec['type']=='normal'
    family = 'normal' if legacy else spec['family']
    if family=='normal':
        mean=number(spec['mean']) if spec.get('mean') is not None else 0
        sd=number(spec['sd']) if spec.get('sd') is not None else 1
        if sd<1e-8:
            raise ValueError('Invalid standard deviation')
        def density(x):
            return np.exp(-0.5*((x-mean)/sd)**2)/(sd*math.sqrt(2*math.pi))
        alt=(f'Courbe normale de moyenne {fmt(mean)} et d’écart-type {fmt(sd)}.' if fr else
             f'Normal density curve with mean {fmt(mean)} and standard deviation {fmt(sd)}.')
        name='Normale' if fr else 'Normal'
    elif family=='t':
        df=number(spec['df'])
        if df<=0:
            raise ValueError('Degrees of freedom must be positive')
        mean,sd=0,1
        factor=math.exp(math.lgamma((df+1)/2)-math.lgamma(df/2)-0.5*math.log(df*math.pi))
        def density(x):
            return factor*np.exp(-(df+1)/2*np.log1p(x*x/df))
        name=f't ({fmt(df)} ddl)' if fr else f't ({fmt(df)} df)'
        alt=(f'Loi de Student à {fmt(df)} degrés de liberté.' if fr else
             f'Student t density with {fmt(df)} degrees of freedom.')
    else:
        raise ValueError('Unknown distribution')

    mode=('middle' if spec.get('shade') else 'none') if legacy else spec['shade']
    cuts=[number(c) for c in ((spec.get('shade') or []) if legacy else spec['critical'])]
    if len(cuts)!={'none':0,'left':1,'right':1,'two_tails':2,'middle':2}.get(mode):
        raise ValueError('Wrong number of critical values')
    if len(cuts)==2 and cuts[1]<=cuts[0]:
        raise ValueError('Cutoffs must be increasing')
    lo=min([mean-4*sd]+[c-sd for c in cuts])
    hi=max([mean+4*sd]+[c+sd for c in cuts])
    if spec.get('compare_normal'):
        lo,hi=min(lo,-4),max(hi,4)
    xs=np.linspace(lo,hi,701)
    ax.plot(xs,density(xs),label=name,color='#174777',linewidth=2)
    if spec.get('compare_normal'):
        ax.plot(xs,np.exp(-xs*xs/2)/math.sqrt(2*math.pi),'--',color='#952f17',
                label='Normale standard' if fr else 'Standard normal')
        ax.legend()
        alt+=(' La courbe en tirets représente la normale standard.' if fr else
              ' The dashed curve shows the standard normal.')
        if family=='t':
            alt+=(' La loi de Student a des queues plus épaisses.' if fr else
                  ' The t distribution has heavier tails.')
    ax.set(xlabel='x',ylabel='Densité' if fr else 'Density',ylim=(0,None))
    intervals=[]
    if mode in ('left','two_tails'):
        intervals.append((lo,cuts[0]))
        alt+=f' Queue gauche ombrée sous {fmt(cuts[0])}.' if fr else f' Left tail shaded below {fmt(cuts[0])}.'
    if mode in ('right','two_tails'):
        intervals.append((cuts[-1],hi))
        alt+=f' Queue droite ombrée au-delà de {fmt(cuts[-1])}.' if fr else f' Right tail shaded above {fmt(cuts[-1])}.'
    if mode=='middle':
        intervals.append(cuts)
        a,b=map(fmt,cuts)
        alt+=f' Aire ombrée entre {a} et {b}.' if fr else f' Area shaded from {a} to {b}.'
    for a,b in intervals:
        region=np.linspace(a,b,301)
        ax.fill_between(region,0,density(region),color='#8ebbd2',hatch='//',edgecolor='#426577')
    for cutoff in cuts:
        ax.axvline(cutoff,color='#762b17',linestyle=':')
        ax.annotate(fmt(cutoff),(cutoff,0.94),xycoords=('data','axes fraction'),ha='center',
                    bbox={'facecolor':'white','edgecolor':'none','pad':1})
    return alt


def binomial(ax,spec,fr,fmt):
    n,p=spec['n'],number(spec['p'])
    if spec['family']!='binomial' or type(n)!=int or not 0<=n<=500 or not 0<=p<=1:
        raise ValueError('Invalid binomial parameters')
    highlight=spec['highlight']
    if len(highlight)>2 or any(type(k) not in (int,float) or not number(k).is_integer() or not 0<=k<=n for k in highlight):
        raise ValueError('Invalid highlighted outcomes')
    if highlight and highlight[0]>highlight[-1]:
        raise ValueError('Unordered highlighted outcomes')
    xs=range(n+1)
    probs=[math.comb(n,k)*p**k*(1-p)**(n-k) for k in xs]
    bars=ax.bar(xs,probs,color='#36688d')
    alt=(f'Loi binomiale avec n = {n} et p = {fmt(p)}.' if fr else
         f'Binomial probability distribution with n = {n} and p = {fmt(p)}.')
    ax.set(xlabel='k',ylabel='Probabilité' if fr else 'Probability',ylim=(0,None))
    if highlight:
        a,b=int(highlight[0]),int(highlight[-1])
        for k in range(a,b+1):
            bars[k].set(facecolor='#e5b271',edgecolor='#4d3521',hatch='//')
        span=str(a) if a==b else f'{a}–{b}'
        alt+=f' En surbrillance : {span}.' if fr else f' Highlighted outcomes: {span}.'
    return alt


def calculus(ax,spec,fr,fmt):
    import numpy as np
    import sympy as sp

    kind=spec['type']
    a=number(spec['a'])
    lo,hi=pair(spec['x_range'],ordered=True)
    xs=np.linspace(lo,hi,501)
    f=spec['f']
    expr,ys=curve(f,xs)
    if ys.count()<2 or not lo<=a<=hi:
        raise ValueError('Invalid function interval')
    ax.plot(xs,ys,label='y = '+f.replace('**','^'),linewidth=2)
    ax.set(xlabel='x',ylabel='y',xlim=(lo,hi))
    alt=('Courbe de ' if fr else 'Graph of ')+f.replace('**','^')+'.'
    if kind=='area':
        b=number(spec['b'])
        if not a<b<=hi:
            raise ValueError('Invalid shading interval')
        region=np.linspace(a,b,401)
        _,values=curve(f,region)
        if values.count()<2:
            raise ValueError('No real area on interval')
        ax.fill_between(region,0,values,color='#8ebbd2',hatch='//',edgecolor='#426577')
        ax.axhline(0,color='#333',linewidth=1)
        return alt+(f' Aire ombrée entre la courbe et l’axe des x de {fmt(a)} à {fmt(b)}.' if fr else
                    f' Area shaded between the curve and the x-axis from {fmt(a)} to {fmt(b)}.')

    points=[a]
    if kind=='secant':
        b=number(spec['b']) if spec.get('b') is not None else a+number(spec['h'])
        if not lo<=b<=hi or b==a:
            raise ValueError('Invalid second point')
        points.append(b)
    _,values=curve(f,np.array(points,dtype=float))
    if values.count()!=len(points):
        raise ValueError('Point outside real domain')
    if kind=='tangent':
        x=sp.Symbol('x',real=True)
        slope=float(sp.diff(expr,x).subs(x,a))
        # At a cusp the symbolic sign convention can give a spurious finite derivative.
        if expr.has(sp.Abs):
            delta=1e-6*max(1,abs(a))
            _,near=curve(f,np.array([a-delta,a+delta]))
            if near.count()!=2 or not np.isclose((values[0]-near[0])/delta,(near[1]-values[0])/delta,rtol=1e-4,atol=1e-4):
                raise ValueError('No unique tangent at this point')
        label='Tangente' if fr else 'Tangent'
    else:
        slope=(values[1]-values[0])/(b-a)
        label='Sécante' if fr else 'Secant'
    if not math.isfinite(slope):
        raise ValueError('Non-finite slope')
    ax.plot(xs,values[0]+slope*(xs-a),'--',color='#983a24',label=label)
    coords=[]
    for px,py in zip(points,values):
        coord=f'({fmt(px)} ; {fmt(py)})' if fr else f'({fmt(px)}, {fmt(py)})'
        coords.append(coord)
        ax.scatter(px,py,color='#712813',zorder=3)
        ax.annotate(coord,(px,py),xytext=(4,5),textcoords='offset points')
    ax.legend()
    joined=(' et ' if fr else ' and ').join(coords)
    return alt+(f' {label} de pente {fmt(slope)} passant par {joined}.' if fr else
                f' {label} with slope {fmt(slope)} through {joined}.')


def _draw(spec, lang):
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fr = lang.startswith('fr')
    def fmt(value):
        s = f'{value:.6g}'.replace('-', '−')
        return s.replace('.', ',') if fr else s

    title = spec['title']
    if not isinstance(title,str) or len(title)>100:
        raise ValueError('Invalid title')
    fig = Figure(figsize=(6.4, 3.8), facecolor='white', layout='constrained')
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.set_title(title, parse_math=False, wrap=True)
    ax.set_facecolor('white')
    ax.grid(color='#d0d5da')
    ax.set_axisbelow(True)
    if spec['type']=='function':
        lo, hi = pair(spec['x_range'], ordered=True)
        xs = np.linspace(lo, hi, 501)
        exprs = spec['expr']
        if not isinstance(exprs,list) or not 1<=len(exprs)<=len(line_styles):
            raise ValueError('Expected one to six curves')
        labels=[]
        for source, style in zip(exprs, line_styles):
            expr, ys = curve(source, xs)
            if ys.count()<2:
                raise ValueError(f'Fewer than two real, finite samples for {source!r} in [{lo}, {hi}]')
            label=re.sub(r'\*\*2(?![.\d])','²',source.strip()).replace('**','^').replace('*','×')
            if fr:
                label=re.sub(r'(?<=\d)\.(?=\d)',',',label)
            ax.plot(xs, ys, style, linewidth=2, label='y = '+label)
            labels.append('y = '+label)
        ax.legend()
        ax.set(xlabel='x', ylabel='y', xlim=(lo,hi))
        alt = (('Graphique de ' if fr else 'Graph of ')+', '.join(labels)
               + (f' pour x de {fmt(lo)} à {fmt(hi)}.' if fr else f' for x from {fmt(lo)} to {fmt(hi)}.'))
        if len(labels)==1 and str(expr)=='x**2':
            alt += (' Parabole ouverte vers le haut, de sommet (0 ; 0).' if fr
                    else ' Upward-opening parabola with vertex at (0, 0).')
        points=spec.get('mark_points') or []
        if not isinstance(points,list) or len(points)>8:
            raise ValueError('Too many points')
        for point in points:
            px,py=pair(point)
            if not lo<=px<=hi:
                raise ValueError('Point outside plot')
            ax.scatter(px,py,color='#982b18',zorder=3)
            alt+= (f' Point marqué ({fmt(px)} ; {fmt(py)}).' if fr else f' Marked point ({fmt(px)}, {fmt(py)}).')
    elif spec['type'] in ('distribution','normal'):
        alt=distribution(ax,spec,fr,fmt)
    elif spec['type']=='discrete':
        alt=binomial(ax,spec,fr,fmt)
    elif spec['type'] in ('tangent','secant','area'):
        alt=calculus(ax,spec,fr,fmt)
    else:
        raise ValueError('Unknown plot type')
    output=io.BytesIO()
    fig.savefig(output,format='svg',facecolor='white')
    encoded=base64.b64encode(output.getvalue()).decode('ascii')
    return {'kind':'generated','local_url':'data:image/svg+xml;base64,'+encoded,'alt':alt}


def generated_plot(spec, lang):
    if spec is None:
        return None
    log.info('Model plot=%s', json.dumps(spec, ensure_ascii=True))
    try:
        if not isinstance(spec,dict):
            raise ValueError('Expected a plot object')
        with _render_lock:
            return _draw(spec,lang)
    except Exception as error:
        log.warning("Plot generation failed: %s: %s; plot=%s", type(error).__name__, str(error), json.dumps(spec, ensure_ascii=True))
        # Optional illustration errors must never discard a supported answer.
        return None
