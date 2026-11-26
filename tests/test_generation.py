from types import SimpleNamespace

from originality import check_example, normalized
from planning import local_intent


def test_local_generation_or_lookup():
    for q in ['Generate a quadratic.', 'Create an exercise.', 'Give me an example of a polynomial.',
              'Génère une fonction.', 'Donne-moi un exemple de fonction quadratique.']:
        assert local_intent(q)=='generate'
    assert local_intent('What is a quadratic function?')=='lookup'


def test_normalized_expression_check_in_another_book(tmp_path):
    (tmp_path/'chapter.html').write_text('<h2>7x<sup>2</sup> − 8x + 5</h2>')
    index=SimpleNamespace(pages={('pdf',1):[{'text':'5x + 1'}],('html',1):[]},docs={
        'pdf':{'title':'PDF'},'html':{'format':'html','title':'HTML','path':tmp_path/'book.json',
                                      'chapters':[{'file':'chapter.html','title':'Chapter'}]}})
    expr='7*x**2-8*x+5'
    assert normalized(expr)==normalized(r'7 \cdot x^{2} − 8x + 5')
    assert check_example(index,expr,r'\(f(x)=7x²-8x+5\)','en-CA')[0] is True
    assert check_example(index,'9x','f(x)=9x','fr-CA')[0] is False
    assert check_example(index,'8x','f(x)=9x','en-CA')[0] is None
