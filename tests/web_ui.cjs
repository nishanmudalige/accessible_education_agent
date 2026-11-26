// Exercise the real UI, Markdown parser and sanitizer without any model requests.
const assert=require('node:assert/strict'),fs=require('node:fs');
const {JSDOM}=require('jsdom');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function scenario(auto,fail=false,category='book',plotFailureLang=null){
  const dom=new JSDOM('<div id="examples"></div><button id="shuffle"></button><select id="reply-language"><option value="auto">auto</option></select><form id="ask-form"><textarea id="question"></textarea><input id="doc"><input type="checkbox" id="web"><button id="ask"></button><button id="local-search"></button></form><div id="conversation"></div><p id="status"></p>',{url:'https://app.test',runScripts:'outside-only'});
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
(async()=>{await scenario(false,false,'book','en-CA');await scenario(false,false,'generated','fr-CA');await scenario(false,true);await scenario(true);await scenario(true,false,'generated');await scenario(false,false,'related_outside');await scenario(false,false,'out_of_scope');console.log('Web UI interactions, Markdown and sanitization passed');})().catch(e=>{console.error(e);process.exitCode=1;});
