const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const read=file=>fs.readFileSync(file,'utf8');

async function run(found,fr=false){
  const actions=read('templates/_reader_page_actions.html').replace(/{% if pdf_reader %}.*?{% endif %}/s,'');
  const html=read('templates/base.html').replace('{% block content %}{% endblock %}',actions+
    '<p id="citation-status" data-source-lang="'+(fr?'fr-CA':'en-CA')+'"></p>'+
    '<article class="chapter-content"><details><p id="evidence">A passage.</p></details><p id="long"></p></article>');
  const dom=new JSDOM(html,{url:'https://app.test/book/test/ch?hl='+(found?'evidence':'missing'),runScripts:'outside-only'});
  const w=dom.window,d=w.document,$=id=>d.getElementById(id);
  w.HTMLElement.prototype.scrollIntoView=function(){this.scrolled=true;};
  w.requestAnimationFrame=fn=>fn();
  $("translation-dialog").showModal=function(){this.open=true;};
  w.MathJax={startup:{promise:Promise.resolve()}};
  w.eval(read('static/common.js'));
  w.eval(read('static/book.js'));
  w.dispatchEvent(new w.Event('load'));
  await new Promise(resolve=>setImmediate(resolve));
  const target=$('evidence'),toggle=$('reader-highlight-toggle'),highlights=$('reader-read-highlights');
  assert.equal(highlights.disabled,!found);
  assert.equal($('reader-text-toggle'),null);
  if(found){
    assert.ok(target.parentElement.open&&target.scrolled);
    assert.equal(d.activeElement,target);
    assert.equal(target.getAttribute('aria-describedby'),'citation-status');
    toggle.click();assert.equal(toggle.getAttribute('aria-pressed'),'false');
    assert.equal(toggle.textContent,'Show highlights');
    assert.ok(d.querySelector('.chapter-content.hide-citation .cited-passage'));
    const spoken=[];
    w.AccessSpeech={readText:(...args)=>spoken.push(args)};
    highlights.click();assert.equal(spoken[0][0],'A passage.');
    toggle.click();assert.equal(toggle.getAttribute('aria-pressed'),'true');
    $('long').textContent='word '.repeat(3000).trim();
    $('read-page').click();assert.equal(spoken[1][0],'A passage.\n\n'+$('long').textContent);
    let copied;w.navigator.clipboard={writeText:async value=>{copied=value;}};
    $('reader-copy').click();assert.equal(copied,w.location.href);

    const requests=[];
    w.fetch=async(path,options)=>{
      const batch=JSON.parse(options.body);requests.push(batch.text);
      assert.equal(path,'/api/translate');assert.equal(batch.target,'fr-CA');
      if(requests.length===2){
        assert.equal($('translation-text').textContent,'Premier passage.');
        assert.match($('translation-note').textContent,/1\/3/);
        return {status:429,ok:false};
      }
      return {ok:true,json:async()=>({text:'Premier passage.',notice:'Test'})};
    };
    $('translate-page').click();await new Promise(resolve=>setImmediate(resolve));
    assert.equal(requests[0],'A passage.');assert.equal(requests.length,2);
    assert.ok(requests.every(text=>text.length<=14000));
    assert.match($('translation-note').textContent,/1\/3.*limit/i);
    assert.equal($('translation-text').textContent,'Premier passage.');
    assert.equal($('read-translation').disabled,false);
    const translated=[];
    w.fetch=async(path,options)=>{
      translated.push(JSON.parse(options.body).text);
      return {ok:true,json:async()=>({text:'Part '+translated.length,notice:'Test'})};
    };
    $('translate-page').click();await new Promise(resolve=>setImmediate(resolve));
    assert.equal(translated.slice(1).join(' '),$('long').textContent);
    assert.match($('translation-note').textContent,/3\/3/);
    assert.equal($('translation-text').textContent,'Part 1\n\nPart 2\n\nPart 3');
  }else assert.ok($('citation-status').textContent.includes(fr?'introuvable':'could not be found'));
  dom.window.close();
}
(async()=>{await run(true);await run(false);await run(false,true);console.log('HTML reader actions and batched translation passed');})().catch(error=>{console.error(error);process.exitCode=1;});
