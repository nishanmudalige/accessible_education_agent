'use strict';
(() => {
  const $=id=>document.getElementById(id),A=window.AccessEdu;
  const source=$('page-text'),lang=document.querySelector('[data-source-language]').dataset.sourceLanguage;
  $('read-page').onclick=()=>A.speak(source.textContent,lang,source);
  $('translate-page').onclick=()=>A.translate(source.innerText,lang.startsWith('fr')?'en-CA':'fr-CA');
  $('highlights').onchange=e=>{document.body.classList.toggle('hide-evidence',!e.target.checked);};
  $('original-view').onchange=e=>{source.hidden=e.target.checked;$('page-figure').hidden=!e.target.checked;};
  document.querySelector('.source-block.evidence')?.scrollIntoView({block:'center'});
})();
