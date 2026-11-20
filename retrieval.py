"""Local multi-document BM25 retrieval with stable PDF-block evidence IDs.

No embeddings, database, cloud upload or API call is needed to build this index.
The exact same blocks drive search results, reader text and image overlays.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from pathlib import Path
import json
import math
import re
import unicodedata
import time
from timing import emit
from html_books import load_html_book
import fitz

STOP = set('the a an and or of to in is are it this that how what why explain please book page le la les un une des de du et ou est sont en dans que qui comment pourquoi expliquer livre je me vous mon my for with from on au aux pour avec ce ces il elle'.split())
GLOSSARY = {
    'intervalle de confiance': 'confidence interval', 'écart type': 'standard deviation',
    'écart-type': 'standard deviation', 'moyenne': 'mean average', 'médiane': 'median',
    'échantillon': 'sample sampling', 'échantillonnage': 'sampling',
    'probabilité': 'probability', 'probabilités': 'probability',
    'régression': 'regression', 'corrélation': 'correlation',
    'hypothèse': 'hypothesis testing', 'valeur p': 'p value hypothesis test',
    'loi normale': 'normal distribution', 'loi binomiale': 'binomial distribution',
    'loi de poisson': 'poisson distribution', 'variance': 'variance',
    'puissance': 'power', 'biais': 'bias', 'résidus': 'residuals',
    'données': 'data', 'écarts': 'deviations', 'indépendance': 'independence',
}

def normalize(text):
    text = text.replace('\u00ad', '')
    text = re.sub(r'(?<=\w)-\n(?=\w)', '', text)
    return re.sub(r'\s+', ' ', text).strip()

def tokens(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    return [x for x in re.findall(r"[a-z0-9]+", text) if len(x) > 1 and x not in STOP]

def expand(query):
    return ' '.join(v for k, v in GLOSSARY.items() if k in query.lower())

def manifest_documents(manifest, seen=None):
    manifest=manifest.resolve()
    seen=set() if seen is None else seen
    if manifest in seen: raise ValueError('Cyclic manifest inheritance')
    seen.add(manifest)
    data=json.loads(manifest.read_text(encoding='utf-8'))
    inherited=[]
    if data.get('extends'):
        parent=(manifest.parent/data['extends']).resolve()
        if not parent.is_relative_to(manifest.parent): raise ValueError('Unsafe inherited manifest path')
        inherited=manifest_documents(parent,seen)
    return inherited+data['documents']

class LibraryIndex:
    def __init__(self, manifest: Path, doc_id=None):
        self.root = manifest.parent.resolve()
        self.docs, self.pages, self.passages = {}, {}, []
        self.bags = []
        self.postings = defaultdict(list)
        entries = manifest_documents(manifest)
        if doc_id:
            entries=[entry for entry in entries if entry['id']==doc_id]
            if not entries: raise ValueError('Unknown document for indexing')
        for entry in entries:
            book_started = time.perf_counter()
            first_passage = len(self.passages)
            doc_id = entry['id']
            if not re.fullmatch(r'[a-z0-9-]+', doc_id) or doc_id in self.docs:
                raise ValueError('Each document needs a unique lowercase slug ID')
            if entry.get('format','pdf')=='html':
                doc,pages,passages=load_html_book(self.root,entry)
                self.docs[doc_id]=doc
                self.pages.update(pages)
                self.passages.extend(passages)
            else:
                path = (self.root / entry['file']).resolve()
                if not path.is_relative_to(self.root) or not path.is_file():
                    raise ValueError(f'Missing or unsafe document path for {doc_id}')
                with fitz.open(path) as pdf:
                    toc = [{'level': level, 'title': title, 'page': page} for level, title, page in pdf.get_toc() if 1 <= page <= len(pdf)]
                    self.docs[doc_id] = {**entry, 'path': path, 'page_count': len(pdf), 'toc': toc}
                    excluded = set(entry.get('exclude_search_pages', []))
                    for number, page in enumerate(pdf, 1):
                        blocks = []
                        for block in page.get_text('dict', sort=True)['blocks']:
                            if block['type'] != 0:
                                continue
                            lines = block.get('lines', [])
                            text = normalize('\n'.join(''.join(s['text'] for s in line['spans']) for line in lines))
                            if not text:
                                continue
                            # Preserve every textual block in the reader; tiny blocks stay out of ranking.
                            rects = [{'x': l['bbox'][0]/page.rect.width*100,
                                      'y': l['bbox'][1]/page.rect.height*100,
                                      'w': (l['bbox'][2]-l['bbox'][0])/page.rect.width*100,
                                      'h': (l['bbox'][3]-l['bbox'][1])/page.rect.height*100} for l in lines]
                            record = {'id': f'p{len(blocks)}', 'doc': doc_id, 'page': number,
                                      'text': text, 'rects': rects, 'label': page.get_label() or str(number)}
                            blocks.append(record)
                            if number not in excluded and len(text) >= 55:
                                self.passages.append(record)
                        self.pages[(doc_id, number)] = blocks
            for passage in self.passages[first_passage:]:
                bag = Counter(tokens(passage['text']))
                i = len(self.bags)
                self.bags.append(bag)
                for term in bag:
                    self.postings[term].append(i)
            emit(event='book_index', book=doc_id, seconds=time.perf_counter()-book_started)
        self.lengths = [sum(b.values()) for b in self.bags]
        self.avg = sum(self.lengths)/max(1,len(self.lengths))

    def public_docs(self):
        return [{k:v for k,v in d.items() if k not in ('path','chapters')} for d in self.docs.values()]

    def search(self, query, doc_id=None, limit=10):
        scores = defaultdict(float)
        words = set(tokens(query + ' ' + expand(query)))
        for word in words:
            indices = self.postings.get(word, [])
            idf = math.log(1+(len(self.bags)-len(indices)+.5)/(len(indices)+.5))
            for i in indices:
                if doc_id and self.passages[i]['doc'] != doc_id:
                    continue
                frequency = self.bags[i][word]
                scores[i] += idf*frequency*2.5/(frequency+1.5*(.25+.75*self.lengths[i]/max(1,self.avg)))
        result, seen = [], Counter()
        for i in sorted(scores, key=scores.get, reverse=True):
            p = self.passages[i]
            if seen[(p['doc'],p['page'])] >= 3:
                continue
            result.append({**p,'score':round(scores[i],3)})
            seen[(p['doc'],p['page'])] += 1
            if len(result) >= limit:
                break
        return result

    def page(self, doc_id, number):
        if (doc_id, number) not in self.pages:
            raise KeyError('Unknown document or PDF page')
        return self.pages[(doc_id,number)]
