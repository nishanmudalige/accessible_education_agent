const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM,requestInterceptor,VirtualConsole}=require('jsdom');
const ROOT=process.cwd();
const read=p=>fs.readFileSync(p,'utf8');
async function basic(){
  const dom=new JSDOM('<main></main>',{url:'https://app.test',runScripts:'outside-only'}),w=dom.window;
  w.AccessEdu={tr:en=>en};w.MathJax={startup:{promise:Promise.resolve()},typesetPromise:async()=>{}};
  for(const file of ['static/vendor/marked/lib/marked.umd.js','static/vendor/dompurify/dist/purify.min.js','static/rich-text.js'])w.eval(read(file));
  const source=String.raw`### Answer

- **First** item
- Second item with \(f_x=\frac{a}{b}\)

\[
f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}
\]

See [S1] and [safe](https://example.org).

<img src=x onerror="window.pwned=1"><script>window.pwned=2</script><svg onload="window.pwned=3"><a href="javascript:alert(1)">x</a></svg>
<a href="javascript:alert(1)" onclick="window.pwned=4">bad</a>
<form id="conversation"><input name="DOMPurify"></form>
<math><mtext><table><mglyph><style><!--</style><img title="--><img src=x onerror=alert(1)>">
`;
  const root=w.AccessRichText.render(source,{evidence:[{key:'S1',url:'/book/test/chapter?hl=p1',title:'Book',chapter_title:'Chapter'}]});
  w.document.body.append(root);await w.AccessRichText.typeset(root);
  assert.equal(root.querySelector('h3').textContent,'Answer');assert.equal(root.querySelectorAll('li').length,2);
  assert.ok(root.textContent.includes(String.raw`\(f_x=\frac{a}{b}\)`));
  assert.ok(root.textContent.includes(String.raw`\lim_{h\to0}`));
  assert.ok(root.querySelector('a.citation').getAttribute('href').startsWith('/book/test/'));
  assert.equal(root.querySelectorAll('script,svg,math,img,form,input,style,[onclick],[onerror],[onload]').length,0);
  assert.equal(root.querySelectorAll('a[href^="javascript:"]').length,0);
  assert.equal(w.pwned,undefined);assert.equal(root.getAttribute('aria-live'),'off');
  const web='### Web\n\n😀 **Claim** CITATION.';const start=Array.from(web.slice(0,web.indexOf('CITATION'))).length;
  const result=w.AccessRichText.render(web,{citations:[{start,end:start+8,url:'https://example.org/source',title:'Source'}]});
  assert.equal(result.querySelector('h3').textContent,'Web');assert.ok(result.querySelector('strong'));
  assert.equal(result.querySelector('a.citation').textContent,'[1]');assert.equal(result.querySelector('a.citation').href,'https://example.org/source');
  const unsafe=w.AccessRichText.render('[bad](data:text/html,evil) [ok](https://example.org)');
  assert.equal([...unsafe.querySelectorAll('a[href]')].length,1);
  assert.equal(w.AccessRichText.safeURL('javascript:alert(1)'),null);
  dom.window.close();
}
async function realMath(){
  const resources={interceptors:[requestInterceptor(request=>{
    const parsed=new URL(request.url);
    if(parsed.origin!=='https://app.test'||!parsed.pathname.startsWith('/static/'))throw Error('Unexpected resource '+request.url);
    const target=path.resolve(ROOT,'.'+parsed.pathname);
    if(!target.startsWith(path.join(ROOT,'static')+path.sep))throw Error('Unsafe path');
    return new Response(fs.readFileSync(target),{headers:{'Content-Type':'application/javascript'}});
  })]};
  const console=new VirtualConsole();const errors=[];console.on('jsdomError',e=>errors.push(e.message));
  const html='<script src="/static/mathjax-config.js"></script><script src="/static/vendor/mathjax/es5/tex-chtml-full.js"></script><main id="math">\\[f\'(a)=\\lim_{h\\to0}\\frac{f(a+h)-f(a)}{h}\\] \\(\\href{javascript:alert(1)}{x}\\)</main>';
  const dom=new JSDOM(html,{url:'https://app.test',runScripts:'dangerously',resources,pretendToBeVisual:true,virtualConsole:console});
  await new Promise((resolve,reject)=>{if(dom.window.document.readyState==='complete')resolve();else dom.window.addEventListener('load',resolve,{once:true});setTimeout(()=>reject(Error('MathJax startup timed out')),10000).unref();});
  await dom.window.MathJax.startup.promise;
  assert.ok(dom.window.document.querySelector('mjx-container[jax="CHTML"]'),'Real MathJax typesetting');
  assert.ok(dom.window.document.querySelector('mjx-assistive-mml math'),'Assistive MathML is present');
  assert.equal(dom.window.document.querySelectorAll('a[href^="javascript:"]').length,0);
  assert.equal(dom.window.MathJax.config.options.safeOptions.allow.URLs,'none');
  assert.equal(errors.length,0,errors.join('\n'));
  dom.window.close();
}
(async()=>{await basic();await realMath();console.log('Markdown, TeX, citations, XSS and assistive MathML passed');})().catch(error=>{console.error(error);process.exitCode=1;});
