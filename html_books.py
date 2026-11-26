"""Load local, sanitized HTML book snapshots into the shared retrieval index."""
import json
from pathlib import Path

def load_html_book(root, entry):
    path=(root / entry['file']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Missing or unsafe HTML book index')
    saved=json.loads(path.read_text(encoding='utf-8'))
    chapters=saved['chapters']
    for chapter in chapters:
        target=(path.parent / chapter['file']).resolve()
        if not target.is_relative_to(path.parent) or not target.is_file():
            raise ValueError('Missing or unsafe HTML chapter')
    toc=[{'level':1,'title':c['title'],'page':i,'chapter':c['id'],
          'url':f"/book/{entry['id']}/{c['id']}"} for i,c in enumerate(chapters,1)]
    doc={**entry,'path':path,'chapters':chapters,'chapter_count':len(chapters),'page_count':len(chapters),'toc':toc}
    media_path=path.with_name('media.json')
    media=json.loads(media_path.read_text(encoding='utf-8')) if media_path.is_file() else {}
    pages={}
    passages=[]
    for number,chapter in enumerate(chapters,1):
        records=[{**p,'doc':entry['id'],'page':number,'chapter':chapter['id'],
                  'chapter_title':chapter['title'],'format':'html','rects':[],
                  'label':chapter['title']} for p in chapter['passages']]
        for record in records:
            for image in record.get('images', []):
                asset=media.get(image.get('source_url'), {})
                image['available']=(asset.get('status')=='ok' and
                                    asset.get('local_url')==image.get('local_url'))
        pages[(entry['id'],number)]=records
        passages.extend(records)
    return doc,pages,passages
