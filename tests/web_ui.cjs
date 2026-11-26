// Exercise the real UI, Markdown parser and sanitizer without any model requests.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function checkDictation(){
  const template=fs.readFileSync('templates/index.html','utf8');
  const form=template.match(/<form id="ask-form">[\s\S]*?<\/form>/)[0];
  const dom=new JSDOM(form,{url:'https://app.test',runScripts:'outside-only'});
  const {window}=dom,doc=window.document;
  window.AccessEdu={tr:en=>en};
  let recognition;
  window.SpeechRecognition=class {
    start(){recognition=this;this.onstart();}
    stop(){this.onend();}
  };
  window.eval(fs.readFileSync('static/dictation.js','utf8'));
  assert.equal(doc.getElementById('dictation').hidden,false);
  for(const lang of ['fr-CA','en-US']){
    doc.querySelector('[data-lang="'+lang+'"]').click();
    doc.getElementById('dictate').click();
    assert.equal(recognition.lang,lang);
    recognition.onresult({results:[[{transcript:'test'}]]});
    assert.ok(doc.getElementById('question').value.endsWith('test'));
    doc.getElementById('dictate').click();
  }
  window.close();
}
function checkSampleQuestions(){
  const form=fs.readFileSync('templates/index.html','utf8').match(/<form id="ask-form">[\s\S]*?<\/form>/)[0];
  const dom=new JSDOM(form,{url:'https://app.test',runScripts:'outside-only'});
  const {window}=dom,doc=window.document;
  window.AccessEdu={tr:en=>en,post(){assert.fail('Choosing a sample submitted the form');}};
  window.eval(fs.readFileSync('static/app.js','utf8'));
  const toggle=doc.getElementById('sample-toggle'),list=doc.getElementById('sample-list');
  const items=[...list.querySelectorAll('button')],question=doc.getElementById('question');
  function key(name){doc.activeElement.dispatchEvent(new window.KeyboardEvent('keydown',{key:name,bubbles:true}));}
  assert.deepEqual([...list.querySelectorAll('section')].map(s=>s.querySelectorAll('button').length),[6,4]);
  assert.equal(toggle.dataset.fr,'Exemples de questions');
  toggle.click();assert.equal(toggle.getAttribute('aria-expanded'),'true');
  assert.equal(doc.activeElement,items[0]);
  key('ArrowUp');assert.equal(doc.activeElement,items.at(-1));
  key('ArrowDown');assert.equal(doc.activeElement,items[0]);
  key('Escape');assert.equal(doc.activeElement,toggle);assert.ok(list.hidden);
  toggle.click();items[6].click();
  assert.equal(question.value,"Qu'est-ce qu'une droite sécante ?");
  assert.equal(doc.activeElement,question);assert.equal(toggle.getAttribute('aria-expanded'),'false');
  dom.window.close();
}
async function scenario(auto,fail=false,category='book',plotFailureLang=null){
  const dom=new JSDOM('<select id="reply-language"><option value="auto">auto</option></select><form id="ask-form"><textarea id="question"></textarea><input id="doc"><input type="checkbox" id="web"><button id="ask"></button><button id="local-search"></button></form><div id="conversation"></div><p id="status"></p>',{url:'https://app.test',runScripts:'outside-only'});
  const window=dom.window,document=window.document,$=id=>document.getElementById(id);
  window.HTMLElement.prototype.scrollIntoView=function(){};
  $('question').value='What is a derivative?';$('web').checked=auto;$('doc').value='active-calculus-html';
  const calls=[];let failed=fail;
  const figure={key:'S2',url:'/book/demo/chapter?hl=diagram',local_url:'/book-assets/demo/diagram.svg',alt:'A tangent at point P'};
  let spoken;
  window.AccessEdu={speak(source,lang){spoken=window.AccessSpeechText(source,lang);},tr:en=>en,localize(){},post:async(path,data)=>{
    calls.push([path,data]);
    if(path==='/api/ask')return {category,intent:category==='generated'?'generate':'lookup',book_answer:['generated','book'].includes(category)?'Textbook answer.':'',notice:'Not verified',language:plotFailureLang||'en-CA',plot_failed:!!plotFailureLang,evidence:[],results:[],figures:plotFailureLang?[]:auto?[{kind:"generated",local_url:"data:image/svg+xml;base64,PHN2Zy8+",alt:figure.alt}]:[figure],web:null,web_token:category==='out_of_scope'?undefined:'signed'};
    if(failed){failed=false;throw Error('Search failed. Try again.');}
    return {web:{verified:true,text:'### External answer.\n\n- One item\n- Another item',citations:[]}};
  }};
  window.MathJax={startup:{promise:Promise.resolve()},typesetPromise:async()=>{}};
  for(const path of ['static/vendor/marked/lib/marked.umd.js','static/vendor/dompurify/dist/purify.min.js','static/rich-text.js','static/speech-text.js','static/app.js'])window.eval(fs.readFileSync(path,'utf8'));
  await $('ask-form').onsubmit({preventDefault(){}});await flush();
  if(plotFailureLang){
    assert.equal(document.querySelector('.answer-figures p').textContent,plotFailureLang==='fr-CA'?"Le graphique n'a pas pu être généré.":'The graph could not be generated.');
    assert.equal(document.querySelector('.answer-figures img'),null);
    dom.window.close();return;
  }
  if(category==='generated'){
    const badge=document.querySelector('.answer > .badge');
    assert.equal(badge.textContent,'Generated example');
    assert.equal(badge.dataset.fr,'Exemple généré');
    assert.equal(calls.length,1);
    dom.window.close();return;
  }
  if(category==='book'){
    const img=document.querySelector('.answer-figures figure img');
    assert.equal(img.alt,figure.alt);
    if(auto){
      assert.equal(document.querySelector('figcaption details p').textContent,figure.alt);
      assert.equal(document.querySelector('figcaption .badge').textContent,'Generated plot');
    }else{
      assert.equal(img.getAttribute('src'),figure.local_url);
      assert.equal(img.parentElement.getAttribute('href'),figure.url);
      assert.equal(document.querySelector('figcaption a').textContent,'[S2]');
    }
    document.querySelector('.answer-actions button').click();
    assert.match((await spoken).text,/Textbook answer[\s\S]*Image: A tangent at point P/);
  }else assert.equal(document.querySelector('.answer-figures'),null);
  assert.equal(calls[0][1].web,false);
  const button=[...document.querySelectorAll('button')].find(n=>n.dataset.en==='Search the web');
  if(category==='out_of_scope'){assert.equal(button,undefined);assert.equal(calls.length,1);dom.window.close();return;}
  assert.ok(button);
  if(!auto){assert.equal(calls.length,1);button.click();await flush();}
  assert.equal(calls[1][0],'/api/web-search');assert.equal(calls[1][1].token,'signed');
  if(fail){assert.equal(button.disabled,false);assert.ok($('conversation').textContent.includes('Search failed. Try again.'));button.click();await flush();}
  assert.equal(button.hidden,true);
  assert.equal(document.querySelector('.web-content h3').textContent,'External answer.');
  assert.equal(document.querySelectorAll('.web-content li').length,2);
  if(category==='book')assert.ok(document.querySelector('.answer > .prose').textContent.includes('Textbook answer.'));
  else assert.equal(button.className,'primary');
  dom.window.close();
}
(async()=>{checkDictation();checkSampleQuestions();await scenario(false,false,'book','en-CA');await scenario(false,false,'generated','fr-CA');await scenario(false,true);await scenario(true);await scenario(true,false,'generated');await scenario(false,false,'related_outside');await scenario(false,false,'out_of_scope');console.log('Web UI interactions, Markdown and sanitization passed');})().catch(e=>{console.error(e);process.exitCode=1;});
