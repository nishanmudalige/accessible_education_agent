'use strict';
(() => {
  const status=document.getElementById('citation-status');
  const french=status.dataset.sourceLang.startsWith('fr');
  const id=new URLSearchParams(location.search).get('hl');
  const target=id?document.getElementById(id):null;
  const $=id=>document.getElementById(id);
  const chapter=document.querySelector('.chapter-content');
  const actions=window.AccessEdu;
  const toggle=$('reader-highlight-toggle');
  const readHighlights=$('reader-read-highlights');
  toggle.disabled=true;

  function paragraphs(root){
    // Keep paragraph boundaries even when the imported HTML is on a single line.
    const formulas=new Map();
    for(const item of window.MathJax?.startup?.document?.getMathItemsWithin(root)||[]){
      formulas.set(item.typesetRoot,item.math);
    }
    const lines=[];
    let line='';
    function flush(){
      const text=line.replace(/\s+/g,' ').trim();
      if(text)lines.push(text);
      line='';
    }
    function visit(node){
      if(node.nodeType===3){line+=node.nodeValue;return;}
      if(node.nodeType!==1 || node.matches('script,style,[hidden],mjx-assistive-mml'))return;
      if(formulas.has(node)){line+=' '+formulas.get(node)+' ';return;}
      if(node.matches('img')){line+=' '+node.alt+' ';return;}
      const block=node.matches('p,div,section,article,aside,figure,figcaption,li,dt,dd,h1,h2,h3,h4,h5,h6,blockquote,pre,br,tr,th,td,summary');
      if(block)flush();
      for(const child of node.childNodes)visit(child);
      if(block)flush();
    }
    visit(root);flush();
    return lines;
  }

  function translationBatches(lines){
    const limit=14000, batches=[];
    let batch='';
    for(let line of lines){
      if(batch && batch.length+2+line.length>limit){batches.push(batch);batch='';}
      while(line.length>limit){
        let end=line.lastIndexOf(' ',limit);
        if(end<=0)end=/[\uD800-\uDBFF]/.test(line[limit-1])?limit-1:limit;
        batches.push(line.slice(0,end));line=line.slice(end).trimStart();
      }
      batch=batch?batch+'\n\n'+line:line;
    }
    if(batch)batches.push(batch);
    return batches;
  }

  function read(root){actions.speak(paragraphs(root).join('\n\n'),status.dataset.sourceLang,root);}
  toggle.onclick=()=>{
    const visible=toggle.getAttribute('aria-pressed')!=='true';
    chapter.classList.toggle('hide-citation',!visible);
    toggle.setAttribute('aria-pressed',String(visible));
    toggle.dataset.en=visible?'Hide highlights':'Show highlights';
    toggle.dataset.fr=visible?'Masquer le surlignage':'Afficher le surlignage';
    toggle.textContent=actions.tr(toggle.dataset.en,toggle.dataset.fr);
  };
  readHighlights.onclick=()=>read(target);
  $('read-page').onclick=()=>read(chapter);
  $('translate-page').onclick=()=>{
    const batches=translationBatches(paragraphs(chapter));
    if(batches.length)actions.translate(batches,french?'en-CA':'fr-CA');
  };
  $('reader-copy').onclick=()=>actions.copy(location.href,(en,fr)=>{status.textContent=actions.tr(en,fr);});
  function locate(){
    if(!id)return;
    if(!target||!target.closest('.chapter-content')){
      status.textContent=french?'Le passage cité est introuvable sur cette page.':'The cited passage could not be found on this page.';return;
    }
    for(let ancestor=target.parentElement;ancestor;ancestor=ancestor.parentElement){
      if(ancestor.tagName==='DETAILS')ancestor.open=true;
    }
    toggle.disabled=false;readHighlights.disabled=false;
    target.classList.add('cited-passage');target.setAttribute('tabindex','-1');
    target.setAttribute('aria-describedby','citation-status');
    status.textContent=french?'Passage cité mis en évidence.':'Cited passage highlighted.';
    target.scrollIntoView({block:'center',behavior:'auto'});target.focus({preventScroll:true});
  }
  const math=window.MathJax?.startup?.promise;
  function ready(){
    const done=()=>requestAnimationFrame(()=>requestAnimationFrame(locate));
    if(math)math.then(done).catch(()=>{locate();status.textContent+=(french?' Le rendu des formules a échoué.':' Formula rendering failed.');});
    else done();
  }
  if(document.readyState==='complete')ready();else window.addEventListener('load',ready,{once:true});
})();
