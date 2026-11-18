/* Kysely's original-page/overlay approach, adapted for multiple English/French books. */
(() => {
 'use strict';
 const $=id=>document.getElementById(id),A=window.AccessEdu;
 const root=$('main'),doc=root.dataset.doc,total=Number(root.dataset.pageCount),sourceLang=root.dataset.sourceLanguage||'en-CA';
 const frame=$('reader-image-frame'),image=$('reader-image'),scroller=$('reader-scroller'),text=$('page-text'),overlay=$('reader-highlights');
 const params=new URLSearchParams(location.search),initialPage=Number(params.get('page'))||1;
 const evidenceByPage=new Map([[initialPage,(params.get('ids')||'').split(',').filter(x=>/^p\d+$/.test(x))]]);
 const initialEvidence=[...(evidenceByPage.get(initialPage)||[])];
 let currentPage=initialPage,zoom=null,width=612,generation=0,pageData=null,activeQuery=params.get('q')||'',highlightEnabled=true,controller=null;
 function applyReaderMode(p=window.AccessDisplayPrefs?.get()||{readerMode:'page'}){
  const useText=p.readerMode==='text';frame.hidden=useText;$('reader-page-text').hidden=!useText;scroller.classList.toggle('text-first',useText);$('reader-text-toggle').setAttribute('aria-pressed',String(useText));setLabel($('reader-text-toggle'),useText?'Show original page':'Show page text',useText?'Afficher la page originale':'Afficher le texte');requestAnimationFrame(resize);
 }
 document.addEventListener('accessedu:displaychange',event=>applyReaderMode(event.detail));
 const saved=(key,fallback)=>{try{return localStorage.getItem('accessedu-'+key)||fallback;}catch{return fallback;}};
 const save=(key,val)=>{try{localStorage.setItem('accessedu-'+key,val);}catch{}};
 highlightEnabled=saved('reader-highlights','on')!=='off';
 $('reader-search').value=activeQuery;
 function bounded(page){return Math.max(1,Math.min(total,Math.floor(Number(page)||1)));}
 function setLabel(button,en,fr){button.dataset.en=en;button.dataset.fr=fr;button.textContent=A.tr(en,fr);}
 function status(en,fr){$('reader-status').textContent=A.tr(en,fr);}
 function pageUrl(page){
  const q=new URLSearchParams({doc,page});const ids=evidenceByPage.get(page)||[];if(ids.length)q.set('ids',ids.join(','));if(activeQuery)q.set('q',activeQuery);return '/reader?'+q;
 }
 function fitScale(){return Math.max(120,(scroller.clientWidth||innerWidth-80)-(innerWidth<740?18:48))/width;}
 function resize(){const scale=zoom===null?fitScale():zoom;frame.style.width=Math.round(width*scale)+'px';$('reader-zoom-level').textContent=zoom===null?A.tr('Fit width','Pleine largeur'):Math.round(scale*100)+'%';}
 function setSidebar(open,persist=true){$('reader-sidebar').hidden=!open;$('reader-layout').classList.toggle('no-sidebar',!open);$('reader-contents-toggle').setAttribute('aria-expanded',String(open));if(persist)save('reader-contents',open?'on':'off');requestAnimationFrame(resize);}
 setSidebar(saved('reader-contents',innerWidth>740?'on':'off')==='on',false);
 $('reader-contents-toggle').onclick=()=>setSidebar($('reader-sidebar').hidden);
 function drawBoxes(host,boxes,cls){host.replaceChildren();for(const r of boxes||[]){const n=document.createElement('span');n.className=cls;for(const [key,value] of Object.entries({left:r.x,top:r.y,width:r.w,height:r.h}))n.style[key]=value+'%';host.append(n);}}
 function updateHighlights(){
  document.body.classList.toggle('reader-highlight-hidden',!highlightEnabled);
  $('reader-highlight-toggle').setAttribute('aria-pressed',String(highlightEnabled));
  setLabel($('reader-highlight-toggle'),highlightEnabled?'Hide highlights':'Show highlights',highlightEnabled?'Masquer le surlignage':'Afficher le surlignage');
  const count=pageData?.boxes?.length||0;
  $('reader-read-highlights').disabled=!pageData?.passage_texts?.length;
  $('reader-highlight-note').hidden=!count;
  if(count)$('reader-highlight-note').textContent=A.tr('Outlined highlights mark source passages or search matches on this original page.','Les contours indiquent les passages sources ou les résultats de recherche sur cette page originale.');
 }
 function fillText(blocks){text.replaceChildren();for(const b of blocks){const p=document.createElement('p');p.className='source-block';if(pageData.selected_ids.includes(b.id))p.classList.add('evidence');p.id=b.id;p.dataset.passage=b.id;p.textContent=b.text;text.append(p,document.createTextNode('\n\n'));}}
 function scrollToEvidence(){if(!highlightEnabled||!pageData?.boxes?.length)return;if(window.AccessDisplayPrefs?.get().readerMode==='text'){text.querySelector('.evidence')?.scrollIntoView({block:'center'});return;}requestAnimationFrame(()=>{const first=pageData.boxes[0];scroller.scrollTop=Math.max(0,frame.offsetTop+first.y/100*frame.clientHeight-90);});}
 async function go(page,push=true){
  currentPage=bounded(page);const token=++generation;
  window.AccessSpeech?.clear();$('reader-speech-highlights').replaceChildren();controller?.abort();controller=new AbortController();
  $('reader-page').value=currentPage;$('reader-prev').disabled=currentPage===1;$('reader-next').disabled=currentPage===total;
  frame.classList.add('loading');frame.setAttribute('aria-busy','true');overlay.replaceChildren();text.replaceChildren();pageData=null;
  status('Opening page '+currentPage+'…','Ouverture de la page '+currentPage+'…');
  const query=new URLSearchParams();const ids=evidenceByPage.get(currentPage)||[];if(ids.length)query.set('ids',ids.join(','));if(activeQuery)query.set('q',activeQuery);
  const scale=zoom!==null&&zoom>2.3?3.5:2.5;
  const imageUrl='/page-image/'+encodeURIComponent(doc)+'/'+currentPage+'?scale='+scale;
  if(push)history.pushState({page:currentPage},'',pageUrl(currentPage));
  document.querySelectorAll('.reader-chapter').forEach(link=>{const chosen=Number(link.dataset.page)===currentPage;link.classList.toggle('active',chosen);if(chosen)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');});
  try{
   const picture=new Image(),textMode=window.AccessDisplayPrefs?.get().readerMode==='text';const ready=textMode?Promise.resolve():new Promise((resolve,reject)=>{picture.onload=resolve;picture.onerror=()=>reject(Error(A.tr('Could not load the page image.','Impossible de charger l’image de la page.')));picture.src=imageUrl;});
   const dataPromise=fetch('/api/reader/'+encodeURIComponent(doc)+'/'+currentPage+'?'+query,{signal:controller.signal}).then(async r=>{if(!r.ok)throw Error(A.tr('Could not load this PDF page.','Impossible de charger cette page PDF.'));return r.json();});
   const [data]=await Promise.all([dataPromise,ready]);if(token!==generation)return;
   pageData=data;width=data.width;text.lang=data.language;text.dataset.speechLang=data.language;
   image.src=imageUrl;image.alt=A.tr('Original textbook PDF page '+currentPage+' of '+total,'Page PDF originale '+currentPage+' sur '+total);image.width=picture.naturalWidth;image.height=picture.naturalHeight;image.style.aspectRatio=data.width+' / '+data.height;
   // CSS height:auto keeps the page and percentage overlay in the same coordinate system at every zoom.
   image.removeAttribute('height');image.removeAttribute('width');
   fillText(data.blocks);drawBoxes(overlay,data.boxes,'reader-highlight');resize();updateHighlights();applyReaderMode();
   frame.classList.remove('loading');frame.setAttribute('aria-busy','false');status('Page '+currentPage+' of '+total,'Page '+currentPage+' sur '+total);
   scroller.scrollTop=0;scroller.scrollLeft=0;scrollToEvidence();
  }catch(error){if(token!==generation||error.name==='AbortError')return;frame.classList.remove('loading');frame.setAttribute('aria-busy','false');$('reader-status').textContent=error.message;$('reader-status').classList.add('reader-error');}
 }
 function setZoom(value){zoom=value===null?null:Math.max(.3,Math.min(4,value));resize();if(zoom&&zoom>2.3&&pageData){const next='/page-image/'+encodeURIComponent(doc)+'/'+currentPage+'?scale=3.5';if(image.getAttribute('src')!==next)image.src=next;}}
 $('reader-zoom-in').onclick=()=>setZoom((zoom??fitScale())*1.2);$('reader-zoom-out').onclick=()=>setZoom((zoom??fitScale())/1.2);$('reader-fit').onclick=()=>setZoom(null);
 $('reader-prev').onclick=()=>go(currentPage-1);$('reader-next').onclick=()=>go(currentPage+1);$('reader-page').onchange=e=>go(e.target.value);$('reader-page').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();go(e.target.value);}};
 window.addEventListener('resize',resize);document.addEventListener('languagechange',()=>{resize();updateHighlights();if(pageData)status('Page '+currentPage+' of '+total,'Page '+currentPage+' sur '+total);});
 window.addEventListener('popstate',()=>{const p=new URLSearchParams(location.search),page=bounded(p.get('page'));activeQuery=p.get('q')||'';evidenceByPage.set(page,(p.get('ids')||'').split(',').filter(x=>/^p\d+$/.test(x)));go(page,false);});
 window.addEventListener('hashchange',()=>{const m=location.hash.match(/page=(\d+)/);if(m)go(m[1]);});
 document.querySelectorAll('.reader-chapter').forEach(link=>link.onclick=e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();go(link.dataset.page);if(innerWidth<=740)setSidebar(false);});
 document.addEventListener('keydown',e=>{if(e.altKey||e.ctrlKey||e.metaKey||e.shiftKey||/input|textarea|select|button/i.test(document.activeElement?.tagName||'')||document.querySelector('dialog[open]')||window.getSelection()?.toString())return;if(e.key==='ArrowRight'){e.preventDefault();go(currentPage+1);}if(e.key==='ArrowLeft'){e.preventDefault();go(currentPage-1);}});
 $('reader-document')?.addEventListener('change',e=>{location.href='/reader?'+new URLSearchParams({doc:e.target.value,page:1});});
 $('reader-highlight-toggle').onclick=()=>{highlightEnabled=!highlightEnabled;save('reader-highlights',highlightEnabled?'on':'off');updateHighlights();};
 $('reader-text-toggle').onclick=()=>{const mode=frame.hidden?'page':'text';if(window.AccessDisplayPrefs)window.AccessDisplayPrefs.set({readerMode:mode});else applyReaderMode({readerMode:mode});};
 $('read-page').onclick=()=>{if(pageData)A.speak(text.textContent,sourceLang,text);};
 $('reader-read-highlights').onclick=()=>{if(pageData?.passage_texts?.length)A.speak(pageData.passage_texts.join('\n\n'),sourceLang,text);};
 $('translate-page').onclick=()=>{if(pageData)A.translate(pageData.text,sourceLang.startsWith('fr')?'en-CA':'fr-CA');};
 async function copy(value){try{await navigator.clipboard.writeText(value);status('Link or text copied.','Lien ou texte copié.');}catch{status('Copy unavailable. Select the text or address manually.','Copie indisponible. Sélectionnez le texte ou l’adresse manuellement.');}}
 $('reader-copy').onclick=()=>copy(location.origin+pageUrl(currentPage));$('reader-copy-text').onclick=()=>{if(pageData)copy(pageData.text);};
 let searchGeneration=0;
 $('reader-search-form').onsubmit=async e=>{
  e.preventDefault();const q=$('reader-search').value.trim();if(q.length<2)return;const token=++searchGeneration;activeQuery=q;
  $('reader-chapters').hidden=true;$('reader-results').hidden=false;setSidebar(true);$('reader-results-list').replaceChildren();$('reader-results-count').textContent=A.tr('Searching this textbook…','Recherche dans ce manuel…');$('reader-search-form').classList.add('is-searching');
  try{
   const response=await fetch('/api/search?'+new URLSearchParams({q,doc}));if(!response.ok)throw Error('Search unavailable.');const data=await response.json();if(token!==searchGeneration)return;
   $('reader-results-count').textContent=data.results.length?A.tr(data.results.length+' matching passages',data.results.length+' passages trouvés'):A.tr('No matching passages.','Aucun passage trouvé.');
   for(const r of data.results){
    const card=document.createElement('article');card.className='reader-result';const link=document.createElement('a');link.href=r.url;link.textContent=A.tr('Page ','Page ')+r.page;
    const snippet=document.createElement('p');snippet.lang=r.language||sourceLang;snippet.dataset.speechLang=snippet.lang;snippet.textContent=r.text;
    const actions=document.createElement('div');actions.className='result-actions';
    const read=document.createElement('button');read.type='button';read.textContent=A.tr('▶ Read','▶ Lire');read.onclick=()=>A.speak(r.text,snippet.lang,snippet);
    const translate=document.createElement('button');translate.type='button';translate.textContent=snippet.lang.startsWith('fr')?'→ English':'→ Français';translate.onclick=()=>A.translate(r.text,snippet.lang.startsWith('fr')?'en-CA':'fr-CA');
    link.onclick=event=>{if(event.ctrlKey||event.metaKey||event.shiftKey)return;event.preventDefault();evidenceByPage.set(r.page,[r.id]);go(r.page);if(innerWidth<=740)setSidebar(false);};
    actions.append(read,translate);card.append(link,snippet,actions);$('reader-results-list').append(card);
   }
   go(currentPage);
  }catch(error){if(token===searchGeneration)$('reader-results-count').textContent=error.message;}
  finally{if(token===searchGeneration)$('reader-search-form').classList.remove('is-searching');}
 };
 $('reader-results-close').onclick=()=>{searchGeneration++;activeQuery='';evidenceByPage.clear();evidenceByPage.set(initialPage,initialEvidence);$('reader-results').hidden=true;$('reader-chapters').hidden=false;go(currentPage);};
 document.addEventListener('accessedu:speech',event=>{if(!pageData)return;const ids=event.detail?.root===text?event.detail.ids||[]:[];drawBoxes($('reader-speech-highlights'),pageData.blocks.filter(b=>ids.includes(b.id)).flatMap(b=>b.rects),'reader-speaking');});
 applyReaderMode();
 const hash=location.hash.match(/page=(\d+)/);if(hash)currentPage=bounded(hash[1]);history.replaceState({page:currentPage},'',pageUrl(currentPage));go(currentPage,false);
 window.AccessReader={goToPage:go,currentPage:()=>currentPage,fit:()=>setZoom(null)};
})();
