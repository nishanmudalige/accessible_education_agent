#!/usr/bin/env python3
"""Run locally against the actual Flask routes; no HTTP server is required."""
import argparse
from collections import defaultdict
import json
import logging
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--questions', type=Path, default=ROOT / 'benchmark/questions_calculus.json')
    parser.add_argument('--book', help='Override every question book ID')
    parser.add_argument('--limit', type=int, help='Run only the first N requests after expanding repeats')
    parser.add_argument('--interval', type=float, default=8.0, help='Seconds between Ask requests (default: 8)')
    parser.add_argument('--cold-runs', type=int, default=3, help='Separate full-library index builds (default: 3)')
    parser.add_argument('--page-runs', type=int, default=3, help='Uncached page renders (default: 3)')
    parser.add_argument('--page', type=int, default=1, help='PDF page to render (default: 1)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--offline-only', action='store_true', help='Only measure health, indexing and page rendering; no model requests')
    parser.add_argument('--plan-quality', action='store_true', help='Log planning output and retrieved block identifiers (may contain user input)')
    parser.add_argument('--defer-web', action='store_true', help='For web-enabled questions, request the book answer first and search separately')
    parser.add_argument('--skip-plan', choices=('on','off'), help='Override SKIP_PLAN for this benchmark process')
    args = parser.parse_args()
    if args.interval < 0 or args.cold_runs < 0 or args.page_runs < 0 or args.page < 1:
        parser.error('interval and run counts must be nonnegative, and page must be positive')
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be a positive integer')
    questions = json.loads(args.questions.read_text(encoding='utf-8'))
    if not isinstance(questions, list) or not questions:
        parser.error('questions must be a nonempty JSON array')
    for q in questions:
        if (not isinstance(q, dict) or not isinstance(q.get('book'), str) or not q['book']
            or not isinstance(q.get('question'), str) or not q['question'].strip()
            or q.get('question_language') not in ('en', 'fr') or q.get('reply_language') not in ('en', 'fr')
            or type(q.get('web')) is not bool or type(q.get('repeats')) is not int or q['repeats'] < 1):
            parser.error('invalid question entry: check book, question, languages, web, and repeats')
    requests = [(q, repeat) for q in questions for repeat in range(q['repeats'])]
    if args.limit is not None:
        requests = requests[:args.limit]
    count = len(requests)
    print(f'Planned /api/ask requests: {count}; interval: {args.interval:g}s; cold runs: {args.cold_runs}; page renders: {args.page_runs}')
    if args.dry_run:
        return 0

    sys.path.insert(0, str(ROOT))
    import app as application
    from retrieval import LibraryIndex
    from reader_backend import page_png
    from timing import log

    application.app.config['BENCHMARK_PLAN_QUALITY'] = args.plan_quality
    if args.skip_plan is not None:
        application.app.config['SKIP_PLAN'] = args.skip_plan == 'on'

    class Collector(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []
        def emit(self, record):
            message = record.getMessage()
            if message.startswith('[TIMING] '):
                self.records.append(json.loads(message[len('[TIMING] '):]))
    collector = Collector()
    log.addHandler(collector)
    client = application.app.test_client()
    start = time.perf_counter()
    response = client.get('/health')
    if response.status_code != 200:
        raise RuntimeError(f'Health check failed: HTTP {response.status_code}')
    print(f'Warm-up /health: {time.perf_counter()-start:.3f}s; excluded from questions')
    client.get('/')
    with client.session_transaction() as session:
        csrf = session['csrf']
    library = application.library()
    books = {args.book or q['book'] for q, _ in requests}
    missing = books - set(library.docs)
    if missing:
        raise ValueError(f'Unknown book IDs: {sorted(missing)}')
    if any(args.page > library.docs[book]['page_count'] for book in books):
        raise ValueError('Requested page is outside a selected book')

    print('Cold index runs (full collection, per-book times in [TIMING] logs):')
    cold = []
    cold_start = len(collector.records)
    for _ in range(args.cold_runs):
        start = time.perf_counter()
        index = LibraryIndex(ROOT / 'content/manifest.json')
        cold.append(time.perf_counter()-start)
        del index
    print('  full index median:', f'{statistics.median(cold):.3f}s' if cold else 'skipped')
    per_book = defaultdict(list)
    for event in collector.records[cold_start:]:
        if event.get('event') == 'book_index':
            per_book[event['book']].append(event['seconds'])
    for book, values in sorted(per_book.items()):
        print(f'  {book}: {statistics.median(values):.3f}s median (n={len(values)})')
    print('Uncached page rendering:')
    for book in sorted(books):
        times = []
        for _ in range(args.page_runs):
            page_png.cache_clear()
            start = time.perf_counter()
            response = client.get(f'/page-image/{book}/{args.page}')
            if response.status_code != 200:
                raise RuntimeError(f'Page render failed: HTTP {response.status_code}')
            times.append(time.perf_counter()-start)
        print(f'  {book}:', f'{statistics.median(times):.3f}s median client time' if times else 'skipped')

    if args.offline_only:
        print('Offline-only: no /api/ask or model requests sent')
        return 0

    groups = defaultdict(list)
    previous = None
    failures = 0
    for q, repeat in requests:
        book = args.book or q['book']
        if previous is not None:
            time.sleep(max(0, args.interval - (time.monotonic() - previous)))
        previous = time.monotonic()
        before = len(collector.records)
        start = time.perf_counter()
        response = client.post('/api/ask', json={'doc': book, 'question': q['question'],
            'language': {'en':'en-CA', 'fr':'fr-CA'}[q['reply_language']], 'web': q['web'] and not args.defer_web, 'history': []},
            headers={'X-CSRF-Token': csrf})
        elapsed = time.perf_counter()-start
        records = [r for r in collector.records[before:] if r.get('event') == 'ask']
        entry = dict(records[-1]) if records else {}
        entry['client'] = elapsed
        entry['http'] = response.status_code
        entry['category'] = (response.get_json(silent=True) or {}).get('category')
        entry['combined_client'] = elapsed
        result = response.get_json(silent=True) or {}
        if args.defer_web and q['web'] and response.status_code == 200 and result.get('web_token'):
            time.sleep(max(0, args.interval - (time.monotonic() - previous)))
            previous = time.monotonic()
            web_before = len(collector.records)
            web_start = time.perf_counter()
            response = client.post('/api/web-search', json={'token': result['web_token']}, headers={'X-CSRF-Token': csrf})
            web_elapsed = time.perf_counter()-web_start
            web_records = [r for r in collector.records[web_before:] if r.get('event') == 'web_search']
            entry['combined_client'] += web_elapsed
            entry['http'] = response.status_code
            if web_records:
                web_record = web_records[-1]
                entry['web'] = web_record['web']
                for name in ('tokens_in', 'tokens_out'):
                    entry[name] = entry.get(name, 0) + web_record.get(name, 0)
                entry['usage_unknown'] = entry.get('usage_unknown', True) or web_record.get('usage_unknown', True)
            else:
                entry['usage_unknown'] = True
            print(f'Separate web request: client={web_elapsed:.3f}s HTTP={response.status_code}')
        if response.status_code != 200:
            failures += 1
            print(f"FAILED HTTP {response.status_code}: {q['question']} (repeat {repeat+1})")
        groups[(q['question_language'], q['reply_language'], q['web'])].append(entry)
        print(f"Request {q['question_language']}/{q['reply_language']} web={q['web']} repeat={repeat+1}: client={elapsed:.3f}s server={entry.get('total', 'unknown')} HTTP={response.status_code}")
    print('\nGroup summaries (seconds; skipped stages excluded from medians):')
    total_in = total_out = unknown = 0
    for key, entries in sorted(groups.items()):
        parts = []
        for name in ('plan', 'retrieve', 'answer', 'web', 'total', 'client', 'combined_client'):
            values = [e[name] for e in entries if isinstance(e.get(name), (float, int))]
            parts.append(f'{name}={statistics.median(values):.3f}s (n={len(values)})' if values else f'{name}=skipped')
        tin = sum(e.get('tokens_in', 0) for e in entries)
        tout = sum(e.get('tokens_out', 0) for e in entries)
        missing_usage = sum(e.get('http') != 200 or e.get('usage_unknown', True) for e in entries)
        total_in += tin; total_out += tout; unknown += missing_usage
        print(f'{key}: '+ ' '.join(parts)+f' tokens_in={tin} tokens_out={tout} usage_unknown={missing_usage}')
    print(f'Total known tokens: input={total_in} output={total_out} total={total_in+total_out}; requests with unknown usage={unknown}; failed requests={failures}')
    return 1 if failures else 0

if __name__ == '__main__':
    raise SystemExit(main())
