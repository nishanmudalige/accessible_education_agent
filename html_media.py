"""Local, validated textbook images from publisher archives or paced downloads."""
import base64
from collections import defaultdict
import hashlib
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

IMAGE_SUFFIXES={'.svg','.png','.jpg','.jpeg','.gif','.webp','.avif'}

def image_suffix(data):
    if data.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
    if data.startswith(b'\xff\xd8\xff'): return '.jpg'
    if data.startswith((b'GIF87a',b'GIF89a')): return '.gif'
    if data[:4]==b'RIFF' and data[8:12]==b'WEBP': return '.webp'
    if b'ftypavif' in data[:32]: return '.avif'
    # Reject HTML error pages even when they have an image filename/content type.
    prefix=data.lstrip(b'\xef\xbb\xbf \r\n\t')
    if re.search(rb'<svg(?:\s|>)',prefix[:4096]) and b'<html' not in prefix[:4096].lower():
        return '.svg'
    raise ValueError('Response is not a supported image')

class MediaStore:
    def __init__(self,folder,book,fetch,archive=None,prefix=None):
        self.folder=folder;self.book=book;self.fetch=fetch
        self.assets=folder/'assets';self.assets.mkdir(exist_ok=True)
        self.manifest=folder/'media.json'
        self.records=json.loads(self.manifest.read_text()) if self.manifest.exists() else {}
        self.archive=ZipFile(archive) if archive else None
        self.names=defaultdict(list)
        if self.archive:
            for name in self.archive.namelist():
                if Path(name).suffix.lower() in IMAGE_SUFFIXES and (not prefix or '/'+prefix.strip('/')+'/' in '/'+name):
                    self.names[Path(name).name].append(name)

    def archived(self,url):
        path=unquote(urlsplit(url).path)
        matches=self.names.get(path.rsplit('/',1)[-1],[])
        if not matches:return None
        # Prefer the longest matching directory suffix, then reject ambiguous bytes.
        def score(name):
            left=name.split('/');right=path.split('/');n=0
            for a,b in zip(reversed(left),reversed(right)):
                if a!=b:break
                n+=1
            return n
        best=max(map(score,matches));matches=[n for n in matches if score(n)==best]
        blobs={hashlib.sha256(self.archive.read(n)).hexdigest():n for n in matches}
        if len(blobs)!=1:raise ValueError('Ambiguous archive image filename: '+url)
        name=next(iter(blobs.values()))
        return self.archive.read(name),'archive:'+name

    def store(self,data):
        suffix=image_suffix(data)
        name=hashlib.sha256(data).hexdigest()[:24]+suffix
        (self.assets/name).write_bytes(data)
        return '/book-assets/'+self.book+'/'+name

    def localize(self,candidates,alt):
        errors=[]
        candidates=list(dict.fromkeys(candidates))
        available=lambda u: (u in self.records and self.records[u]['status']=='ok') or bool(self.names.get(unquote(urlsplit(u).path).rsplit('/',1)[-1]))
        candidates=sorted(candidates,key=lambda u:not available(u))
        for source in dict.fromkeys(candidates):
            cached=self.records.get(source)
            if cached and (cached['status']=='ok' or not self.archive) and (self.assets/Path(cached['local_url']).name).is_file():
                return cached['local_url'],source
            try:
                if source.startswith('data:image/'):
                    header,value=source.split(',',1)
                    data=base64.b64decode(value) if ';base64' in header else unquote(value).encode()
                    provenance='inline-data'
                else:
                    archived=self.archived(source)
                    if archived:data,provenance=archived
                    else:
                        # Upgrade old WordPress HTTP links before making any request.
                        secure=re.sub('^http://','https://',source)
                        data=self.fetch.get_bytes(secure);provenance=secure
                local=self.store(data)
                self.records[source]={'status':'ok','local_url':local,'provenance':provenance}
                return local,source
            except Exception as error:
                errors.append(type(error).__name__+': '+str(error))
        # An unavailable original remains visibly identified, never an HTML error image.
        lines=['Original image unavailable.']
        if alt and alt.lower() not in ('image','picture','photo'): lines+=['Source alternative text: '+alt]
        words=' '.join(lines).split();rows=[];line=''
        for word in words:
            if len(line+' '+word)>86:rows.append(line);line=word
            else:line=(line+' '+word).strip()
        if line:rows.append(line)
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="760" height="'+str(40+26*len(rows))+'" viewBox="0 0 760 '+str(40+26*len(rows))+'"><rect width="100%" height="100%" fill="#fff5df"/><text x="18" y="30" font-family="sans-serif" font-size="16" fill="#342800">'+''.join('<tspan x="18" dy="'+('0' if i==0 else '26')+'">'+escape(row)+'</tspan>' for i,row in enumerate(rows))+'</text></svg>'
        local=self.store(svg.encode())
        source=candidates[0] if candidates else '(missing image source)'
        self.records[source]={'status':'unavailable','local_url':local,'alt':alt,'errors':errors}
        print('IMAGE UNAVAILABLE: '+source,flush=True)
        return local,source

    def save(self):
        self.manifest.write_text(json.dumps(self.records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if self.archive:self.archive.close()
