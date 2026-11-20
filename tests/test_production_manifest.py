from pathlib import Path
import json
import pytest
import app as module
from retrieval import LibraryIndex

ROOT=Path(__file__).resolve().parents[1]

def test_production_never_loads_benchmark_pdf():
    index=module.library()
    assert 'active-calculus-pdf' not in index.docs
    assert len(index.docs)==4
    assert all(p['doc']!='active-calculus-pdf' for p in index.passages)
    client=module.create_app({'TESTING':True,'SECRET_KEY':'production'}).test_client()
    assert b'active-calculus-pdf' not in client.get('/').data
    assert client.get('/pdf/active-calculus-pdf').status_code==404
    assert client.get('/health').json['documents']==4

def test_benchmark_manifest_retains_pdf_without_production_mutation():
    index=module.library(ROOT/'content/manifest.benchmark.json')
    assert index.docs['active-calculus-pdf']['page_count']==593
    assert index.search('derivative','active-calculus-pdf')
    assert 'active-calculus-pdf' not in module.library().docs

def test_manifest_inheritance_rejects_escaping_paths_and_cycles(tmp_path):
    manifest=tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'extends':'../other.json','documents':[]}))
    with pytest.raises(ValueError):LibraryIndex(manifest)
    manifest.write_text(json.dumps({'extends':'manifest.json','documents':[]}))
    with pytest.raises(ValueError):LibraryIndex(manifest)
