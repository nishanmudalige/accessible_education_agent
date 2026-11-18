"""Diagnose local configuration; --request runs short billable Responses probes.

Never prints the key, .env contents or a raw provider error message.
"""
import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv, dotenv_values
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',action='store_true',help='Make a short billable Responses request with each configured model')
    args=parser.parse_args()
    path=ROOT/'.env'
    old_key=os.getenv('OPENAI_API_KEY')
    values=dotenv_values(path) if path.is_file() else {}
    render=os.getenv('RENDER','').lower()=='true'
    load_dotenv(path,override=not render)
    import ai_service as ai
    print('Configuration mode:', 'Render environment takes precedence' if render else 'Local .env takes precedence over exported variables')
    print('.env found:',path.is_file())
    print('OPENAI_API_KEY configured:',bool(os.getenv('OPENAI_API_KEY','').strip()))
    if old_key and values.get('OPENAI_API_KEY') and old_key!=values['OPENAI_API_KEY']:
        print('An exported API key differs from .env. This updated local build uses the .env value.')
    for name in ('OPENAI_ORG_ID','OPENAI_PROJECT_ID','OPENAI_BASE_URL'):
        print(name+' override set:',bool(os.getenv(name)))
    models=list(dict.fromkeys([ai.SOL,ai.ASTRA,ai.TRANSLATE]))
    print('Models:',', '.join(models))
    if not args.request:
        print('No API request made. For short billable direct endpoint checks, add --request.')
        return 0
    failed=False
    for model in models:
        try:
            response=ai.client().responses.create(model=model,input='Reply with the word OK.',
                reasoning={'effort':'low'},store=False,max_output_tokens=1024)
            print(f'{model}: request accepted; response status={response.status}')
        except Exception as error:
            failed=True
            status,code=ai.error_details(error)
            print(f'{model}: {type(error).__name__}; HTTP={status or "not available"}; code={code or "not provided"}')
            print(ai.error_summary(error))
            # Authentication failure applies to the same credentials for both models.
            if status==401:break
    return int(failed)

if __name__=='__main__':raise SystemExit(main())
