"""Compare literal content across all locally loaded textbook pages."""
import re
import unicodedata
from bs4 import BeautifulSoup


def normalized(text):
    # Preserve exponents before NFKC folds superscript digits into ordinary digits.
    text=re.sub('[⁰¹²³⁴⁵⁶⁷⁸⁹]+',lambda m:'^'+unicodedata.normalize('NFKC',m[0]),text)
    text=unicodedata.normalize('NFKC',text).lower()
    text=re.sub(r'\\(?:left|right)\b|\\(?:[(),;!\[\]]|quad\b|qquad\b)', '',text)
    text=re.sub(r'\\(?:cdot|times)\b|[×⋅·∗]','*',text)
    text=text.replace('**','^').replace('−','-').replace('–','-').replace('＋','+')
    text=re.sub(r'\\(?:d?frac|tfrac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}',r'(\1)/(\2)',text)
    text=re.sub(r'\s+','',text)
    text=re.sub(r'\^\{(-?\d+)\}',r'^\1',text)
    return re.sub(r'(?<=[0-9)])\*(?=[a-z(])','',text)


def check_example(index, example, answer, lang):
    fr=lang=='fr-CA'
    key=normalized(example or '')
    if not key or key not in normalized(answer):
        return (None,'La comparaison textuelle n’a pas pu être effectuée.' if fr else
                'The text comparison could not be completed.')
    for (doc,page),blocks in index.pages.items():
        found=key in normalized(' '.join(p['text'] for p in blocks))
        document=index.docs[doc]
        if not found and document.get('format')=='html':
            chapter=document['chapters'][page-1]
            path=document['path'].parent/chapter['file']
            soup=BeautifulSoup(path.read_bytes(),'html.parser',from_encoding='utf-8')
            for power in soup.select('sup'):
                power.insert_before('^')
            found=key in normalized(soup.get_text(' '))
        if found:
            title=index.docs[doc]['title']
            location=document['chapters'][page-1]['title'] if document.get('format')=='html' else str(page)
            return (True, f'Une occurrence textuelle normalisée a été trouvée dans {title} ({location}).' if fr else
                    f'A normalized text match was found in {title} ({location}).')
    return (False,'Aucune occurrence textuelle normalisée de cet exemple dans le texte extrait des manuels chargés. Les formes algébriquement équivalentes peuvent différer.' if fr else
            'No normalized text match for this example was found in the extracted text of the loaded textbooks. Algebraically equivalent forms may be written differently.')
