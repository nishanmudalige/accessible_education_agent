'use strict';
(() => {
  const blocks='p,div,section,article,aside,figure,figcaption,li,dt,dd,h1,h2,h3,h4,h5,h6,blockquote,pre,br,tr,th,td,summary';
  const texCommand=/\\(?:begin|end|text|lim|frac|sqrt|sum|int|to)(?![a-zA-Z])/;
  let engineQueue=Promise.resolve();

  function spokenFormula(words,locale){
    if(locale==='fr')return words.trim().replace(/(?:^|\s+)(?:virgule|point)$/i,'');
    return words.trim().replace(/(?:^|\s+)(?:comma|period|full stop)$/i,'')
      .replace(/(^|\s)[aA](?=\s|$)/g,'$1ay');
  }

  // Visible CHTML glyphs need not contribute any characters to Selection.toString().
  // Include the complete expression even when a boundary falls inside a glyph.
  function mathSelection(input){
    const range=input.cloneRange();
    if(range.collapsed)return {range,formulas:new Set()};
    const element=node=>node.nodeType===1?node:node.parentElement;
    const first=element(range.startContainer)?.closest('mjx-container');
    const last=element(range.endContainer)?.closest('mjx-container');
    if(first)range.setStartBefore(first);
    if(last)range.setEndAfter(last);
    const root=element(range.commonAncestorContainer);
    const formulas=new Set();
    if(!range.collapsed && root){
      for(const formula of root.querySelectorAll('mjx-container')){
        if(range.intersectsNode(formula))formulas.add(formula);
      }
    }
    return {range,formulas};
  }

  async function speechText(source,language){
    const locale=language?.startsWith('fr')?'fr':'en';
    const fallback=locale==='fr'?'formule':'formula';
    // The answer renderer has its own queue after MathJax's initial page typeset.
    try {
      await window.MathJax?.startup?.promise;
      await window.AccessRichText?.whenReady();
    } catch { /* Unrendered math uses the same spoken fallback. */ }
    const selected=source instanceof Range?mathSelection(source):null;
    const range=selected?.range;
    const parts=[];
    let hasMedia=false;
    function visit(node){
      if(range && !range.intersectsNode(node))return;
      if(node.nodeType===Node.TEXT_NODE){
        const start=node===range?.startContainer?range.startOffset:0;
        const end=node===range?.endContainer?range.endOffset:node.length;
        let text=node.data.slice(start,end);
        text=text.replace(/\\\([\s\S]*?\\\)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$/g,' '+fallback+' ');
        parts.push(texCommand.test(text)?' '+fallback+' ':text);
        return;
      }
      if(node.nodeType!==Node.ELEMENT_NODE)return;
      if(node.matches('script,style,[hidden],#latex-macros,mjx-assistive-mml,[aria-hidden="true"]:not(mjx-container)'))return;
      if(selected?selected.formulas.has(node):node.matches('mjx-container')){
        hasMedia=true;parts.push(node);
        return;
      }
      if(node.matches('.process-math') && !node.querySelector('mjx-container')){parts.push(' '+fallback+' ');return;}
      if(node.matches('img')){
        hasMedia=true;
        const alt=node.getAttribute('alt');
        if(alt===null)parts.push(locale==='fr'?' Image sans description ':' Image without description ');
        else if(alt.trim())parts.push((locale==='fr'?' Image : ':' Image: ')+alt.trim()+' ');
        return;
      }
      const block=node.matches(blocks);
      if(block)parts.push('\n\n');
      for(const child of node.childNodes)visit(child);
      if(block)parts.push('\n\n');
    }
    if(range){
      const ancestor=range.commonAncestorContainer;
      const element=ancestor.nodeType===1?ancestor:ancestor.parentElement;
      visit(element.closest('mjx-container,img')||ancestor);
    }else{
      for(const root of Array.isArray(source)?source:[source])visit(root);
    }
    if(parts.some(part=>typeof part!=='string')){
      // SRE has one active locale. Configure and verbalize a request as one operation.
      engineQueue=engineQueue.then(async()=>{
        let sre;
        try {
          await MathJax.loader.load('a11y/sre');
          sre=MathJax._.a11y.sre.Sre;
          await sre.sreReady();
          await sre.setupEngine({locale,domain:'mathspeak',style:'default'});
        } catch { sre=null; }
        for(const [index,part] of parts.entries()){
          if(typeof part==='string')continue;
          const math=part.querySelector('mjx-assistive-mml math');
          let words;
          try { if(math && sre && !math.querySelector('merror'))words=sre.toSpeech(new XMLSerializer().serializeToString(math)); } catch {}
          parts[index]=' '+(words && !texCommand.test(words)?spokenFormula(words,locale):fallback)+' ';
        }
      });
      await engineQueue;
    }
    const text=parts.join('').split(/\n\s*\n/).map(line=>line.replace(/\s+/g,' ').trim())
      .filter(Boolean).map(line=>texCommand.test(line)?fallback:line).join('\n\n');
    return {text,hasMedia};
  }
  window.AccessSpeechText=speechText;
  window.AccessSpeechText.mathSelection=mathSelection;
})();
