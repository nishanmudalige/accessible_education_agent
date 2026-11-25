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
    if(response.status===429)throw Error(tr('Request limit reached. Please wait a minute before trying again.','Limite de requêtes atteinte. Veuillez patienter une minute avant de réessayer.'));
    let result; try {result=await response.json();} catch {throw Error(tr('The server did not return a usable response. Reload and try again.','Le serveur n’a pas renvoyé de réponse utilisable. Rechargez la page et réessayez.'));}
    if(!response.ok)throw Error(result.error||'Request failed');return result;
  }

  let selection={text:'',root:null,lang:'en-CA'};
  let selectedFormulas=new Set();
  function markSelection(formulas){
    for(const el of selectedFormulas)if(!formulas.has(el))el.classList.remove('selection-math');
    for(const el of formulas)if(!selectedFormulas.has(el))el.classList.add('selection-math');
    selectedFormulas=formulas;
  }
  function currentSelection(){
    const s=window.getSelection(); if(!s || !s.rangeCount || s.isCollapsed){
      markSelection(new Set());selection.range=null;$('selection-tools').hidden=true;return;
    }
    const text=s.toString().trim();
    let node=s.anchorNode.nodeType===1?s.anchorNode:s.anchorNode.parentElement;
    if(node.closest('#selection-tools,#speech-player,textarea,input,select,header,footer')){
      markSelection(new Set());selection.range=null;$('selection-tools').hidden=true;return;
    }
    const {range,formulas}=window.AccessSpeechText.mathSelection(s.getRangeAt(0));
    markSelection(formulas);
    const root=node.closest('[data-speech-lang],.prose,.source-block,.result-text,#page-text,.chapter-content')||node;
    selection={text,root,range,lang:root.closest('[lang]')?.lang||ui};
    const tools=$('selection-tools'); tools.hidden=false;
    const rect=s.getRangeAt(0).getBoundingClientRect?.();
    if(rect){tools.style.left=Math.max(10,Math.min(innerWidth-330,rect.left))+'px';tools.style.top=Math.max(10,Math.min(innerHeight-70,rect.bottom+8))+'px';tools.style.right='auto';tools.style.bottom='auto';}

  }
  document.addEventListener('selectionchange',currentSelection);
  document.addEventListener('pointerdown',event=>{if(!event.target.closest('#selection-tools,#speech-player'))$('selection-tools').hidden=true;});
  $('selection-tools').addEventListener('pointerdown',event=>event.preventDefault());
  window.addEventListener('scroll',()=>$('selection-tools').hidden=true,true);
  $('close-translation').onclick=()=>$('translation-dialog').close();
  let translationRequest=0;
  async function translate(input,target){
    const batches=Array.isArray(input)?input:[input];
    const request=++translationRequest;
    const output=$('translation-text'), dialog=$('translation-dialog'), note=$('translation-note');
    output.textContent=tr('Translating…','Traduction en cours…');output.lang=target;output.dataset.speechLang=target;
    note.textContent='';$('read-translation').disabled=true;
    if(!dialog.open)dialog.showModal();
    const current=()=>request===translationRequest && dialog.open;
    let completed=0;
    const progress=()=>batches.length>1?tr('Batches translated','Lots traduits')+' '+completed+'/'+batches.length+'. ':'';
    try {
      note.textContent=progress();
      for(const text of batches){
        const r=await post('/api/translate',{text,target});
        if(!current())return;
        if(!completed)output.textContent='';
        output.append(document.createTextNode((completed?'\n\n':'')+r.text));
        completed++;
        note.textContent=progress()+(r.notice||'');
      }
    } catch(e){
      if(!current())return;
      if(!completed)output.textContent='';
      note.textContent=progress()+e.message;
    } finally{
      if(current()){$('read-translation').disabled=!completed;output.focus();}
    }
  }
  $('translate-fr').onclick=()=>translate(selection.text,'fr-CA');$('translate-en').onclick=()=>translate(selection.text,'en-CA');

  let speechRequest=0;
  async function speak(source,lang,root=source){
    const request=++speechRequest;
    const {text,hasMedia}=await window.AccessSpeechText(source,lang);
    if(request!==speechRequest)return;
    window.AccessSpeech?.readText(text,lang,root,hasMedia);
  }
  $('read-selection').onclick=()=>{
    if(!window.getSelection()?.isCollapsed)currentSelection();
    if(selection.range)speak(selection.range,selection.lang,selection.root);
  };
  $('read-translation').onclick=()=>speak($('translation-text'),$('translation-text').lang);
  async function copy(value,status){
    try{await navigator.clipboard.writeText(value);status('Link or text copied.','Lien ou texte copié.');}
    catch{status('Copy unavailable. Select the text or address manually.','Copie indisponible. Sélectionnez le texte ou l’adresse manuellement.');}
  }
  window.AccessEdu={copy,post,tr,localize,translate,speak,lang:()=>ui,selection:()=>selection};
})();
