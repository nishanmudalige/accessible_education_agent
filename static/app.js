'use strict';
(() => {
  const $=id=>document.getElementById(id),A=window.AccessEdu;
  const history=[];
  const samples=[
    'What does a 95% confidence interval mean?',
    'Quelle est la différence entre un paramètre et une statistique?',
    'Why does random sampling matter?',
    'Comment interpréter une valeur p?',
    'Explain the conditions for a binomial model.',
    'Comment interpréter les résidus d’une régression?',
    'What is the difference between association and causation?',
    'Expliquez la loi de Poisson avec un exemple du livre.'
  ];
  let offset=0;
  function examples(){
    $('examples').replaceChildren();
    for(let i=0;i<4;i++){const text=samples[(offset+i)%samples.length],b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=()=>{$('question').value=text;$('question').focus();};$('examples').append(b);}
    offset=(offset+4)%samples.length;
  }
  examples();$('shuffle').onclick=examples;
  try{$('reply-language').value=localStorage.getItem('accessedu-reply')||'auto';}catch{}
  $('reply-language').onchange=()=>{try{localStorage.setItem('accessedu-reply',$('reply-language').value);}catch{}};
  function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text)n.textContent=text;return n;}
  function label(node,en,fr){node.dataset.en=en;node.dataset.fr=fr;node.textContent=A.tr(en,fr);return node;}
  function actionBar(root,lang){
    const bar=el('div','answer-actions'),read=label(el('button'),'Read aloud','Lire à voix haute');read.type='button';
    read.onclick=()=>A.speak(root.textContent,lang,root);
    const fr=el('button','','→ Français canadien'),en=el('button','','→ English');fr.type=en.type='button';
    fr.onclick=()=>A.translate(root.textContent,'fr-CA');en.onclick=()=>A.translate(root.textContent,'en-CA');bar.append(read,fr,en);return bar;
  }
  function resultCards(results,query='',supported=new Set()){
    const details=el('details','results'),summary=label(el('summary'),'Retrieved passages · select text to read or translate','Passages trouvés · sélectionnez le texte pour le lire ou le traduire');details.append(summary);
    for(const r of results){
      const card=el('article','result-card'),heading=el('a','',`${r.title} · PDF ${r.page}${r.key?' · ['+r.key+']':''}`);heading.href=r.url;heading.target='_blank';heading.rel='noopener';
      const text=el('p','result-text');text.lang=r.language||'en-CA';text.dataset.speechLang=text.lang;
      const terms=[...new Set((query.toLowerCase().match(/[\p{L}\p{N}]+/gu)||[]).filter(w=>w.length>3))];
      const re=terms.length?new RegExp('('+terms.join('|')+')','ig'):null;
      if(re){let at=0;for(const m of r.text.matchAll(re)){text.append(document.createTextNode(r.text.slice(at,m.index)));text.append(el('mark','query-match',m[0]));at=m.index+m[0].length;}text.append(document.createTextNode(r.text.slice(at)));}else text.textContent=r.text;
      if(supported.has(r.key))text.classList.add('supported-result');
      const btn=label(el('button'),'Read passage','Lire le passage');btn.type='button';btn.onclick=()=>A.speak(text.textContent,text.lang,text);
      card.append(heading,text,btn);details.append(card);
    }
    return details;
  }
  function evidenceText(text,evidence){
    const root=el('div','prose'),byKey=new Map(evidence.map(e=>[e.key,e]));let at=0;
    for(const match of text.matchAll(/\[(S\d+)\]/g)){
      root.append(document.createTextNode(text.slice(at,match.index)));
      const e=byKey.get(match[1]);
      if(e){const a=el('a','citation',match[0]);a.href=e.url;a.target='_blank';a.rel='noopener';a.title=`${e.title} · PDF ${e.page}`;root.append(a);}else root.append(document.createTextNode(match[0]));
      at=match.index+match[0].length;
    }
    root.append(document.createTextNode(text.slice(at)));return root;
  }
  function webText(web){
    const root=el('div','prose');let at=0;
    // Provider offsets are Unicode character indexes. Use code points, not JS UTF-16 offsets.
    const chars=Array.from(web.text);
    const citations=[...web.citations].sort((a,b)=>a.start-b.start);
    for(const c of citations){
      if(c.start<at||c.end>chars.length||c.end<c.start)continue;
      let url;try{url=new URL(c.url);}catch{continue;}if(!['https:','http:'].includes(url.protocol))continue;
      root.append(document.createTextNode(chars.slice(at,c.start).join('')));
      const a=el('a','citation',`[${citations.indexOf(c)+1}]`);a.href=url.href;a.target='_blank';a.rel='noopener';a.title=c.title;root.append(a);at=c.end;
    }
    root.append(document.createTextNode(chars.slice(at).join('')));return root;
  }
  function message(question){
    const block=el('section','turn'),q=el('p','user-question',question);block.append(q);$('conversation').append(block);return block;
  }
  function render(block,data){
    const answer=el('article','answer panel');
    if(data.book_answer){
      answer.append(label(el('span','badge book'),'From the source','Tiré de la source'));
      const text=evidenceText(data.book_answer,data.evidence);text.lang=data.language;text.dataset.speechLang=data.language;answer.append(text,actionBar(text,data.language));
    }else{
      answer.append(label(el('span',`badge ${data.category==='out_of_scope'?'outside':'related'}`),data.category==='out_of_scope'?'Outside the subjects':'Related · not verified in source',data.category==='out_of_scope'?'Hors des sujets':'Connexe · non confirmé dans la source'));
      const text=el('div','prose',data.notice);text.lang=data.language;text.dataset.speechLang=data.language;answer.append(text,actionBar(text,data.language));
    }
    if(data.web){
      const section=el('section','web-section');section.append(label(el('span','badge related'),'Related · external web search','Connexe · recherche Web externe'));
      if(data.web.verified){const text=webText(data.web);text.lang=data.language;text.dataset.speechLang=data.language;section.append(text,actionBar(text,data.language));
        const list=el('ul','web-sources'),seen=new Set();for(const c of data.web.citations){if(seen.has(c.url))continue;seen.add(c.url);const li=el('li'),link=el('a','',c.title||new URL(c.url).hostname);link.href=c.url;link.target='_blank';link.rel='noopener';li.append(link);list.append(li);}section.append(list);
      }else section.append(label(el('p','muted'),'External search unavailable or returned no verifiable citations. No web-based claim is shown.','La recherche externe est indisponible ou n’a fourni aucune référence vérifiable. Aucune affirmation tirée du Web n’est affichée.'));
      answer.append(section);
    }
    if(data.results?.length)answer.append(resultCards(data.results,data.question||'',new Set(data.evidence.map(e=>e.key))));block.append(answer);A.localize(block);
  }
  let busy=false;
  function setBusy(value){busy=value;$('ask').disabled=value;$('local-search').disabled=value;$('status').textContent=value?A.tr('Searching sources and preparing a response… this may take a minute or two.','Recherche des sources et préparation d’une réponse… cela peut prendre une minute ou deux.'):'';$('conversation').setAttribute('aria-busy',String(value));}
  $('ask-form').onsubmit=async e=>{
    e.preventDefault();if(busy)return;const q=$('question').value.trim();if(!q)return;
    const block=message(q);setBusy(true);
    try{
      const r=await A.post('/api/ask',{question:q,language:$('reply-language').value,doc:$('doc').value,web:$('web').checked,history});r.question=q;render(block,r);
      history.push({role:'user',content:q},{role:'assistant',content:r.book_answer||r.notice||''});if(history.length>6)history.splice(0,history.length-6);$('question').value='';
      $('status').textContent=A.tr('Response ready.','Réponse prête.');
    }catch(err){const p=el('p','error',err.message);p.setAttribute('role','alert');block.append(p);}
    finally{setBusy(false);$('status').textContent=A.tr('Request finished. Check the response above.','Demande terminée. Consultez la réponse ci-dessus.');block.scrollIntoView({block:'start',behavior:'smooth'});}
  };
  $('local-search').onclick=async()=>{
    const q=$('question').value.trim();if(!q||busy)return;setBusy(true);const block=message(q);
    try{const response=await fetch('/api/search?'+new URLSearchParams({q,doc:$('doc').value}));const data=await response.json();if(!response.ok)throw Error(data.error||'Search failed');
      const panel=el('article','panel answer');panel.append(label(el('span','badge neutral'),'Local search · relevance not yet verified','Recherche locale · pertinence non encore vérifiée'));
      if(data.results.length){const cards=resultCards(data.results,q);cards.open=true;panel.append(cards);}else panel.append(label(el('p'),'No matching passages. Try different terms or use Ask for bilingual query expansion.','Aucun passage trouvé. Essayez d’autres termes ou utilisez Questionner pour une recherche bilingue enrichie.'));block.append(panel);
    }catch(err){block.append(el('p','error',err.message));}finally{setBusy(false);block.scrollIntoView({block:'start',behavior:'smooth'});}
  };
})();
