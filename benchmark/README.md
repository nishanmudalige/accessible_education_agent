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
