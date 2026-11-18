"""Deterministic contrast checks for every display/palette combination."""
import json
from pathlib import Path
import pytest
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
PALETTES=json.loads((ROOT/'static/accessibility-palettes.json').read_text())
def luminance(value):
    rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
    return sum(a*b for a,b in zip(linear,(.2126,.7152,.0722)))
def contrast(a,b):
    x,y=sorted((luminance(a),luminance(b)))
    return (y+.05)/(x+.05)
@pytest.mark.parametrize('appearance',list(PALETTES))
@pytest.mark.parametrize('vision',list(PALETTES['light']))
def test_every_theme_and_palette_has_readable_text(appearance,vision):
    p=PALETTES[appearance][vision]
    limit=7 if appearance.startswith('contrast') else 4.5
    for fg in ('ink','muted','accent','blue'):
        for bg in ('paper','bg','wash'):
            assert contrast(p[fg],p[bg])>=limit,(appearance,vision,fg,bg,contrast(p[fg],p[bg]))
    for fg,bg in [('green','book-bg'),('orange','related-bg'),('red','outside-bg'),('action-ink','action-bg')]:
        assert contrast(p[fg],p[bg])>=limit,(appearance,vision,fg,bg,contrast(p[fg],p[bg]))
    for bg in ('paper','bg','wash'):
        assert contrast(p['control-line'],p[bg])>=3,(appearance,vision,'control boundary',bg)
    for key in ('pdf-evidence-line','pdf-spoken-line'):
        assert contrast(p[key],'#ffffff')>=3

def test_settings_use_native_controls_and_distinct_source_labels():
    template=(ROOT/'templates/_accessibility.html').read_text()
    for value in ['protanopia','deuteranopia','tritanopia','monochrome','contrast-light','contrast-dark']:
        assert value in template
    assert '<fieldset>' in template and 'type="radio"' in template
    css=(ROOT/'static/accessibility.css').read_text()
    assert '.badge.book' in css and 'border-style:dashed' in css and 'border-style:dotted' in css
    assert 'prefers-reduced-motion' in css and 'forced-colors:active' in css
    assert 'filter:grayscale' not in css

def test_bilingual_settings_and_external_scripts_are_available():
    from app import create_app
    client=create_app({'TESTING':True,'SECRET_KEY':'test'}).test_client()
    html=client.get('/').get_data(as_text=True)
    assert 'id="accessibility-dialog"' in html and 'id="accessibility-open"' in html
    assert 'data-fr="Basse vision"' in html
    for file in ('display-init.js','accessibility.js','accessibility.css','display-palettes.css'):
        assert client.get('/static/'+file).status_code==200


def test_runtime_css_matches_the_checked_palette_values():
    css=(ROOT/'static/display-palettes.css').read_text()
    for appearance,visions in PALETTES.items():
        for vision,tokens in visions.items():
            selector=f':root[data-appearance="{appearance}"][data-vision="{vision}"]'
            assert selector in css
            block=css.split(selector+'{',1)[1].split('}',1)[0]
            for key,value in tokens.items():assert f'--{key}:{value};' in block
