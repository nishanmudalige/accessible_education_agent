/* Accessible display controls. Native dialog/radios retain keyboard semantics. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),D=window.AccessDisplayPrefs,A=window.AccessEdu,dialog=$('accessibility-dialog');
 const libraryToggle=$('library-toggle');
 function syncLibrary(simple){
   if(!libraryToggle)return;
   libraryToggle.setAttribute('aria-expanded',String(!simple));
   $('library-toggle-label').textContent=simple?A.tr('Show library','Afficher la bibliothèque'):A.tr('Hide library','Masquer la bibliothèque');
 }
 if(libraryToggle)libraryToggle.onclick=()=>{
   D.set({focusMode:!D.get().focusMode});
   libraryToggle.focus();
 };
 function sync(){const p=D.get();syncLibrary(p.focusMode);document.querySelectorAll('[data-pref]').forEach(control=>{const value=p[control.dataset.pref];if(control.type==='radio')control.checked=control.value===value;else if(control.type==='checkbox')control.checked=Boolean(value);else control.value=String(value);});$('display-size-value').textContent=p.textSize+' px';$('display-size').setAttribute('aria-valuetext',p.textSize+A.tr(' pixels',' pixels'));$('theme').setAttribute('aria-pressed',String(document.documentElement.dataset.theme==='dark'));$('theme').setAttribute('aria-label',A.tr('Switch light or dark appearance','Passer à un affichage clair ou sombre'));$('reading-guide').hidden=!p.readingGuide;$('font-down').disabled=p.textSize<=16;$('font-up').disabled=p.textSize>=36;}
 function announce(en='Display preferences saved.',fr='Préférences d’affichage enregistrées.'){$('accessibility-status').textContent=A.tr(en,fr);}
 function update(change){D.set(change);sync();announce();}
 $('accessibility-open').onclick=()=>{sync();dialog.showModal();};
 function close(){dialog.close();$('accessibility-open').focus();}
 $('accessibility-close').onclick=close;$('accessibility-done').onclick=close;dialog.addEventListener('close',()=>$('accessibility-open').focus());
 dialog.addEventListener('change',event=>{const c=event.target;if(!c.matches('[data-pref]'))return;update({[c.dataset.pref]:c.type==='checkbox'?c.checked:c.value});});
 $('display-size').addEventListener('input',event=>{D.set({textSize:Number(event.target.value)});sync();});
 $('font-up').onclick=()=>update({textSize:D.get().textSize+1});$('font-down').onclick=()=>update({textSize:D.get().textSize-1});
 $('theme').onclick=()=>{const p=D.get(),dark=p.appearance.endsWith('dark'),high=p.appearance.startsWith('contrast');update({appearance:high?(dark?'contrast-light':'contrast-dark'):(dark?'light':'dark')});};
 const presets={
  'default':()=>({...D.defaults(),vision:D.get().vision,highlight:D.get().highlight}),
  'low-vision':()=>({...D.defaults(),vision:D.get().vision,highlight:D.get().highlight,appearance:'contrast-light',textSize:24,lineHeight:1.9,letterSpacing:.05,paragraphSpacing:1.5,largeTargets:true,reduceMotion:true,readerMode:'text'}),
  'low-glare':()=>({...D.defaults(),vision:D.get().vision,highlight:D.get().highlight,appearance:'dark',textSize:20,lineHeight:1.9,paragraphSpacing:1.5,reduceMotion:true})
 };
 document.querySelectorAll('[data-display-preset]').forEach(button=>button.onclick=()=>{D.set(presets[button.dataset.displayPreset]());sync();announce('Reading preset applied. You can adjust any setting below.','Préréglage appliqué. Vous pouvez ajuster chaque option ci-dessous.');});
 $('accessibility-reset').onclick=()=>{D.reset();sync();announce('Display reset. Your language and voice preferences were kept.','Affichage réinitialisé. Vos préférences de langue et de voix sont conservées.');};
 document.addEventListener('accessedu:displaychange',sync);document.addEventListener('languagechange',sync);
 function guideAt(y){if(!D.get().readingGuide)return;$('reading-guide').style.top=Math.max(0,Math.min(innerHeight-82,y-41))+'px';}
 document.addEventListener('pointermove',e=>guideAt(e.clientY),{passive:true});document.addEventListener('focusin',e=>{if(e.target.closest('dialog'))return;const r=e.target.getBoundingClientRect();guideAt(r.top+r.height/2);});
 guideAt(innerHeight/2);sync();
})();
