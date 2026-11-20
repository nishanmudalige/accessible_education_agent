const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
async function run(found,fr=false){
  const details={tagName:'DETAILS',open:false,parentElement:null};
  const target={parentElement:details,attrs:{},classList:{add(value){target.highlight=value;}},setAttribute(k,v){this.attrs[k]=v;},closest(){return true;},scrollIntoView(){this.scrolled=true;},focus(){this.focused=true;}};
  const status={dataset:{sourceLang:fr?'fr-CA':'en-CA'},textContent:''};
  vm.runInNewContext(fs.readFileSync('static/book.js','utf8'),{
    document:{readyState:'complete',getElementById:id=>id==='citation-status'?status:(found?target:null)},
    location:{search:'?hl=evidence'},URLSearchParams,requestAnimationFrame:fn=>fn(),
    window:{MathJax:{startup:{promise:Promise.resolve()}}}
  });
  await Promise.resolve();await Promise.resolve();
  if(found){assert.ok(details.open&&target.focused&&target.scrolled);assert.equal(target.attrs['tabindex'],'-1');assert.equal(target.attrs['aria-describedby'],'citation-status');assert.equal(target.highlight,'cited-passage');}
  else assert.ok(status.textContent.includes(fr?'introuvable':'could not be found'));
}
(async()=>{await run(true);await run(false);await run(false,true);console.log('HTML citation focus and disclosure tests passed');})().catch(error=>{console.error(error);process.exitCode=1;});
