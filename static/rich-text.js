'use strict';
(() => {
  const htmlEscape=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const parser=new window.marked.Marked({gfm:true,breaks:false});
  const delimiters=[['\\(','\\)'],['\\[','\\]'],['$$','$$']];
  function nextMath(src){const positions=delimiters.map(([open])=>src.indexOf(open)).filter(i=>i>=0);return positions.length?Math.min(...positions):undefined;}
  function mathToken(src){
    for(const [open,close] of delimiters){
      if(!src.startsWith(open))continue;
      const end=src.indexOf(close,open.length);
      if(end>=open.length)return {type:'tex',raw:src.slice(0,end+close.length)};
    }
  }
  // Protect TeX from Markdown's backslash escapes and emphasis rules, including underscores.
  parser.use({extensions:[
    {name:'tex',level:'inline',start:nextMath,tokenizer:mathToken,renderer:t=>'<span>'+htmlEscape(t.raw)+'</span>'},
    {name:'texBlock',level:'block',start(src){return src.indexOf('\\[');},tokenizer(src){if(src.startsWith('\\[')||src.startsWith('$$')){const t=mathToken(src);if(t)return {...t,type:'texBlock'};}},renderer:t=>'<div>'+htmlEscape(t.raw)+'</div>'}
  ]});
  function safeURL(value,local=false){
    if(typeof value!=='string')return null;
    if(local && /^\/(?:book\/|reader\?)/.test(value)&&!/[\u0000-\u0020\\]/.test(value))return value;
    if(!/^https?:\/\//i.test(value))return null;
    try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}
  }
  let serial=0,mathQueue=Promise.resolve();
  function typeset(root){
    root.setAttribute('aria-live','off');
    mathQueue=mathQueue.catch(()=>{}).then(async()=>{
      if(!root.isConnected)return;
      const math=window.MathJax;
      if(!math?.startup?.promise)throw Error('Math renderer unavailable');
      await math.startup.promise;
      if(!root.isConnected)return;
      await math.typesetPromise([root]);
    }).catch(()=>{
      if(!root.isConnected)return;
      const notice=document.createElement('p');notice.className='muted';notice.setAttribute('role','status');
      notice.textContent=window.AccessEdu?.tr('Formula rendering failed; the original notation is shown.','Le rendu des formules a échoué ; la notation originale est affichée.')||'Formula rendering failed; the original notation is shown.';
      root.append(notice);
    });
    return mathQueue;
  }
  function render(source,{evidence=[],citations=[]}={}){
    const root=document.createElement('div');root.className='prose rich-text';root.sourceText=source;
    if(!window.DOMPurify?.sanitize){root.textContent=source;return root;}
    const references=new Map(),chars=Array.from(source);let at=0,input='';
    const nonce='ACCESSCITE'+(++serial)+'X'+(window.crypto?.randomUUID?.().replaceAll('-','')||Date.now());
    [...citations].sort((a,b)=>a.start-b.start).forEach((citation,i)=>{
      const url=safeURL(citation.url);
      if(!url||!Number.isInteger(citation.start)||!Number.isInteger(citation.end)||citation.start<at||citation.end>chars.length||citation.end<=citation.start)return;
      const key=nonce+'X'+i+'END';references.set(key,{url,label:'['+(i+1)+']',title:citation.title||url});
      input+=chars.slice(at,citation.start).join('')+key;at=citation.end;
    });
    input+=chars.slice(at).join('');
    const clean=window.DOMPurify.sanitize(parser.parse(input),{
      ALLOWED_TAGS:['p','br','h1','h2','h3','h4','h5','h6','ul','ol','li','strong','em','b','i','del','blockquote','pre','code','hr','table','thead','tbody','tr','th','td','a','span','div','sup','sub'],
      ALLOWED_ATTR:['href','title','colspan','rowspan','scope'],ALLOW_DATA_ATTR:false,ALLOW_ARIA_ATTR:false,
      RETURN_DOM_FRAGMENT:true
    });
    root.append(clean);
    // All post-sanitize additions use validated URLs and DOM text, never HTML strings.
    for(const link of root.querySelectorAll('a')){
      const url=safeURL(link.getAttribute('href'));
      if(url){link.href=url;link.target='_blank';link.rel='noopener noreferrer';}
      else link.removeAttribute('href');
    }
    const book=new Map(evidence.map(e=>[e.key,e]));
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),nodes=[];
    while(walker.nextNode())nodes.push(walker.currentNode);
    const pattern=new RegExp(nonce+'X\\d+END|\\[S\\d+\\]','g');
    for(const node of nodes){
      if(node.parentElement?.closest('a,pre,code')||mathToken(node.nodeValue)?.raw===node.nodeValue)continue;
      const text=node.nodeValue,fragment=document.createDocumentFragment();let pos=0,changed=false;
      for(const match of text.matchAll(pattern)){
        const key=match[0],item=book.get(key.slice(1,-1));
        const reference=references.get(key)||(item&&{url:safeURL(item.url,true),label:key,title:item.title+' · '+(item.chapter_title||'PDF '+item.page)});
        if(!reference?.url)continue;
        fragment.append(document.createTextNode(text.slice(pos,match.index)));
        const link=document.createElement('a');link.className='citation';link.href=reference.url;link.target='_blank';link.rel='noopener noreferrer';link.title=reference.title;link.textContent=reference.label;
        fragment.append(link);pos=match.index+key.length;changed=true;
      }
      if(changed){fragment.append(document.createTextNode(text.slice(pos)));node.replaceWith(fragment);}
    }
    return root;
  }
  window.AccessRichText={render,typeset,safeURL,whenReady:()=>mathQueue};
})();
