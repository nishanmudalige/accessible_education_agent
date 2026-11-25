// Run inside the real MathJax browser fixture; only the operating-system voice is replaced.
const fs=require('node:fs'),assert=require('node:assert/strict');
const read=path=>fs.readFileSync(path,'utf8');
module.exports=async function renderedSpeech(w){
  const d=w.document,$=id=>d.getElementById(id);
  const fragment=(path,selector)=>new w.DOMParser().parseFromString(read(path),'text/html').querySelector(selector);
  const calculus='content/active-calculus-html/sec-1-2-lim.html';
  const definition=fragment(calculus,'#sec-1-2-lim-4-4');
  const image=fragment(calculus,'img[alt]');
  const french=fragment('content/liberte1-html/module-2.html','#paragraph-878e350404724eaf-1');
  const base=read('templates/base.html').split(/<body[^>]*>/)[1].split('</body>')[0];
  const actions=read('templates/_reader_page_actions.html').replace(/{% if pdf_reader %}.*?{% endif %}/s,'');
  d.body.innerHTML=base.replace('{% block content %}{% endblock %}',actions+
    '<p id="citation-status" data-source-lang="en-CA"></p><article lang="en-CA" class="chapter-content"></article>');
  const chapter=d.querySelector('.chapter-content');
  const caption=fragment('content/active-calculus-html/sec-1-3-derivative-pt.html','#F-1-3-SecToTan figcaption');
  chapter.append(definition,image,caption);
  w.history.replaceState(null,'','?hl='+definition.id);
  await w.MathJax.typesetPromise([chapter]);
  const formula=definition.querySelector('.displaymath mjx-container');
  const assistive=formula.querySelector('mjx-assistive-mml').outerHTML;
  const utterances=[];
  w.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
  w.speechSynthesis={getVoices:()=>[],cancel(){},speak(u){utterances.push(u);u.onend();}};
  w.HTMLElement.prototype.scrollIntoView=function(){};
  w.requestAnimationFrame=fn=>fn();
  for(const file of ['speech-text.js','common.js','speech.js','book.js','vendor/marked/lib/marked.umd.js',
    'vendor/dompurify/dist/purify.min.js','rich-text.js'])w.eval(read('static/'+file));
  await new Promise(resolve=>setImmediate(resolve));
  async function play(action){
    utterances.length=0;
    const readText=w.AccessSpeech.readText;
    let resolve;
    const done=new Promise(r=>{resolve=r;});
    w.AccessSpeech.readText=(...args)=>{readText(...args);resolve();};
    try {
      action();await Promise.race([done,new Promise((_,reject)=>setTimeout(()=>reject(Error('No playback')),5000).unref())]);
    }finally{w.AccessSpeech.readText=readText;}
    const text=utterances.map(u=>u.text).join(' ');
    assert.doesNotMatch(text,/\\(?:begin|end|text|lim|frac|to)(?![a-z])/i);
    return text;
  }

  const limit='limit Underscript x right arrow a Endscripts f left parenthesis x right parenthesis equals upper L';
  assert.ok((await play(()=>$('reader-read-highlights').click())).includes(limit));
  assert.equal(formula.querySelector('mjx-assistive-mml').outerHTML,assistive);
  assert.ok((await play(()=>$('read-page').click())).includes('Image: '+image.alt));
  const range=d.createRange();range.selectNode(formula);
  w.getSelection().removeAllRanges();w.getSelection().addRange(range);
  d.dispatchEvent(new w.Event('selectionchange'));await new Promise(r=>setTimeout(r,120));
  assert.equal(await play(()=>$('read-selection').click()),limit);
  function select(range){
    w.getSelection().removeAllRanges();w.getSelection().addRange(range);
    d.dispatchEvent(new w.Event('selectionchange'));
  }
  const inline=caption.querySelectorAll('mjx-container');
  const before=inline[3].parentElement.previousSibling, after=inline[4].parentElement.nextSibling;
  range.setStart(before,before.textContent.lastIndexOf('to '));
  range.setEnd(after,after.length);select(range);
  assert.deepEqual([...d.querySelectorAll('.selection-math')],[inline[3],inline[4]]);
  assert.equal(await play(()=>$('read-selection').click()),
    'to f at left parenthesis a comma f left parenthesis a right parenthesis right parenthesis is given by');
  range.setStart(inline[3].querySelector('mjx-c'),0);range.setEnd(inline[4].querySelector('mjx-c'),0);select(range);
  assert.equal(await play(()=>$('read-selection').click()),
    'f at left parenthesis a comma f left parenthesis a right parenthesis right parenthesis');
  range.selectNodeContents(definition);select(range);
  const definitionText=await play(()=>$('read-selection').click());
  assert.ok(definitionText.includes(limit));
  w.getSelection().removeAllRanges();d.dispatchEvent(new w.Event('selectionchange'));
  assert.equal(d.querySelector('.selection-math'),null);
  const pdf=d.createElement('div');pdf.id='page-text';pdf.lang='en-CA';
  pdf.innerHTML='<p class="source-block">First paragraph.</p><p class="source-block">Second paragraph.</p>';
  d.body.append(pdf);range.setStart(pdf.firstChild.firstChild,6);range.setEnd(pdf.lastChild.firstChild,6);select(range);
  assert.equal(await play(()=>$('read-selection').click()),'paragraph. Second');
  const sample=d.createElement('p');
  sample.innerHTML='before<img alt=""><img><img alt="chat"><mjx-container></mjx-container>after';
  assert.equal((await w.AccessSpeechText(sample,'fr')).text,'before Image sans description Image : chat formule after');
  assert.equal((await w.AccessSpeechText(sample,'en')).text,'before Image without description Image: chat formula after');
  const partial=d.createRange();
  partial.setStart(sample.firstChild,3);partial.setEnd(sample.lastChild,2);
  assert.equal((await w.AccessSpeechText(partial,'en')).text,'ore Image without description Image: chat formula af');
  sample.textContent=String.raw`\lim_{x\to a} f(x)`;
  assert.equal((await w.AccessSpeechText(sample,'en')).text,'formula');
  assert.match((await w.AccessSpeechText(formula,'fr')).text,/limite.*égale/);
  chapter.replaceChildren(french);$('citation-status').dataset.sourceLang='fr-CA';
  assert.match(await play(()=>$('read-page').click()),/Combien d’amis/);
  assert.ok(utterances.every(u=>u.lang==='fr-CA'));

  d.body.insertAdjacentHTML('beforeend',read('templates/index.html').split('{% block content %}')[1].split('{% endblock %}')[0]);
  w.AccessEdu.post=async()=>({language:'en-CA',category:'book',book_answer:String.raw`The derivative is \[f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}\]`,evidence:[],results:[]});
  w.eval(read('static/app.js'));
  $('question').value='What is derivative';
  await $('ask-form').onsubmit({preventDefault(){}});
  const answerText=await play(()=>d.querySelector('.answer-actions button').click());
  assert.match(answerText,/limit.*fraction/i);
  console.log('Spoken definition formula:',limit);
};
