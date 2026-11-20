#!/usr/bin/env python3
"""Import an authorized PreTeXt or Pressbooks book, one chapter request at a time."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urljoin, urlsplit, urldefrag, unquote
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup, Comment, NavigableString

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from html_media import MediaStore, image_suffix

BOXES='.theorem, .theorem-like, .assemblage, .definition, .definition-like, .example, .example-like, .textbox, .text-box, .bcc-box'
ATOMIC=BOXES+', table'
PARAGRAPHS='p, div.para, dt, dd, li, .displaymath, figure, img'
DROP='script, style, nav, footer, form, iframe, object, embed, button, input, link, meta, base, .autopermalink, .heading-permalink, .print-preview-header, .print-controls, .print-links, .material-symbols-outlined, .summary-links, .screen-reader-text, .visually-hidden, .share-buttons, .social-media'
ALLOWED=set('section article div span p h1 h2 h3 h4 h5 h6 ul ol li dl dt dd table thead tbody tfoot tr th td caption blockquote pre code em strong b i u s sub sup br hr a img figure figcaption details summary abbr math semantics annotation mrow mi mn mo mfrac msqrt mroot msub msup msubsup munder mover munderover mtable mtr mtd mtext mspace'.split())

def normalized(text):
    return re.sub(r'\s+',' ',text).strip()

def safe_url(url,base):
    result=urljoin(base,url)
    return result if urlsplit(result).scheme in ('http','https') else None

def chapter_links(soup,url,kind):
    selector='#ptx-toc a[href]' if kind=='pretext' else '.toc a[href], #toc a[href], .table-of-contents a[href]'
    base=urlsplit(url)
    prefix=base.path.rsplit('/',1)[0]+'/' if kind=='pretext' else base.path.rstrip('/')+'/'
    found={}
    for a in soup.select(selector):
        target=urldefrag(urljoin(url,a['href']))[0]
        parts=urlsplit(target)
        if parts.netloc!=base.netloc or not parts.path.startswith(prefix): continue
        if kind=='pretext' and not parts.path.endswith('.html'): continue
        if kind=='pressbooks' and not any(x in parts.path for x in ('/chapter/','/front-matter/','/back-matter/','/part/')): continue
        found.setdefault(target,normalized(a.get_text(' ',strip=True)))
    return found

def srcset_urls(value):
    entries=[]
    for item in value.split(','):
        parts=item.strip().split()
        if not parts: continue
        size=float(parts[1][:-1]) if len(parts)>1 and re.fullmatch(r'(?:\d+(?:\.\d+)?|\.\d+)[wx]',parts[1]) else 0
        entries.append((size,parts[0]))
    return [url for _,url in sorted(entries,reverse=True)]

def image_urls(node,url):
    candidates=[]
    for key in ('data-srcset','data-lazy-srcset'):
        candidates.extend(srcset_urls(node.get(key,'')))
    candidates.extend(node.get(k,'') for k in ('data-src','data-lazy-src','data-original'))
    picture=node.find_parent('picture')
    if picture:
        for source in picture.select('source'):
            candidates.extend(srcset_urls(source.get('data-srcset') or source.get('srcset','')))
    candidates.extend(srcset_urls(node.get('srcset','')))
    candidates.append(node.get('src',''))
    resolved=[]
    for candidate in candidates:
        if not candidate: continue
        target=candidate if candidate.startswith('data:image/') else safe_url(candidate,url)
        if target and target not in resolved: resolved.append(target)
    # A lazy-loading transparent data URL must not override a real image.
    return [x for x in resolved if not x.startswith('data:')]+[x for x in resolved if x.startswith('data:')]

def evidence_text(node):
    if isinstance(node,NavigableString): return normalized(str(node))
    if node.name=='img': return normalized(node.get('alt',''))
    if node.name=='table':
        rows=[]
        caption=node.find('caption',recursive=False)
        if caption: rows.append(evidence_text(caption))
        for row in node.select('tr'):
            if row.find_parent('table') is node:
                rows.append(' | '.join(evidence_text(c) for c in row.find_all(['th','td'],recursive=False)))
        return '\n'.join(rows)
    return ' '.join(filter(None,(evidence_text(child) for child in node.children)))

def clean_chapter(raw,url,kind,media=None):
    soup=BeautifulSoup(raw,'html.parser')
    title=soup.select_one('.entry-title, main h1, main h2')
    title=normalized(title.get_text(' ',strip=True)) if title else normalized(soup.title.get_text())
    body=soup.select_one('.ptx-content') if kind=='pretext' else soup.select_one('.entry-content')
    if body is None: raise ValueError(f'No {kind} chapter body at {url}')
    macros=soup.select_one('#latex-macros')
    if macros and not body.select_one('#latex-macros'):
        body.insert(0,macros.extract())
    for script in list(body.select('script[type^="math/tex"]')):
        inline='mode=display' not in script.get('type','')
        script.replace_with(('\\(' if inline else '\\[')+script.get_text()+('\\)' if inline else '\\]'))
    for math in list(body.select('math')):
        tex=math.select_one('annotation[encoding="application/x-tex"]')
        if tex: math.replace_with('\\('+tex.get_text()+'\\)')
    # Keep image objects instead of deleting their fallback images with the object.
    for obj in list(body.select('object')):
        child=obj.find('img')
        if child: obj.replace_with(child.extract())
        elif obj.get('type','').startswith('image/') and obj.get('data'):
            image=soup.new_tag('img',src=obj['data'],alt=obj.get('aria-label',''))
            obj.replace_with(image)
    for bad in list(body.select(DROP)): bad.decompose()
    image_metadata={}
    for image in list(body.select('img')):
        candidates=image_urls(image,url)
        alt=normalized(image.get('alt',''))
        if media:
            local,source=media.localize(candidates,alt)
            image['src']=local
            image_metadata[id(image)]={'source_url':source,'local_url':local,'alt':alt}
        elif candidates:
            image['src']=candidates[0]
        else:
            image['alt']=alt or 'Image source unavailable'
            image.attrs.pop('src',None)

    heading=body.select_one('h1')
    if heading: title=normalized(heading.get_text(' ',strip=True))
    for comment in body.find_all(string=lambda x:isinstance(x,Comment)): comment.extract()
    for node in list(body.find_all(True)):
        if node.name not in ALLOWED:
            node.unwrap();continue
        for key in list(node.attrs):
            if key not in ('id','class','href','src','alt','title','colspan','rowspan','scope','open','lang','display','encoding','width','height'):
                del node[key]
        if node.name=='a':
            target=safe_url(node.get('href',''),url)
            if target: node['href']=target
            elif 'href' in node.attrs: del node['href']
        if node.name=='img':
            target=node.get('src')
            if target:
                node['src']=target if media else safe_url(target,url)
                node['loading']='lazy'
    # Original IDs stay metadata; generated IDs are stable for text and duplicate order.
    seen=set()
    for node in body.select('[id]'):
        if node['id'] in seen: del node['id']
        else: seen.add(node['id'])
    atomic={id(node) for node in body.select(ATOMIC)}
    candidates=body.select(ATOMIC+', '+PARAGRAPHS+', div')
    records=[];duplicates=Counter();selected=set()
    for node in candidates:
        parents=list(node.parents)
        if node.get('id')=='latex-macros' or any(p.get('id')=='latex-macros' for p in parents): continue
        if any('index' in p.get('class',[]) for p in [node]+parents): continue
        if any(id(parent) in atomic or id(parent) in selected for parent in parents): continue
        is_atomic=id(node) in atomic
        if not is_atomic and node.select(ATOMIC): continue
        if node.name=='div' and 'para' not in node.get('class',[]) and not is_atomic and node.select(PARAGRAPHS+', div'):
            continue
        text=evidence_text(node).strip()
        heading=node.find_previous(['h1','h2','h3','h4','h5','h6'])
        section=normalized(heading.get_text(' ',strip=True)) if heading and body in heading.parents else ''
        # Tables and image examples need their original section heading to retain meaning.
        images=([node] if node.name=='img' else node.select('img'))
        if section and (node.name=='table' or images) and text:
            text=section+'\n'+text
        context=[]
        if node.name=='table':
            # Keep the source's tense/usage explanation beside the complete paradigm.
            for previous in node.previous_siblings:
                if not getattr(previous,'name',None): continue
                if previous.name in ('h1','h2','h3','h4','h5','h6','table') or previous.select('table'): break
                value=evidence_text(previous).strip()
                if value:
                    if len(value)>1400: break
                    context.insert(0,value)
                if len(context)>=3: break
            if context: text='\n'.join(context)+'\n'+text
        text=re.sub(r'\[latex\](.*?)\[/latex\]',lambda m:'\\('+m[1]+'\\)',text,flags=re.S)
        if not text:continue
        selected.add(id(node))
        original=node.get('id')
        anchor=original
        if not anchor:
            digest=hashlib.sha256(text.encode()).hexdigest()[:16];duplicates[digest]+=1
            anchor=f'paragraph-{digest}-{duplicates[digest]}'
            while anchor in seen: anchor+='-local'
            seen.add(anchor);node['id']=anchor
        node['data-evidence']='true'
        kind_name='table' if node.name=='table' else ('box' if is_atomic else ('image' if node.name=='img' else 'paragraph'))
        record={'id':anchor,'text':text,'source_url':url,'source_anchor':original,'kind':kind_name}
        if section: record['section_title']=section
        if context: record['context']=context
        if images: record['images']=[image_metadata.get(id(i),{'source_url':i.get('src'),'alt':i.get('alt','')}) for i in images]
        records.append(record)
    # Preserve common Pressbooks [latex] delimiters for browser MathJax as well.
    output=str(body)
    output=re.sub(r'\[latex\](.*?)\[/latex\]',lambda m:'\\('+m[1]+'\\)',output,flags=re.S)
    return title,output,records

def export_chapters(raw,base):
    """Split the publisher's complete Pressbooks XHTML export in TOC order."""
    soup=BeautifulSoup(raw,'html.parser')
    if not soup.select_one('#toc'): raise ValueError('Not a complete Pressbooks XHTML export')
    nodes=[]
    for a in soup.select('#toc a[href^="#"]'):
        node=soup.find(id=a['href'][1:])
        if node and node.name=='div' and node not in nodes: nodes.append(node)
    mapping={}
    for node in nodes:
        ident=node['id']
        for prefix in ('front-matter-','back-matter-','chapter-','part-'):
            if ident.startswith(prefix):
                url=urljoin(base,prefix[:-1]+'/'+ident[len(prefix):]+'/');break
        else: raise ValueError('Unrecognized exported chapter identifier')
        mapping[ident]=url
    anchors={child['id']:mapping[node['id']] for node in nodes for child in node.select('[id]')}
    for node in nodes:
        for a in node.select('a[href^="#"]'):
            ident=a['href'][1:]
            if ident in mapping: a['href']=mapping[ident]
            elif ident in anchors: a['href']=anchors[ident]+'#'+ident
        title=node.get('title') or normalized(node.select_one('h1,h2,h3').get_text(' ',strip=True))
        wrapper=BeautifulSoup('<main><h1 class="entry-title"></h1><div class="entry-content"></div></main>','html.parser')
        wrapper.h1.string=title
        wrapper.select_one('.entry-content').append(node)
        yield mapping[node['id']],str(wrapper)

class Fetcher:
    def __init__(self,cache,interval): self.cache=cache;self.interval=interval;self.last=None
    def get_bytes(self,url):
        key=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.image')
        if key.exists():return key.read_bytes()
        if self.last is not None:time.sleep(max(0,self.interval-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        req=Request(url,headers={'User-Agent':'AccessEdu-Textbook-Importer/1.0 (educational offline reading)'})
        with urlopen(req,timeout=60) as response:data=response.read()
        image_suffix(data)
        key.write_bytes(data)
        return data

    def get(self,url):
        key=self.cache/(hashlib.sha256(url.encode()).hexdigest()+'.html')
        if key.exists():return key.read_text(encoding='utf-8')
        if self.last is not None:time.sleep(max(0,self.interval-(time.monotonic()-self.last)))
        self.last=time.monotonic()
        req=Request(url,headers={'User-Agent':'AccessEdu-Textbook-Importer/1.0 (educational offline reading)'})
        with urlopen(req,timeout=60) as response: raw=response.read().decode('utf-8')
        if 'Just a moment...' in raw or 'Request blocked.' in raw:raise ValueError(f'Website access blocked: {url}')
        key.write_text(raw,encoding='utf-8')
        return raw

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',required=True);p.add_argument('--url',required=True)
    p.add_argument('--kind',choices=['pretext','pressbooks'],required=True)
    p.add_argument('--interval',type=float,default=1.5)
    p.add_argument('--media-archive',type=Path,help='Official EPUB or published ZIP containing original image files')
    p.add_argument('--media-prefix',help='Restrict ZIP images to this directory, e.g. html2e')
    p.add_argument('--export-file',type=Path,help='Official Pressbooks XHTML export saved through a browser; avoids refetching blocked chapter pages')
    args=p.parse_args()
    if not re.fullmatch('[a-z0-9-]+',args.id) or args.interval<1:p.error('Use a slug ID and an interval of at least one second')
    folder=ROOT/'content'/args.id;folder.mkdir(parents=True,exist_ok=True)
    cache=folder/'raw';cache.mkdir(exist_ok=True)
    fetch=Fetcher(cache,args.interval)
    media=MediaStore(folder,args.id,fetch,args.media_archive,args.media_prefix)
    if args.export_file:
        if args.kind!='pressbooks':p.error('--export-file is only for Pressbooks')
        raw=args.export_file.read_text(encoding='utf-8')
        (folder/'source.xhtml').write_text(raw,encoding='utf-8')
        exported=dict(export_chapters(raw,args.url))
        links={url:'' for url in exported}
    else:
        raw=fetch.get(args.url);soup=BeautifulSoup(raw,'html.parser')
        links=chapter_links(soup,args.url,args.kind)
        exported={}
    if not links:raise ValueError('No chapter directory found; use the full PreTeXt frontmatter URL or Pressbooks book home')
    chapters=[]
    for url,label in links.items():
        raw=exported[url] if args.export_file else (raw if url==args.url else fetch.get(url))
        title,html,records=clean_chapter(raw,url,args.kind,media)
        slug=re.sub(r'[^a-zA-Z0-9_-]','-',urlsplit(url).path.rstrip('/').split('/')[-1].removesuffix('.html'))
        filename=slug+'.html';(folder/filename).write_text(html,encoding='utf-8')
        chapters.append({'id':slug,'file':filename,'title':title or label,'source_url':url,'passages':records})
        print(f'{args.id}: {len(chapters)}/{len(links)} {slug} ({len(records)} blocks)',flush=True)
    # Rewrite internal links only after the full directory is known.
    local={c['source_url']:f"/book/{args.id}/{c['id']}" for c in chapters}
    for c in chapters:
        path=folder/c['file'];soup=BeautifulSoup(path.read_text(),'html.parser')
        for a in soup.select('a[href]'):
            url,anchor=urldefrag(a['href'])
            if url in local:a['href']=local[url]+('#'+anchor if anchor else '')
            elif url in media.records:a['href']=media.records[url]['local_url']
        path.write_text('\n'.join(line.rstrip() for line in str(soup).splitlines())+'\n',encoding='utf-8')
    media.save()
    unavailable=sum(r['status']!='ok' for r in media.records.values())
    print(f'Local media: {len(media.records)} sources; unavailable originals: {unavailable}',flush=True)
    index=folder/'book.json'
    index.write_text(json.dumps({'source_url':args.url,'kind':args.kind,'import_method':'official_xhtml_export' if args.export_file else 'chapter_crawl','chapters':chapters},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Saved {len(chapters)} chapters to {index}',flush=True)

if __name__=='__main__':main()
