# Local benchmark

Run from the repository root after installing `requirements-dev.txt` and setting `OPENAI_API_KEY` in `.env`. This runs the real Flask routes in a local test client; it measures local processing and OpenAI latency, not a deployed Render instance or Internet round trip to Render. It does not start an HTTP server. A live run incurs OpenAI charges.

```sh
python benchmark/run.py --dry-run
python benchmark/run.py --limit 1  # one Ask request; may make multiple model calls
python benchmark/run.py --offline-only
python benchmark/run.py --book active-calculus-pdf
```

The default 8-second interval spaces the start of Ask requests to stay under the default 8-per-minute in-process limit. Set `--interval 10` for a wider margin or change `REQUESTS_PER_MINUTE` in `.env` before running. Provider rate limits still apply. A failed request is reported and causes a nonzero exit; there are no retries.

The script first calls `/health` to build the index, outside all question timings. It then measures three independent full-library index builds and three uncached renders per selected book by default. Use `--cold-runs`, `--page-runs`, and `--page` to change these. Per-book index measurements appear in `[TIMING]` logs; full index and client-side PNG times appear in the summary. These repeated in-process builds do not include process or Render cold-start time and may benefit from OS file caches. Each build includes all books in the manifest.

Each Ask logs per-stage server time and per-call token usage without question text. The summary also shows client request time, group medians, known token totals, and missing usage counts. `null` stages were skipped. If a request or provider response fails, its full token consumption may be unknown. Logs go to stderr; redirect both streams to save the complete report.

Use `--questions path/to/questions.json` to choose a question file and `--book BOOK_ID` to override its book IDs for a comparison. For example, once an HTML adapter and manifest entry exist, the same questions can be run with its ID. Languages in the file are `en` or `fr`; the reply language is mapped to the API's `en-CA` or `fr-CA`. Question language is a grouping label; the question text itself is sent unchanged.

`--limit N` runs the first N requests in file order after expanding each question’s repeats; it also limits the count shown by `--dry-run`. Omit it to run all requests. Pre-warm and offline index/page measurements still run unless disabled with `--cold-runs 0 --page-runs 0`.

To compare planning quality, pass `--plan-quality` to explicitly log the planner's related decision, language and search terms, together with the final retrieved document/page/block IDs. These logs can contain user-provided information; ordinary service requests do not enable them. Model timing logs include `reasoning_tokens` when the API returns it (otherwise `null`); reasoning tokens are a subset of output tokens and must not be added to the total again.

## On-demand web search (stage one)

`WEB_SEARCH_DEFAULT=off` is the application default. Set it to `on` in `.env` and restart to preselect the homepage checkbox and enable web search when API callers omit `web`. The browser always obtains the book answer first, then sends a separate `/api/web-search` request if the user selected automatic web search or clicks **Search the web**. The signed search request expires after 15 minutes and is bound to the current session. No second planning call is made. If it expires, ask the original question again.

The question file's explicit `web` field overrides the application default. Without `--defer-web`, the benchmark retains the synchronous API path for comparison. With `--defer-web`, web-enabled entries call the same independent endpoint as the browser, after the book answer. The configured interval also applies before separate web requests to respect the rate limit; that intentional wait is excluded from `combined_client`, which sums the two request durations:

```sh
python benchmark/run.py --questions benchmark/questions_calculus.json --cold-runs 0 --page-runs 0 2>&1 | tee benchmark/web_inline.log
python benchmark/run.py --questions benchmark/questions_calculus.json --cold-runs 0 --page-runs 0 --defer-web 2>&1 | tee benchmark/web_deferred.log
```

Both commands incur model usage. In the `web=True` group, `client` and `total` measure the initial Ask request, `web` measures the search stage, and `combined_client` measures both requests combined. In deferred mode token totals include both requests. Their combined duration is not expected to shrink merely from splitting the requests; the book answer becomes available sooner. `questions_plan.json` has web disabled for every entry, so it measures book-only speed and is not a web-on/off comparison.

Manual browser check: run `python app.py`, open http://127.0.0.1:5000, select a book and ask a related question. The web checkbox starts unchecked; the textbook answer should offer the web button. Clicking it should populate a separate external section while keeping the textbook answer. Use the browser Network panel to confirm one `/api/ask` followed by `/api/web-search` and no second Ask. Check a related unsupported question for the emphasized button, an unrelated question for no web button, and a checked checkbox for automatic follow-up search. Error messages leave the button available for another attempt. Run `node tests/web_ui.cjs` for mocked UI interactions without model usage.

## Optional planning fast path

`SKIP_PLAN=off` is the default: all questions use model planning. Set `SKIP_PLAN=on` to experimentally enable raw-question BM25 search when local conservative detection recognizes English, the reply language is English or automatic, and the request has no history. French, mixed or uncertain language and follow-ups retain model planning. Browser testing found that “What is a limit” could return an unverified answer without query expansion while planning answered it correctly, so the fast path remains opt-in. This heuristic can send some English input through planning; it does not make a language-model request to detect language. The answer schema now includes `related`, and the answer model receives the selected document subjects to distinguish unrelated requests from related-but-unsupported questions. A valid selected page request bypasses the lexical score gate, preserving page explanation requests.

`SKIP_PLAN_MIN_SCORE=1.0` is a provisional low-match gate used only on the fast path. A raw BM25 top score below it returns the existing outside-subjects response without a model call. On the current two-book corpus with Active Calculus selected, the three English calculus questions score 5.698, 18.903 and 14.335. The weather question scores 7.958, above the derivative question: no single score threshold separates this small sample. The conservative threshold therefore only removes very weak/no matches; it does NOT reliably identify off-topic questions. Related topics with no lexical overlap can be rejected, and scores change with corpus size/content. Use `SKIP_PLAN=off` to restore planning for all questions. No semantic classifier or embedding was added.

With `--plan-quality`, logs include `plan_skipped`, `top_score`, and the scope source (`bm25_gate`, `answer` or `planner`). On skipped requests, the English query is the original question, the French query is empty, and `related` is the answer model's final decision or the lexical gate's decision. The regular Ask timing summary includes `plan_skipped`; `plan=null` means no planning call was made.

Compare without editing `.env` (these are paid runs):

```sh
python benchmark/run.py --questions benchmark/questions_plan.json --plan-quality --skip-plan off --cold-runs 0 --page-runs 0 2>&1 | tee benchmark/skip_plan_off.log
python benchmark/run.py --questions benchmark/questions_plan.json --plan-quality --skip-plan on --cold-runs 0 --page-runs 0 2>&1 | tee benchmark/skip_plan_on.log
```

`--skip-plan` overrides the environment for that benchmark process only. For the browser, edit `.env` and restart the server. The English initial questions exercise the fast path; the two French questions retain planning. These commands do not measure streaming.

## HTML books and isolated index measurements

HTML snapshots are imported by `scripts/import_html.py` from a PreTeXt frontmatter directory or a Pressbooks home page. Downloads are sequential with a default 1.5-second interval; raw responses are cached under `content/BOOK/raw/` (not committed). A completed `book.json` contains chapter titles, paragraph text, source chapter URLs and original/local anchor IDs. Paragraphs lacking a source ID receive a SHA-256 text-based ID plus a duplicate counter; it locates the exact paragraph in this saved snapshot, while the original URL links to the source chapter without inventing a source fragment. Re-importing the same snapshot preserves IDs. MathJax 3.2.2 and fonts are local; images are stored locally and interactive embeds are omitted in favor of the original chapter link. Import sanitizes scripts and event attributes.

```sh
python scripts/import_html.py --id active-calculus-html --kind pretext --url https://mattboelkins.github.io/active-calculus-single-mbx/html2e/frontmatter.html
python benchmark/run.py --offline-only --book active-calculus-pdf --index-book active-calculus-pdf
python benchmark/run.py --offline-only --book active-calculus-html --index-book active-calculus-html
```

`--index-book` isolates measured index rebuilds to that book. Initial `/health` warm-up still loads the full collection and is reported separately. Without `--index-book`, per-book logs still show each book's time. HTML page measurements time serving a saved chapter, not browser MathJax layout. An HTML `page` value is a chapter ordinal, not a printed page. Existing PDF reading is unchanged.

For a Pressbooks site that blocks automated requests, use its **Download this book → XHTML** export in your browser, then import the complete official HTML export locally. This uses the publisher's full table of contents and reconstructs canonical chapter URLs from its chapter/front-matter/back-matter slugs; it does not substitute another edition. Example:

```sh
python scripts/import_html.py --id writing-for-success-html --kind pressbooks --url https://opentextbc.ca/writingforsuccess/ --export-file /path/to/official-export.html
```

The original export is retained as `source.xhtml` alongside sanitized chapters. Only chapter files named by `book.json` are served by the local book route. Remote downloads use pacing; processing an already-downloaded export makes no further network requests.

Three HTML book IDs are available: `active-calculus-html` (69 TOC pages), `writing-for-success-html` (14 pages from the official 2021 XHTML export) and `liberte1-html` (30 TOC entries from the official 2025 XHTML export). `benchmark/questions_html_smoke.json` contains two questions per book with explicit book IDs and no web search. To run the six paid smoke questions, omit `--book` so each entry selects its own book:

```sh
python benchmark/run.py --questions benchmark/questions_html_smoke.json --plan-quality --skip-plan off --cold-runs 0 --page-runs 0
```

Use `--limit 1 --dry-run` to preview a single request. The provided calculus questions test calculus; Writing for Success tests writing/grammar; Liberté tests beginner French. No live model calls were made during import validation; automated tests mock model outputs and verify retrieval and local evidence links.

## Re-importing images, tables and teaching boxes

HTML imports now store every displayed image under `content/BOOK/assets/` and serve it through `/book-assets/BOOK/FILENAME`. `media.json` records the source URL, local file, archive member/provenance and any unavailable original. The importer resolves relative URLs, prefers real lazy-image sources (`data-src`, `data-lazy-src`, `data-original`) over placeholders, chooses a usable `srcset`/`picture` candidate, and removes remote responsive/lazy attributes after localization. Direct image links are rewritten as well. Invalid HTML error responses are rejected instead of being saved as image files. Asset filenames use content hashes; existing downloaded files are reused on re-import.

To avoid hundreds of requests to the book sites, images can be read from the publisher's official EPUB or published GitHub ZIP. Examples for an initial image import:

```sh
python scripts/import_html.py --id active-calculus-html --kind pretext --url https://mattboelkins.github.io/active-calculus-single-mbx/html2e/frontmatter.html --media-archive /path/to/published-gh-pages.zip --media-prefix html2e
python scripts/import_html.py --id writing-for-success-html --kind pressbooks --url https://opentextbc.ca/writingforsuccess/ --export-file content/writing-for-success-html/source.xhtml --media-archive /path/to/official-writing.epub
python scripts/import_html.py --id liberte1-html --kind pressbooks --url https://pressbooks.atlanticoer-relatlantique.ca/liberte1/ --export-file content/liberte1-html/source.xhtml --media-archive /path/to/official-liberte.epub
```

Network fallbacks still use the configured request interval. Published source archives are only used as image sources; chapter text continues to come from the original HTML/XHTML snapshots. After a successful import, local `media.json` and assets are enough for subsequent imports without the archive. Known unavailable images also reuse their marked placeholders rather than repeatedly requesting broken URLs.

All image alternative text is included in evidence text, including image-only examples. Tables remain complete chunks with caption, row/cell boundaries, the source section heading and nearby explanatory text. PreTeXt theorem/definition/assemblage/example blocks and Pressbooks textboxes remain complete evidence blocks; their child paragraphs/formulas are not separately disconnected. Ordinary nested paragraphs preserve their surrounding text as well. Index/navigation items are not evidence. Local citations still point at the actual block, table or image-containing paragraph, not a made-up source fragment.

The repaired snapshots contain 421 Active Calculus image sources, 105 Writing sources and 235 Liberté sources. All are served locally. Two Writing originals (`image1.jpeg`, `image21.jpeg`) return 404 in the original site and are also marked `#fixme`/missing in its official EPUB. Their local placeholders explicitly say the original is unavailable; `image21` retains the full source alternative-text example. `image1` only has the non-descriptive alternative text “image,” so its original visual content could not be recovered.

`benchmark/questions_html_regression.json` contains the three reported failure questions, one request each. Offline regression tests verify complete evidence reaches the answer adapter and citations resolve locally; they mock the models. For an actual paid model check:

```sh
python benchmark/run.py --questions benchmark/questions_html_regression.json --plan-quality --skip-plan off --cold-runs 0 --page-runs 0
```
