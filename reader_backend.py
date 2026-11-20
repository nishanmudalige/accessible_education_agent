"""Original-page rendering and exact source-block overlays, following Kysely's reader."""
from functools import lru_cache
import math
import re
import threading
import time
from timing import emit
import fitz
from retrieval import expand, tokens

PDF_LOCK=threading.RLock()

@lru_cache(maxsize=10)
def page_png(path, number, scale, book=None):
    started = time.perf_counter()
    try:
        with PDF_LOCK, fitz.open(path) as pdf:
            page=pdf[number-1]
            return page.get_pixmap(matrix=fitz.Matrix(scale,scale),colorspace=fitz.csRGB,alpha=False).tobytes('png')
    finally:
        emit(event='png_render', book=book or path, page=number, scale=scale, seconds=time.perf_counter()-started)

def resolution(value):
    try: scale=float(value)
    except (ValueError,TypeError):raise ValueError('Invalid image resolution') from None
    if not math.isfinite(scale) or not 1<=scale<=3.5:raise ValueError('Invalid image resolution')
    return round(scale*2)/2

def page_data(index, doc_id, number, ids=(), query=''):
    blocks=index.page(doc_id,number)
    requested=set(ids)
    selected=[b for b in blocks if b['id'] in requested]
    query=' '.join(query.split())[:200]
    boxes=[]
    if not selected and query:
        # Page searches highlight real matches; bilingual fallback selects matching source blocks.
        with PDF_LOCK, fitz.open(index.docs[doc_id]['path']) as pdf:
            page=pdf[number-1]
            phrases=[query]
            phrases.extend(re.findall(r'[\wÀ-ÿ-]{3,}',expand(query)))
            phrases.extend(re.findall(r'[\wÀ-ÿ-]{3,}',query))
            seen=set()
            for phrase in dict.fromkeys(phrases):
                for rect in page.search_for(phrase)[:60]:
                    key=tuple(round(v,2) for v in rect)
                    if key in seen:continue
                    seen.add(key)
                    boxes.append({'x':rect.x0/page.rect.width*100,'y':rect.y0/page.rect.height*100,
                                  'w':rect.width/page.rect.width*100,'h':rect.height/page.rect.height*100})
            words=set(tokens(query+' '+expand(query)))
            selected=[b for b in blocks if words.intersection(tokens(b['text']))]
    if requested or not boxes:
        boxes=[r for b in selected for r in b['rects']]
    with PDF_LOCK,fitz.open(index.docs[doc_id]['path']) as pdf:
        size=pdf[number-1].rect
        width,height=size.width,size.height
    return {'page':number,'doc':doc_id,'width':width,'height':height,
            'page_count':index.docs[doc_id]['page_count'],
            'language':index.docs[doc_id].get('language','en-CA'),
            'blocks':blocks,'boxes':boxes[:240],'selected_ids':[b['id'] for b in selected],
            'passage_texts':[b['text'] for b in selected],
            'text':'\n\n'.join(b['text'] for b in blocks)}
