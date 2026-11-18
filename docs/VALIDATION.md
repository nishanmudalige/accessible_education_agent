# Delivery validation — 18 November 2026

## Completed checks

- Python 3.12.14; installed runtime requirements are pinned in `requirements.txt`.
- `pip check`: no broken requirements in the test environment after removing unrelated optional packages.
- **22 automated Python tests passed.** The tests exercise the real PDF/retrieval and Flask integration; paid AI calls are mocked.
- The original supplied PDF is indexed in full: **422 pages**, **12 chapter/appendix bookmarks**, **3,624 searchable source blocks**. The PDF is not rewritten.
- English and French retrieval checks returned relevant matching text for confidence intervals, standard deviation and the Poisson distribution.
- Reader links resolve to the exact source block used by retrieval; the page image route produces a PNG, with overlays drawn from the same block's line coordinates.
- Scope/provenance tests cover unrelated requests, unsupported answers, unknown model citation keys, explicit web-off mode, and retaining a valid book answer when external search fails.
- Login, protected PDF/API access, blank-password spend prevention, CSRF, translation input limits, language routing, request limits and sanitized provider errors were tested.
- A temporary two-subject index verified independent document retrieval and rejection of paths outside `content/`.
- JavaScript syntax checks passed for all three browser scripts.
- DOM interaction checks with jsdom passed for local results, query highlighting, French interface labels, display preferences, safe plain-text answer rendering, book citation destinations, Unicode-aware external citation rendering, translation controls, sentence-highlight DOM updates, speech pause/resume, `fr-CA` voice preference, and reader image/highlight toggles. Browser speech and HTTP responses were mocked in those DOM checks.
- The Render YAML and manifest were parsed, the archive was inspected for excluded files, and the included PDF was compared byte-for-byte to the upload during packaging.

## Not verified in this environment

No OpenAI API key was available to this build. **Live GPT-6.2 Astra answers, GPT-6.1 Sol query planning/translation and live web-search results have not been exercised.** The exact model IDs and API patterns were checked against official OpenAI documentation, but account-specific access, live response quality, latency and cost require your key. Run:

```bash
python scripts/check_models.py
python scripts/check_models.py --smoke
```

The second command makes short billable requests to all relevant API functions. Review Canadian French terminology and the semantic support of answers with real examples; a mechanically valid citation does not prove a correct interpretation.

A full graphical browser session could not be launched because the environment blocked Chromium's process-singleton socket. DOM interactions were checked instead. **Rendered desktop/mobile appearance, actual voice output, installed voice inventory, browser-specific speech behaviour and screen-reader operation remain manual checks.** No WCAG certification or complete accessible mathematical edition is claimed.

No repository was created in your GitHub account and no Render service was provisioned. The package includes the exact commands and service configuration for those steps. Render account permissions, free-plan availability and runtime behaviour need verification during deployment.

## Repeatable offline checks

From the project directory, after installing `requirements-dev.txt`:

```bash
python scripts/check_content.py
python -m pytest -q
```

If Node is installed, syntax can also be checked without installing frontend packages:

```bash
node --check static/common.js
node --check static/app.js
node --check static/reader.js
```

Use the walkthrough in the README to test real speech, translation, provenance and keyboard access after deployment.

## Local access fix

The local `.env` now takes precedence over inherited shell variables; Render retains environment precedence. Error messages distinguish HTTP 401, 403, 404 and 429 and expose only safe machine-readable provider codes. A direct Responses diagnostic avoids requiring permission to list models. Tests cover local/Render messages, credential redaction and local `.env` precedence. Live API diagnosis still needs the user’s key.
