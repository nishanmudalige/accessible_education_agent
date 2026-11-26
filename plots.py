"""Bounded, declarative textbook illustrations. Only fixed operations accept model input."""
import ast
import base64
import io
import math
import re
import threading

# One small figure at a time across the Gunicorn worker's threads.
_render_lock = threading.Lock()


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
                 'exp': (sp.exp, np.exp), 'log': (sp.log, np.log),
                 'sqrt': (sp.sqrt, np.sqrt), 'abs': (sp.Abs, np.abs)}

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
            if isinstance(node.op, ast.Pow) and np.isscalar(bv) and np.isfinite(bv) and abs(bv)<=12:
                return sp.Pow(a,b,evaluate=False), np.power(av,bv)
        raise ValueError('Unsupported expression')

    with np.errstate(all='ignore'):
        expr, ys = visit(root)
    ys = np.broadcast_to(ys, xs.shape)
    return expr, np.ma.masked_invalid(ys)


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
        if not isinstance(exprs,list) or not 1<=len(exprs)<=3:
            raise ValueError('Expected one to three curves')
        labels=[]
        for source, style in zip(exprs, ['-', '--', '-.']):
            expr, ys = curve(source, xs)
            if ys.count()<2:
                raise ValueError('No real curve in interval')
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
    elif spec['type']=='normal':
        mean,sd=number(spec['mean']),number(spec['sd'])
        if sd<1e-8:
            raise ValueError('Invalid standard deviation')
        lo,hi=mean-4*sd,mean+4*sd
        shade=spec.get('shade')
        if shade is not None:
            a,b=pair(shade, ordered=True)
            lo,hi=min(a,lo),max(b,hi)
        xs=np.linspace(lo,hi,501)
        def density(x):
            return np.exp(-0.5*((x-mean)/sd)**2)/(sd*math.sqrt(2*math.pi))
        ax.plot(xs,density(xs),color='#174777',linewidth=2)
        ax.set(xlabel='x',ylabel='Densité' if fr else 'Density',ylim=(0,None))
        alt=(f'Courbe normale de moyenne {fmt(mean)} et d’écart-type {fmt(sd)}.' if fr else
             f'Normal density curve with mean {fmt(mean)} and standard deviation {fmt(sd)}.')
        if shade is not None:
            region=np.linspace(a,b,301)
            ax.fill_between(region,0,density(region),color='#8ebbd2',hatch='//',edgecolor='#426577')
            alt+=(f' Aire ombrée entre {fmt(a)} et {fmt(b)}.' if fr else f' Area shaded from {fmt(a)} to {fmt(b)}.')
    else:
        raise ValueError('Unknown plot type')
    output=io.BytesIO()
    fig.savefig(output,format='svg',facecolor='white')
    encoded=base64.b64encode(output.getvalue()).decode('ascii')
    return {'kind':'generated','local_url':'data:image/svg+xml;base64,'+encoded,'alt':alt}


def generated_plot(spec, lang):
    if not isinstance(spec,dict):
        return None
    try:
        with _render_lock:
            return _draw(spec,lang)
    except Exception:
        # Optional illustration errors must never discard a supported answer.
        return None
