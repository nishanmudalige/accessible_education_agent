"""Conservative local English detection for the optional planning fast path."""
import re

ENGLISH = set('what how why when where which who explain define describe find calculate show summarize translate page please the is are does do can could would should tell give help want need learn derivative integral calculus differentiate integrate'.split())
FRENCH = set('bonjour salut merci comment pourquoi quel quelle quels quelles est sont une des dans avec pour explique expliquez definir trouvez calculer pouvez vous nous voudrais veux cherche ce cette qu que du au aux et ou le la les je il elle on dérivée dérivation'.split())

def is_english(question):
    # Ambiguous, mixed-language and non-ASCII alphabetic input uses the planner.
    if any(c.isalpha() and not c.isascii() for c in question):
        return False
    words = set(re.findall(r'[a-z]+', question.lower()))
    return bool(words & ENGLISH) and not bool(words & FRENCH)
