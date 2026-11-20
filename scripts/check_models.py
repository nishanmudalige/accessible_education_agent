"""Check account access; --smoke makes short, billable API requests."""
import argparse
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env', override=os.getenv('RENDER','').lower()!='true')
import ai_service as ai

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--smoke',action='store_true',help='Run short billable structured-output, translation and web-search checks')
    args=p.parse_args()
    try:
        c=ai.client()
        available={m.id for m in c.models.list()}
        missing=[]
        for model in dict.fromkeys([ai.ASTRA,ai.SOL,ai.TRANSLATE]):
            print(model+(': listed for this API project' if model in available else ': NOT listed for this API project'))
            if model not in available: missing.append(model)
        if missing:
            print('No substitute model has been selected. Check access or explicitly edit model variables.')
            return 1
        if args.smoke:
            plan=ai.plan('What is a sample mean?','en-CA',[{'subject':'introductory statistics'}],[])
            assert plan['related'] and plan['language']=='en-CA'
            answer=ai.answer('What is a sample mean?','en-CA',[{'key':'S1','doc':'test','page':1,'id':'p0','text':'The sample mean is the sum of the observations divided by the sample size.'}],[],[{'id':'test','title':'Statistics test','subject':'introductory statistics','language':'en-CA'}])
            assert ai.validate_answer(answer,[{'key':'S1'}])[0]
            print('Astra structured textbook answer: OK')
            translated=ai.translation('A sample mean estimates a population mean.','fr-CA')
            print('Canadian French translation:',translated)
            web=ai.web_search('OpenIntro Statistics official textbook','en-CA','statistics')
            if not web['verified']:raise RuntimeError('Web tool returned no verified URL citations')
            print('Sol live web search with citations: OK')
        return 0
    except Exception as e:
        # Avoid printing raw provider errors or credentials.
        print(f'Check failed: {type(e).__name__}. {ai.error_summary(e)}')
        print('If only the models-list permission is restricted, test the Responses endpoint directly with: python scripts/diagnose_openai.py --request')
        return 1
if __name__=='__main__':raise SystemExit(main())
