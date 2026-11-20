'use strict';
(() => {
  const status=document.getElementById('citation-status');
  const french=status.dataset.sourceLang.startsWith('fr');
  const id=new URLSearchParams(location.search).get('hl');
  const target=id?document.getElementById(id):null;
  function locate(){
    if(!id)return;
    if(!target||!target.closest('.chapter-content')){
      status.textContent=french?'Le passage cité est introuvable sur cette page.':'The cited passage could not be found on this page.';return;
    }
    for(let ancestor=target.parentElement;ancestor;ancestor=ancestor.parentElement){
      if(ancestor.tagName==='DETAILS')ancestor.open=true;
    }
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
