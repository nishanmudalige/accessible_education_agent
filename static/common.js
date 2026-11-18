'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const readPref = (key, fallback) => { try { return localStorage.getItem('accessedu-'+key) || fallback; } catch { return fallback; } };
  const save = (key,val) => { try { localStorage.setItem('accessedu-'+key,val); } catch {} };
  let ui = readPref('language','en-CA');
  if (!['en-CA','fr-CA'].includes(ui)) ui='en-CA';
  const tr = (en,fr) => ui === 'fr-CA' ? fr : en;
  function localize(root=document) {
    root.querySelectorAll('[data-en][data-fr]').forEach(el => {el.textContent=ui==='fr-CA'?el.dataset.fr:el.dataset.en;});
  }
  function language(value) {
    ui=value; save('language',ui); document.documentElement.lang=ui; $('ui-language').value=ui;
    localize(); document.dispatchEvent(new CustomEvent('languagechange'));
  }
  $('ui-language').addEventListener('change',e=>language(e.target.value)); language(ui);

  async function post(path,data){
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify(data)});
    let result; try {result=await response.json();} catch {throw Error(tr('The server did not return a usable response. Reload and try again.','Le serveur n’a pas renvoyé de réponse utilisable. Rechargez la page et réessayez.'));}
    if(!response.ok)throw Error(result.error||'Request failed');return result;
  }

  let selection={text:'',root:null,lang:'en-CA'};
  function currentSelection(){
    const s=window.getSelection(); if(!s || !s.rangeCount || s.isCollapsed)return;
    const text=s.toString().trim();if(!text)return;
    let node=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentElement;
    if(node.closest('#selection-tools,#speech-player,textarea,input,select,header,footer'))return;
    const root=node.closest('[data-speech-lang],.prose,.source-block,.result-text,#page-text')||node;
    selection={text,root,lang:root.closest('[lang]')?.lang||ui};
    const tools=$('selection-tools'); tools.hidden=false;
    const rect=s.getRangeAt(0).getBoundingClientRect?.();
    if(rect){tools.style.left=Math.max(10,Math.min(innerWidth-330,rect.left))+'px';tools.style.top=Math.max(10,Math.min(innerHeight-70,rect.bottom+8))+'px';tools.style.right='auto';tools.style.bottom='auto';}

  }
  document.addEventListener('selectionchange',()=>{clearTimeout(window._selectionTimer);window._selectionTimer=setTimeout(currentSelection,100);});
  document.addEventListener('pointerdown',event=>{if(!event.target.closest('#selection-tools,#speech-player'))$('selection-tools').hidden=true;});
  $('selection-tools').addEventListener('pointerdown',event=>event.preventDefault());
  window.addEventListener('scroll',()=>$('selection-tools').hidden=true,true);
  $('close-translation').onclick=()=>$('translation-dialog').close();
  async function translate(text,target){
    const output=$('translation-text'), dialog=$('translation-dialog');
    output.textContent=tr('Translating…','Traduction en cours…');output.lang=target;output.dataset.speechLang=target;
    $('translation-note').textContent='';$('read-translation').disabled=true;
    if(!dialog.open)dialog.showModal();
    try {const r=await post('/api/translate',{text,target});output.textContent=r.text;$('translation-note').textContent=r.notice;}
    catch(e){output.textContent=e.message;}
    finally{$('read-translation').disabled=false;output.focus();}
  }
  $('translate-fr').onclick=()=>translate(selection.text,'fr-CA');$('translate-en').onclick=()=>translate(selection.text,'en-CA');

  const speak=(text,lang,root)=>window.AccessSpeech?.readText(text,lang,root);
  $('read-selection').onclick=()=>speak(selection.text,selection.lang,selection.root);
  $('read-translation').onclick=()=>speak($('translation-text').textContent,$('translation-text').lang,$('translation-text'));
  window.AccessEdu={post,tr,localize,translate,speak,lang:()=>ui,selection:()=>selection};
})();
