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
  let theme=readPref('theme','light');
  function setTheme(){document.documentElement.dataset.theme=theme;$('theme').setAttribute('aria-pressed',String(theme==='dark'));}
  setTheme(); $('theme').onclick=()=>{theme=theme==='dark'?'light':'dark';save('theme',theme);setTheme();};
  let size=Math.min(24,Math.max(16,Number(readPref('font','18'))||18));
  function font(){document.documentElement.style.setProperty('--base-font',size+'px');save('font',size);}
  font(); $('font-up').onclick=()=>{size=Math.min(24,size+1);font();};$('font-down').onclick=()=>{size=Math.max(16,size-1);font();};

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
    if(node.closest('#selection-tools,.speech-bar,textarea,input,select,header,footer'))return;
    const root=node.closest('[data-speech-lang],.prose,.source-block,.result-text,#page-text')||node;
    selection={text,root,lang:root.closest('[lang]')?.lang||ui};
    $('selection-tools').hidden=false;
  }
  document.addEventListener('selectionchange',()=>{clearTimeout(window._selectionTimer);window._selectionTimer=setTimeout(currentSelection,100);});
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

  const synth=window.speechSynthesis;
  let voices=[], segments=[], cursor=0, token=0, paused=false, speaking=false, speechRoot=null, speechLang='en-CA';
  const speechStatus=$('speech-status');
  let marked=[];
  function clearHighlight(){
    if(window.CSS?.highlights)CSS.highlights.delete('speech');
    for(const mark of marked){const p=mark.parentNode;if(p){mark.replaceWith(document.createTextNode(mark.textContent));p.normalize();}}marked=[];
  }
  function highlight(text){
    clearHighlight(); if(!speechRoot || !speechRoot.isConnected)return;
    const walker=document.createTreeWalker(speechRoot,NodeFilter.SHOW_TEXT);let node,all='',nodes=[];
    while((node=walker.nextNode())){nodes.push({node,start:all.length,end:all.length+node.textContent.length});all+=node.textContent;}
    const start=all.indexOf(text);if(start<0)return;const end=start+text.length;
    const first=nodes.find(n=>n.end>start),last=nodes.find(n=>n.end>=end);
    if(!first||!last)return;
    const range=document.createRange();range.setStart(first.node,start-first.start);range.setEnd(last.node,end-last.start);
    if(window.CSS?.highlights&&window.Highlight){CSS.highlights.set('speech',new Highlight(range));}
    else { // Per-text-node marks avoid restructuring links, paragraphs or controls.
      for(const n of nodes.filter(n=>n.end>start&&n.start<end).reverse()){
        const localStart=Math.max(0,start-n.start),localEnd=Math.min(n.node.length,end-n.start);
        const part=n.node.splitText(localStart);part.splitText(localEnd-localStart);
        const mark=document.createElement('mark');mark.className='speaking';part.replaceWith(mark);mark.append(part);marked.push(mark);
      }
    }
  }
  function voiceList(){
    if(!synth)return;voices=synth.getVoices().filter(v=>/^(en|fr)(-|$)/i.test(v.lang));
    const selected=readPref('voice','');$('voice').replaceChildren(new Option('Automatic / Automatique',''));
    for(const v of voices)$('voice').add(new Option(v.name+' · '+v.lang,v.voiceURI));
    if(voices.some(v=>v.voiceURI===selected))$('voice').value=selected;
  }
  $('voice').onchange=()=>save('voice',$('voice').value);
  $('rate').value=readPref('rate','1');$('rate').onchange=()=>save('rate',$('rate').value);
  function chooseVoice(lang){
    const selected=voices.find(v=>v.voiceURI===$('voice').value);
    if(selected&&selected.lang.slice(0,2)===lang.slice(0,2))return selected;
    return voices.find(v=>v.lang.toLowerCase()===lang.toLowerCase())||voices.find(v=>v.lang.slice(0,2)===lang.slice(0,2));
  }
  function stop(){token++;synth?.cancel();speaking=false;paused=false;clearHighlight();speechStatus.textContent='';}
  function play(){
    if(!synth||cursor>=segments.length){stop();return;}
    const thisToken=++token;synth.cancel();paused=false;speaking=true;
    const voice=chooseVoice(speechLang),u=new SpeechSynthesisUtterance(segments[cursor]);u.lang=speechLang;
    if(voice)u.voice=voice;u.rate=Number($('rate').value)||1;
    const fallback=speechLang==='fr-CA'&&(!voice||voice.lang.toLowerCase()!=='fr-ca');
    speechStatus.textContent=`${cursor+1}/${segments.length} · ${voice?voice.name:speechLang}`+(fallback?tr(' · Canadian French voice unavailable; install one for this accent.',' · Voix canadienne-française indisponible; installez-en une pour cet accent.'):'');
    highlight(segments[cursor]);u.onend=()=>{if(thisToken!==token)return;cursor++;if(cursor<segments.length)play();else stop();};
    u.onerror=e=>{if(thisToken===token&&e.error!=='interrupted'&&e.error!=='canceled'){stop();speechStatus.textContent=tr('Speech unavailable. Check your browser voices.','Lecture indisponible. Vérifiez les voix du navigateur.');}};
    synth.speak(u);
  }
  function speak(text,lang,root){
    if(!synth){speechStatus.textContent=tr('This browser does not support read-aloud.','Ce navigateur ne prend pas en charge la lecture vocale.');return;}
    stop();speechRoot=root;speechLang=lang?.startsWith('fr')?'fr-CA':'en-CA';
    const raw=String(text||'').trim();if(!raw)return;
    let sentences;
    try{sentences=[...new Intl.Segmenter(speechLang,{granularity:'sentence'}).segment(raw)].map(s=>s.segment.trim());}
    catch{sentences=raw.split(/(?<=[.!?])\s+|\n+/);}
    // Short utterances reduce browser truncation; exact text survives for highlighting.
    segments=[];
    for(let s of sentences){while(s.length>220){let at=s.lastIndexOf(' ',210);if(at<40)at=210;segments.push(s.slice(0,at));s=s.slice(at).trimStart();}if(s)segments.push(s);}
    cursor=0;if(segments.length)play();
  }
  $('read-selection').onclick=()=>speak(selection.text,selection.lang,selection.root);
  $('read-translation').onclick=()=>speak($('translation-text').textContent,$('translation-text').lang,$('translation-text'));
  $('speech-stop').onclick=stop;
  $('speech-pause').onclick=()=>{if(!synth||!speaking)return;if(paused)synth.resume();else synth.pause();paused=!paused;};
  $('speech-back').onclick=()=>{if(!segments.length)return;cursor=Math.max(0,cursor-1);play();};
  $('speech-next').onclick=()=>{if(!segments.length)return;cursor=Math.min(segments.length-1,cursor+1);play();};
  if(synth){voiceList();synth.addEventListener('voiceschanged',voiceList);}else speechStatus.textContent='Read-aloud unavailable / Lecture vocale indisponible';
  window.addEventListener('pagehide',stop);
  window.AccessEdu={post,tr,localize,translate,speak,lang:()=>ui,selection:()=>selection};
})();
