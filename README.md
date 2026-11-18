# AccessÉdu — accessible education agent

An independent English ↔ Canadian French demonstration of source-grounded learning, translation and read-aloud. Suggested GitHub repository: **`access-edu-agent`**. The name stays useful when you add other subjects.

The supplied **OpenIntro Statistics, Fourth Edition** PDF is already included and indexed: **422 PDF pages, 12 chapter/appendix bookmarks, 3,624 searchable text blocks**. No vector database or manual file upload to OpenAI is required.

## What is included

- Textbook questions in English and Canadian French, with automatic or explicit reply language.
- GPT-6.1 Sol expands/translates the query; local BM25 finds real PDF passages; GPT-6.2 Astra writes a source-supported answer.
- **Green: From the source.** Citation links open the supporting block in a selectable reader. The original page-image view overlays the same source-block coordinates.
- **Amber: Related, external.** Actual OpenAI web search finds related resources. Its URL annotations remain clickable inline, with a source list. Textbook answers and web answers remain separate, even when both appear.
- **Red: Outside the subjects.** Unrelated requests get a brief boundary explanation. A relevant topic without retrieved evidence is labelled unverified, not unrelated.
- A standalone **Search book only** button for local retrieval without an AI request. It uses a small French/English fallback glossary; the full Ask workflow supports wider bilingual query expansion.
- Selectable text and read-aloud in the reader, answers, retrieved search results and translation dialog. Search terms and cited evidence are highlighted; the current spoken sentence is highlighted when the browser can locate it.
- Original chapter navigation, page jumping, previous/next page, PDF link, highlight toggle and image/text toggle.
- English and Canadian French interface, dark mode, larger/smaller type, keyboard focus and skip link, responsive layout and reduced-motion support.
- Speech controls: read selection/page/answer/passage/translation, pause/resume, stop, previous/next sentence, rate and voice. Automatic selection prefers **en-CA** or **fr-CA**. Available voices depend on the visitor's browser and operating system.
- Expandable multi-document manifest, password protection, CSRF checks, modest in-process request limits, server-side API credentials and a Render Blueprint.

The previous Kysely agent used Claude, Finnish/English and a book-specific index. This project follows its evidence-reader workflow with a new OpenAI backend and general document collection. There are no Anthropic or Finnish runtime settings.

## Model configuration

| Task | Default environment variable | Exact API model ID |
| --- | --- | --- |
| Textbook-supported answers | `OPENAI_ANSWER_MODEL` | `gpt-6.2-astra` |
| Scope classification and bilingual query planning | `OPENAI_SEARCH_MODEL` | `gpt-6.1-sol` |
| Related live web search | `OPENAI_SEARCH_MODEL` | `gpt-6.1-sol` |
| English ↔ Canadian French translation | `OPENAI_TRANSLATE_MODEL` | `gpt-6.1-sol` |

These are explicit settings; there is **no silent model fallback**. The OpenAI API project associated with your key must have access to the chosen models and available billing/quota. ChatGPT access does not itself verify API-project access. Reasoning effort is `low`; requests use the Responses API with `store=False`. That option is not a promise of zero provider retention under all account policies.

Official references checked 18 November 2026:

- [GPT-6.2 Astra](https://developers.openai.com/api/docs/models/gpt-6.2-astra)
- [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [Responses API web search](https://developers.openai.com/api/docs/guides/tools-web-search)
- [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## 1. Download and open the project on your Mac

Download `AccessEdu_Agent_Complete.zip`. The archive contains one top-level folder, `access-edu-agent`. These commands assume the ZIP is in Downloads:

```bash
mkdir -p "$HOME/Projects"
unzip "$HOME/Downloads/AccessEdu_Agent_Complete.zip" -d "$HOME/Projects"
cd "$HOME/Projects/access-edu-agent"
pwd
ls
```

You should see `app.py`, `render.yaml`, `requirements.txt`, `content`, `static`, `templates`, `scripts`, `tests` and this README. Those files belong **at the root of the GitHub repository**, as in the prior Kysely deployment. Do not add another enclosing folder inside the repository.

The original Finnish project is not needed to run this one. Its `.git`, `.venv`, data, caches and secrets are not included.

## 2. Install local tools and Python dependencies

Check existing tools:

```bash
git --version
python3 --version
gh --version
```

If you use Homebrew and need the tools:

```bash
brew install python@3.12 git gh
```

The code was tested on Python 3.12.14. The Render Blueprint selects this version. Create a virtual environment; use `python3.12` if you installed that Homebrew version:

```bash
cd "$HOME/Projects/access-edu-agent"
python3.12 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

If your `python3` already points to Python 3.12, `python3 -m venv .venv` is equivalent. To stop using the environment later, run `deactivate`.

## 3. Add your OpenAI key locally

Run the setup script. It prompts for your key and a demo password without echoing them, generates a session secret, and creates a private `.env` file:

```bash
python scripts/setup_env.py
```

Choose a demo password that you will use when opening the app. The setup script accepts a single-line password without an apostrophe; other configuration can be edited directly afterward. The key is **not** typed into a command or committed to Git.

If `.env` already exists, the script stops to preserve it. Edit it instead:

```bash
nano .env
```

The required values look like this; placeholders are explanatory, not literal working credentials:

```dotenv
OPENAI_API_KEY=your_actual_openai_api_key
APP_PASSWORD=your_chosen_demo_password
SECRET_KEY=a_long_random_secret
OPENAI_ANSWER_MODEL=gpt-6.2-astra
OPENAI_SEARCH_MODEL=gpt-6.1-sol
OPENAI_TRANSLATE_MODEL=gpt-6.1-sol
REQUESTS_PER_MINUTE=8
```

The setup script already generates `SECRET_KEY`. If you configure manually, generate one using:

```bash
python -c 'import secrets; print(secrets.token_hex(32))'
```

## 4. Validate content, models and local operation

These commands do not need your API key and do not make paid AI requests:

```bash
python scripts/check_content.py
python -m pytest -q
```

Check which exact models your API project lists:

```bash
python scripts/check_models.py
```

Then run a **small billable live integration check**. This checks query planning, an Astra answer with a citation, Canadian French translation and Sol web search with URL citations:

```bash
python scripts/check_models.py --smoke
```

If a model is unavailable, check your API project's model permissions. You can explicitly change the environment variables to the other model you requested if it is available; the app never substitutes automatically. For example, using Astra for search and translation too:

```dotenv
OPENAI_SEARCH_MODEL=gpt-6.2-astra
OPENAI_TRANSLATE_MODEL=gpt-6.2-astra
```

Restart after changing `.env`. This changes request cost and latency; it does not change document indexing.

Start the app:

```bash
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), enter the demo password, and test the reader and questions. Stop the server with **Control+C**.

If port 5000 is already in use:

```bash
PORT=5050 python app.py
```

Then open [http://127.0.0.1:5050](http://127.0.0.1:5050). In another terminal, check health without an AI request:

```bash
curl http://127.0.0.1:5000/health
```

Expected JSON includes `"status":"ok"`, `"documents":1`, and `"pages":422`. This endpoint confirms the app/content load; it deliberately does **not** certify API credentials or model availability.

If `APP_PASSWORD` is blank, the local reader and local search still work, but **paid AI routes are disabled**. Set a password to enable Ask and translation.

## 5. Create the GitHub repository

Recommended repository name: **`access-edu-agent`**. The first option creates a private repository. You can deliberately choose `--public` instead if you want to publish the code and included open textbook.

Authenticate with GitHub CLI:

```bash
gh auth login
gh auth status
```

Choose GitHub.com and HTTPS in the login prompts, then complete browser authentication. Initialize the project and inspect what will be committed:

```bash
cd "$HOME/Projects/access-edu-agent"
git init -b main
git check-ignore .env .venv/
git add .
git diff --cached --stat
git status --short
```

The ignore check should list `.env` and `.venv/`. Neither should appear in the staged files. Confirm no unexpected secrets are staged, then commit and create/push the repository:

```bash
git commit -m "Create AccessEdu bilingual accessibility demo"
gh repo create access-edu-agent --private --source=. --remote=origin --push
gh repo view --web
git remote -v
```

If Git asks for an identity, set it for this repository and retry the commit. Replace the example email with the email you use for GitHub, or your GitHub no-reply address:

```bash
git config user.name "Nishan Mudalige"
git config user.email "YOUR_GITHUB_EMAIL"
git commit -m "Create AccessEdu bilingual accessibility demo"
```

The included PDF is about 20.7 MB and can be committed as an ordinary file; Git LFS is not needed for this supplied file. Check future large PDFs before pushing them.

### Alternative: create an empty repository on GitHub.com

If you prefer the website to `gh repo create`, first initialize and commit locally as above. On GitHub, create an empty repository named `access-edu-agent`. Do **not** initialize it with another README, `.gitignore` or license. Then run:

```bash
git remote add origin https://github.com/nishanmudalige/access-edu-agent.git
git remote -v
git push -u origin main
```

This URL uses your known GitHub username, `nishanmudalige`. Change it if you create the repository in another account or organization. Use either the CLI creation route or this route, not both. If the remote already exists and is wrong:

```bash
git remote set-url origin https://github.com/nishanmudalige/access-edu-agent.git
git push -u origin main
```

GitHub HTTPS authentication uses GitHub CLI credentials or a personal access token, not your GitHub account password.

## 6. Deploy on Render using the supplied Blueprint

The supplied `render.yaml` reproduces the familiar **New → Blueprint** workflow from your Kysely project, with OpenAI variables replacing the Anthropic variables.

1. Sign in to [Render Dashboard](https://dashboard.render.com/).
2. Choose **New → Blueprint**.
3. Connect GitHub if needed. Grant Render access to `access-edu-agent`, including private-repository access if applicable.
4. Select that repository and the `main` branch.
5. Use `render.yaml` at the repository root as the Blueprint path.
6. Supply **`OPENAI_API_KEY`** and **`APP_PASSWORD`** when prompted. Use your actual OpenAI key and the password you want demo visitors to enter. The local `.env` is intentionally not sent to Render.
7. Render generates `SECRET_KEY`. The Blueprint sets all three model variables and Python 3.12.14.
8. Review the proposed service and plan, then select **Deploy Blueprint**.
9. Open the resulting web service and check the build/deploy logs. When the service is live, open its actual `https://...onrender.com` URL and sign in.

The Blueprint requests a free instance for a small demo. If your account cannot provision that plan, select an available plan deliberately. Free-instance cold starts, memory and request limits can affect a live presentation. The initial request builds the local index; no paid AI request is used to build it. There is no database or persistent disk requirement because the PDF is part of the repository.

### Manual Web Service alternative

Choose **New → Web Service**, connect the same repository, and set:

| Render field | Value |
| --- | --- |
| Name | `access-edu-agent` |
| Branch | `main` |
| Runtime | Python 3 |
| Root directory | Leave blank: `app.py` is at repository root |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:app --workers 1 --threads 4 --timeout 300 --bind 0.0.0.0:$PORT` |
| Health check path | `/health` |

Set these under **Environment** before deploying:

| Variable | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.12.14` |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `APP_PASSWORD` | Your chosen demo password |
| `SECRET_KEY` | A long random secret, generated with the Python command above |
| `OPENAI_ANSWER_MODEL` | `gpt-6.2-astra` |
| `OPENAI_SEARCH_MODEL` | `gpt-6.1-sol` |
| `OPENAI_TRANSLATE_MODEL` | `gpt-6.1-sol` |

Use the displayed Render `$PORT` binding exactly as written. Do not replace it with port 5000. Keep one worker with this demo's in-memory rate limiter. The four threads allow several requests without loading four separate PDF indexes. Use a shared rate-limit backend and proper user accounts before scaling to multiple workers/instances.

Render's official guides: [Flask deployment](https://render.com/docs/deploy-flask), [Blueprints](https://render.com/docs/infrastructure-as-code), [deploy behaviour](https://render.com/docs/deploys). GitHub's official guide: [Adding locally hosted code](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

## 7. Verify the deployed demo

Use the actual URL shown in Render. Replace the example hostname below:

```bash
curl https://YOUR-ACTUAL-SERVICE.onrender.com/health
```

Sign in and try:

1. **Textbook answer:** “What does a 95% confidence interval mean?” Expect a green source panel, clickable citations and relevant source blocks. Open a citation and toggle between selectable text and the original page image. Evidence highlights should refer to the same block in both views.
2. **Canadian French:** “Comment interpréter une valeur p?” Use automatic reply language, then explicitly select Français canadien. The original source remains English, while explanations/translations are French.
3. **Search results:** Use Search book only for “confidence interval”. Expand/read a passage, select a phrase, translate it to French, and read the translation.
4. **External material:** Enable related web resources and ask for a modern software example beyond the book. The external answer should have amber provenance and clickable real URLs.
5. **Unrelated:** “Plan a beach vacation.” Expect the outside-subjects label and a brief boundary explanation.
6. **Speech:** Read an answer, pause/resume, change rate, move between sentences, and read a selected result. Verify Canadian French with a `fr-CA` voice if available on that machine.
7. **Accessibility checks:** Tab through the interface, use the skip link, enlarge the text, change theme, and try a phone-sized screen. Reader headings, forms and controls should remain usable.

This is a demo checklist, not a claim of WCAG conformance or of a fully accessible mathematical textbook. Include screen-reader users in evaluation before making such a claim.

## 8. Add another book or subject later

No retraining is required. Put an authorized, text-searchable PDF in `content/`, and append an entry to the `documents` array in `content/manifest.json`:

```json
{
  "id": "biology-introduction",
  "file": "BiologyIntroduction.pdf",
  "title": "Your Biology Textbook",
  "authors": "Author names",
  "subject": "Introductory biology, cells, genetics, ecology and evolution",
  "language": "en-CA",
  "source_url": "https://example.edu/biology",
  "license": "The source’s actual license",
  "license_url": "https://example.edu/biology/license",
  "exclude_search_pages": [1, 2]
}
```

Keep both entries inside the same array; include a comma between them. Do not replace the entire file with the single object above. IDs must be unique lowercase slugs. `file` is relative to `content/`; escaping that folder is rejected. Use `fr-CA` for French source material; the reader then offers English as the page-translation target. Give `subject` enough detail to support scope classification. Excluded pages stay readable but do not influence search ranking. PDFs with bookmarks get a contents menu automatically. Scanned PDFs require OCR before adding them.

Update attribution and the UI footer for additional sources in `THIRD_PARTY_NOTICES.md` and `templates/base.html`. The initial footer correctly credits OpenIntro; it is not an automatic license inventory for future books. Search and answers already identify each document by title. Additional non-PDF formats would require another ingestion adapter; the collection is expandable across subjects now, but is PDF-only.

Validate and publish the addition:

```bash
source .venv/bin/activate
python scripts/check_content.py
python -m pytest -q
git add content/manifest.json content/BiologyIntroduction.pdf THIRD_PARTY_NOTICES.md templates/base.html
git diff --cached --stat
git commit -m "Add biology source to the accessibility demo"
git push origin main
```

Render rebuilds/restarts from the new commit when auto-deploy is enabled, rebuilding the index from the updated PDFs. No persistent index needs to be copied.

## 9. Routine updates

From the project folder:

```bash
source .venv/bin/activate
git pull --ff-only origin main
python -m pytest -q
git status
```

After editing, stage the files you changed, inspect, commit and push. For example:

```bash
git add app.py ai_service.py retrieval.py templates/ static/ README.md
git diff --cached --stat
git commit -m "Refine AccessEdu reader and bilingual answers"
git push origin main
```

Watch the Render deploy logs and repeat the key demo checks. If auto-deploy is disabled, use **Manual Deploy → Deploy latest commit**. To rotate the API key or change models on Render, edit **Environment** and save/redeploy; do not commit a key. Changing `.env` locally does not update Render.

## 10. Troubleshooting

### Local authentication/access error

The updated local build reads `.env` in the project folder **before exported shell variables**. On Render, environment settings continue to take precedence. Restart the app after editing `.env`.

If you see an OpenAI access error locally, stop the app with Control+C, then run:

```bash
source .venv/bin/activate
python scripts/diagnose_openai.py
python scripts/diagnose_openai.py --request
```

The first command makes no network request and reports configuration presence, never secret values. The second makes short billable requests directly to the Responses endpoint for the configured models. It does not depend on permission to list models. HTTP 401 points to authentication/key/organization configuration; HTTP 403 points to a request being forbidden (for example permissions or regional/project restrictions). HTTP 404 may indicate a wrong model name or lack of model access. HTTP 429 can indicate quota/spend/rate limits; inspect the machine-readable code to distinguish these cases. See [official OpenAI error documentation](https://developers.openai.com/api/docs/guides/error-codes).

To replace a missing, invalid, revoked or incorrectly copied key, open [OpenAI API keys](https://platform.openai.com/api-keys), choose the appropriate project and create/copy a key with access to the Responses endpoint and requested models. Put its complete value in `OPENAI_API_KEY` in `.env`; do not put it in `APP_PASSWORD`. Check API billing separately if the error code indicates quota or credits.

```bash
nano .env
python scripts/diagnose_openai.py --request
python app.py
```

If the diagnostic reports that `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID` or `OPENAI_BASE_URL` overrides are set, verify that they are intended. For a normal direct OpenAI connection, obsolete overrides can be removed from your shell configuration and `.env`. Do not remove settings intentionally required by your organization.

Share only the diagnostic HTTP status and machine-readable code if more help is needed. Never share `.env` contents or an API key. A successful short request establishes basic model/Responses access, not the quality or availability of every tool; `check_models.py --smoke` remains the fuller integration check.

| Symptom | Check / action |
| --- | --- |
| `ModuleNotFoundError` | Activate `.venv`, run `python -m pip install -r requirements-dev.txt`, then retry. |
| `app` module missing on Render | Confirm `app.py` is at repo root and Root Directory is blank; use the supplied start command. |
| `/health` works but Ask fails | Health checks content only. Verify key, model access and API billing. Run `python scripts/check_models.py --smoke` locally. |
| Unknown / unavailable model | Confirm exact IDs in the environment; run the model checker. There is no silent fallback. |
| OpenAI quota/rate error | Check API-project usage, credits and limits, then retry. A shared demo can consume multiple calls per question. |
| Web panel unavailable but green answer works | Check Sol's web-search access. The book answer remains usable; disable related web resources temporarily if needed. No uncited web claim is shown. |
| Ask/translation disabled | Set a nonblank `APP_PASSWORD`; blank password intentionally blocks paid requests. |
| Login reloads or sessions break after restart | Set a stable `SECRET_KEY` and keep one worker. Blueprint generates a stable value. |
| Session expired error | Reload to obtain a fresh CSRF token and sign in again if needed. |
| Rate limit appears early on Render | The demo uses the direct peer address. Proxy-shared traffic may share one limit; it does not trust arbitrary forwarded client headers. Tune the limit for a controlled demonstration. |
| No `fr-CA` voice | Install a Canadian French system voice or use a browser that exposes one. Another French voice is a labelled fallback; the app does not promise a Canadian accent without a matching voice. |
| Speech stops or pause fails | Browser speech implementations vary. Use shorter selections, Stop then Read, or another browser. Voice choice and speed persist locally. |
| Formula/table text is awkward | PDF extraction is imperfect. Inspect the original page image/PDF. This build does not include OCR, MathML reconstruction or automatic diagram descriptions. |
| A relevant question is labelled unrelated | The scope decision is model-based and can be wrong. Broaden `subject` in the manifest, rephrase, or adjust the planning prompt in `ai_service.py`. |
| New PDF is not searched | Check manifest JSON, file name/case, subject and text extraction, run `check_content.py`, then restart/redeploy. |
| A citation highlights the wrong meaning | Block IDs/positions are validated mechanically; semantic support is selected by the model and needs human evaluation. Review the source and refine the answer prompt/retrieval. |
| First request is slow | Allow for Render cold start and the initial PDF index build. An AI question can make up to three model requests, and more when translation is used. |

## Architecture and data handling

`retrieval.py` extracts stable text blocks, line rectangles and PDF bookmarks with PyMuPDF, then ranks them locally with BM25. `ai_service.py` uses OpenAI Responses structured outputs for scope/query planning and textbook answers. The server validates citation keys against the actual retrieved passages. Both HTML text highlights and original-page overlays use the same source blocks. This verifies citation destinations, not the truth of every model interpretation.

Web search runs only for related requests when enabled, using the requested Sol model and the actual `web_search` tool with required tool use. URL annotations are rendered as links at their citation positions and listed below. No other search-service key is needed. External pages open on their own websites; their text is not silently represented as uploaded-book content.

API calls happen only on the server. The `.env` file, API key and password are never sent to browser JavaScript. Chat history is bounded to the latest six user/assistant messages and is kept in tab memory; the app does not store conversation transcripts in a database or localStorage. Display/language/voice preferences use localStorage. Session authentication uses a signed, HttpOnly cookie; HTTPS on Render enables secure cookies. The app does not intentionally log question or passage text. Hosting and OpenAI providers still have their own service-level processing/logging policies.

Read-aloud uses the visitor's browser Speech Synthesis API, not OpenAI TTS. Some browser voices are remote services. Spoken sentence highlighting uses CSS Custom Highlights when available and per-text-node marks otherwise; it is sentence-level, not guaranteed word-level alignment. A voice selection from the wrong language is not applied to the other language. Text translation is explicitly Canadian French; speech accent depends on installed voices.

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Flask routes, sessions, CSRF, rate limits, source reader and API orchestration |
| `ai_service.py` | Exact OpenAI models, prompts, structured outputs, web citations and translation |
| `retrieval.py` | Multi-document PDF text/block index and local bilingual fallback search |
| `content/manifest.json` | Document metadata, scope subjects and filenames |
| `content/OpenIntroStatistics4e.pdf` | Supplied original textbook |
| `templates/` | Home, reader, login and common accessible controls |
| `static/` | Interface styles, search UI, speech and translation controls |
| `scripts/setup_env.py` | Local secret setup with hidden prompts |
| `scripts/check_models.py` | Model availability and optional billable live integration check |
| `scripts/check_content.py` | Local content/retrieval validation |
| `tests/test_agent.py` | Offline automated integration and regression checks |
| `render.yaml` | Ready-to-use Render service definition |
| `THIRD_PARTY_NOTICES.md` | Textbook attribution, adaptations and third-party licenses |
| `docs/VALIDATION.md` | Checks performed and limits of this delivery |

This package is prepared for you to upload/deploy. It has not created a GitHub repository or Render service in your account. No API key was supplied to this build environment, so live OpenAI calls must be verified using your key before presenting it.
