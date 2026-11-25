/* Kysely-style pop-up player, English / Canadian French, with sentence and PDF overlays. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),A=window.AccessEdu,panel=$('speech-player'),synth=window.speechSynthesis;
 const supported=Boolean(synth&&window.SpeechSynthesisUtterance);
 const buttons={play:$('speech-play'),pause:$('speech-pause'),back:$('speech-back'),next:$('speech-next'),restart:$('speech-restart'),stop:$('speech-stop')};
 let sourceLanguage=null;
 let voices=[],queue=[],index=0,token=0,playing=false,paused=false,finished=false,root=null,language='en-CA',marks=[];
 const pref=(key,fallback)=>{try{return localStorage.getItem('accessedu-'+key)||fallback;}catch{return fallback;}};
 const save=(key,value)=>{try{localStorage.setItem('accessedu-'+key,value);}catch{}};
 const french=new Set('le la les des une un du de est sont avec pour dans sur que qui comment pourquoi expliquer moyenne échantillon probabilité confiance hypothèse'.split(' '));
 const english=new Set('the a an and of is are with for in on that what how why explain mean sample probability confidence hypothesis'.split(' '));
 function detect(text,fallback){let fr=0,en=0;for(const w of text.toLowerCase().match(/[\p{L}’]+/gu)||[]){if(french.has(w))fr+=2;if(english.has(w))en+=2;if(/[éèêàçùœ]/.test(w))fr++;}return Math.abs(fr-en)<2?(fallback?.startsWith('fr')?'fr-CA':'en-CA'):fr>en?'fr-CA':'en-CA';}
 function clearHighlight(){if(window.CSS?.highlights)CSS.highlights.delete('speech');for(const mark of marks){const p=mark.parentNode;if(p){mark.replaceWith(document.createTextNode(mark.textContent));p.normalize();}}marks=[];document.dispatchEvent(new CustomEvent('accessedu:speech',{detail:{root:null,ids:[]}}));}
 function highlight(segment){
  clearHighlight();if(!root?.isConnected||segment.offset<0)return;
  const start=segment.offset,end=start+segment.text.length,walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node,offset=0,nodes=[];
  while((node=walker.nextNode())){nodes.push({node,start:offset,end:offset+node.length});offset+=node.length;}
  const chosen=nodes.filter(n=>n.end>start&&n.start<end);if(!chosen.length)return;
  const range=document.createRange();range.setStart(chosen[0].node,start-chosen[0].start);range.setEnd(chosen.at(-1).node,end-chosen.at(-1).start);
  const ids=[...new Set(chosen.map(n=>n.node.parentElement.closest('[data-passage]')?.dataset.passage).filter(Boolean))];
  if(window.CSS?.highlights&&window.Highlight)CSS.highlights.set('speech',new Highlight(range));
  else for(const n of [...chosen].reverse()){if(n.node.parentElement.closest('mjx-container'))continue;const begin=Math.max(0,start-n.start),length=Math.min(n.end,end)-Math.max(n.start,start),part=n.node.splitText(begin);part.splitText(length);const mark=document.createElement('mark');mark.className='speaking';part.replaceWith(mark);mark.append(part);marks.push(mark);}
  document.dispatchEvent(new CustomEvent('accessedu:speech',{detail:{root,ids,text:segment.text,index,language}}));
 }
 function state(){
  const ready=queue.length>0;
  for(const key of ['back','next','restart','stop'])buttons[key].disabled=!ready;
  buttons.play.disabled=!supported||!ready||(playing&&!paused);buttons.pause.disabled=!playing||paused;
  const number=ready?Math.min(index+1,queue.length):0;
  $('speech-progress').textContent=ready?`${number} / ${queue.length} · `+A.tr(finished?'Finished':paused?'Paused':playing?'Reading':'Ready',finished?'Terminé':paused?'En pause':playing?'Lecture':'Prêt'):A.tr('Ready to read','Prêt à lire');
  $('speech-timeline').max=Math.max(1,queue.length);$('speech-timeline').value=finished?queue.length:ready?index:0;
 }
 function voiceFor(lang){const chosen=voices.find(v=>v.voiceURI===$('speech-voice').value);if(chosen&&chosen.lang.slice(0,2).toLowerCase()===lang.slice(0,2))return chosen;
  const list=voices.filter(v=>v.lang.toLowerCase().startsWith(lang.slice(0,2)));list.sort((a,b)=>score(b,lang)-score(a,lang));return list[0]||null;}
 function score(v,lang){return (v.lang.toLowerCase()===lang.toLowerCase()?100:0)+(/natural|premium|enhanced|neural|google|siri/i.test(v.name)?8:0)+(v.localService?1:0);}
 function voiceNotice(){
  if(!supported){$('speech-notice').textContent=A.tr('Read-aloud is unavailable in this browser.','La lecture vocale est indisponible dans ce navigateur.');return;}
  const voice=voiceFor(language),exact=voice?.lang.toLowerCase()===language.toLowerCase();
  $('speech-detected').textContent=language==='fr-CA'?A.tr('Canadian French','Français canadien'):A.tr('English','Anglais');
  $('speech-notice').textContent=language==='fr-CA'&&!exact?A.tr('A fr-CA voice is not selected or available. Another French voice may be used; install a Canadian French voice for that accent.','Aucune voix fr-CA n’est sélectionnée ou disponible. Une autre voix française peut être utilisée; installez une voix canadienne-française pour cet accent.'):A.tr('Uses your device’s voices. You can change the voice and reading speed.','Utilise les voix de votre appareil. Vous pouvez changer la voix et la vitesse.');
 }
 function loadVoices(){if(!supported)return;voices=synth.getVoices().filter(v=>/^(en|fr)(-|$)/i.test(v.lang));const selected=pref('voice','');$('speech-voice').replaceChildren(new Option(A.tr('Automatic — best available','Automatique — meilleure voix disponible'),''));for(const v of voices.sort((a,b)=>(a.lang+a.name).localeCompare(b.lang+b.name)))$('speech-voice').add(new Option(v.name+' ('+v.lang+')',v.voiceURI));if(voices.some(v=>v.voiceURI===selected))$('speech-voice').value=selected;voiceNotice();}
 function halt(reset=false){token++;playing=false;paused=false;synth?.cancel();clearHighlight();if(reset){index=0;finished=false;}state();}
 function show(){const dialog=$('translation-dialog');if(dialog.open&&panel.parentElement!==dialog)dialog.append(panel);else if(!dialog.open&&panel.parentElement!==document.body)document.body.append(panel);panel.hidden=false;}
 function play(){
  if(!supported||!queue.length)return;
  if(paused){synth.resume();paused=false;playing=true;state();return;}
  if(finished||index>=queue.length){index=0;finished=false;}
  const id=++token;synth.cancel();playing=true;paused=false;
  const segment=queue[index],utterance=new SpeechSynthesisUtterance(segment.text),lang=sourceLanguage||detect(segment.text,language),voice=voiceFor(lang);
  utterance.lang=lang;if(voice)utterance.voice=voice;utterance.rate=Number($('speech-rate').value)||1;utterance.pitch=1;
  highlight(segment);voiceNotice();state();
  utterance.onend=()=>{if(id!==token)return;if(index+1<queue.length){index++;playing=false;play();}else{playing=false;paused=false;finished=true;clearHighlight();state();}};
  utterance.onerror=event=>{if(id!==token||['canceled','interrupted'].includes(event.error))return;playing=false;paused=false;clearHighlight();$('speech-notice').textContent=A.tr('Playback failed. Try a different voice.','La lecture a échoué. Essayez une autre voix.');state();};
  try{synth.speak(utterance);}catch{playing=false;$('speech-notice').textContent=A.tr('The browser could not start speech.','Le navigateur n’a pas pu démarrer la lecture.');state();}
 }
 function readText(input,fallback='en-CA',host=null,fixedLanguage=false){
  sourceLanguage=fixedLanguage?fallback:null;
  const raw=String(input||'').trim();show();halt(true);queue=[];root=host;language=sourceLanguage||detect(raw,fallback);
  if(!raw){$('speech-notice').textContent=A.tr('No text is available on this page.','Aucun texte n’est disponible sur cette page.');return;}
  let sentences;try{sentences=[...new Intl.Segmenter(language,{granularity:'sentence'}).segment(raw)].map(x=>x.segment.trim());}catch{sentences=raw.split(/(?<=[.!?])\s+|\n+/);}
  queue=[];const full=root?.textContent||'';let cursor=0;
  function add(text){if(!text)return;let at=full.indexOf(text,cursor);if(at<0)at=full.indexOf(text);queue.push({text,offset:at});if(at>=0)cursor=at+text.length;}
  for(let s of sentences){while(s.length>240){let at=s.lastIndexOf(' ',220);if(at<40)at=220;add(s.slice(0,at));s=s.slice(at).trimStart();}add(s);}
  const count=raw.split(/\s+/).length;$('speech-preview').textContent=count+A.tr(' words · ',' mots · ')+raw.slice(0,205)+(raw.length>205?'…':'');voiceNotice();state();play();
 }
 buttons.play.onclick=play;buttons.pause.onclick=()=>{if(!playing||paused||!supported)return;synth.pause();paused=true;state();};
 buttons.stop.onclick=()=>halt(true);
 function jump(target){if(!queue.length)return;halt();finished=false;index=Math.max(0,Math.min(queue.length-1,target));play();}
 buttons.restart.onclick=()=>jump(0);buttons.back.onclick=()=>jump(index-1);buttons.next.onclick=()=>jump(index+1);
 $('speech-close').onclick=()=>{halt(true);panel.hidden=true;};
 $('speech-rate').value=pref('rate','1');
 $('speech-rate').onchange=()=>{save('rate',$('speech-rate').value);if(playing&&!paused){halt();play();}};
 $('speech-voice').onchange=()=>{save('voice',$('speech-voice').value);voiceNotice();if(playing&&!paused){halt();play();}};
 $('translation-dialog').addEventListener('close',()=>{if(panel.parentElement!==document.body)document.body.append(panel);});
 document.addEventListener('languagechange',()=>{voiceNotice();state();loadVoices();});
 window.addEventListener('pagehide',()=>halt());
 if(supported){loadVoices();synth.addEventListener?.('voiceschanged',loadVoices);}voiceNotice();state();
 window.AccessSpeech={readText,stop:()=>halt(true),clear:()=>{halt(true);queue=[];root=null;$('speech-preview').textContent='';state();},detectLanguage:detect,state:()=>({playing,paused,index,count:queue.length,language})};
})();
