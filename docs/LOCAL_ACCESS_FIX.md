# Local OpenAI access fix

The previous app combined HTTP 401 and 403 into a single Render-specific message. That wording did not identify the cause. This update separates these cases and reports the provider error code without showing credentials.

Locally, .env now takes precedence over older exported shell variables. Render environment settings still take precedence when deployed there. This change fixes stale exported configuration; it does not grant access to an invalid key or unavailable model.

## Apply the small patch on your Mac

Stop the app with Control+C. If you used the original project location:

```bash
unzip -o "$HOME/Downloads/AccessEdu_Local_Access_Fix.zip" -d "$HOME/Projects"
cd "$HOME/Projects/access-edu-agent"
source .venv/bin/activate
python scripts/diagnose_openai.py
python scripts/diagnose_openai.py --request
```

The patch replaces app code and documentation; it does not contain or overwrite .env, .venv, or content PDFs. Adapt the destination if your project is elsewhere. The --request command makes short billable Responses requests and prints only configuration presence, model names, HTTP status, machine-readable error codes and fixed explanatory messages. The API key and raw provider error are never printed.

- HTTP 401: check the actual key and organization/project configuration in .env. A key can be incorrect, revoked, restricted, or assigned to a different project. Use an actual OpenAI API key, not the demo password.
- HTTP 403: inspect the error code and endpoint/model/project restrictions. Regional or organizational access restrictions are also possible.
- HTTP 404 / model_not_found: verify model names and access for this project. No automatic substitution is made.
- HTTP 429: inspect the code for quota, credit balance, spending limits or rate limiting; API billing is managed separately from the local app.

If a key needs correction, edit it privately:

```bash
nano .env
python scripts/diagnose_openai.py --request
python app.py
```

Reload the local app after restart. Share only the diagnostic HTTP status and code if help is still needed; never send an API key or the .env file.

Official reference: https://developers.openai.com/api/docs/guides/error-codes
