// Exercise the real UI handlers with a small DOM fixture and mocked API.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node{
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.attrs={};this.classList={add(){},toggle(){}};this.textContent='';this.value='';}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=children;}
  setAttribute(k,v){this.attrs[k]=v;}
  get lastElementChild(){return this.children.at(-1);}
  scrollIntoView(){} remove(){} focus(){}
  click(){if(!this.disabled)return this.onclick?.();}
}
function descendants(n){return n.children.flatMap(x=>[x,...descendants(x)]);}
async function scenario(auto,fail=false,category='book'){
  const ids=Object.fromEntries(['examples','shuffle','reply-language','ask-form','question','doc','web','conversation','ask','local-search','status'].map(id=>[id,new Node('div')]));
  ids.question.value='What is a derivative?';ids.web.checked=auto;ids.doc.value='active-calculus-pdf';
  const calls=[];let failed=fail;
  const api={tr:(en)=>en,localize(){},post:async(path,data)=>{
    calls.push([path,data]);
    if(path==='/api/ask')return {category,book_answer:category==='book'?'Textbook answer.':'',notice:'Not verified',language:'en-CA',evidence:[],results:[],web:null,web_token:category==='out_of_scope'?undefined:'signed'};
    if(failed){failed=false;throw Error('Search failed. Try again.');}
    return {web:{verified:true,text:'External answer.',citations:[]}};
  }};
  const document={getElementById:id=>ids[id],createElement:tag=>new Node(tag),createTextNode:text=>Object.assign(new Node('#text'),{textContent:text}),querySelectorAll:()=>[]};
  vm.runInNewContext(fs.readFileSync('static/app.js','utf8'),{window:{AccessEdu:api},document,localStorage:{getItem(){},setItem(){}},URL,Set,Map});
  await ids['ask-form'].onsubmit({preventDefault(){}});
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls[0][1].web,false);
  const all=descendants(ids.conversation),button=all.find(n=>n.tagName==='button'&&n.dataset.en==='Search the web');
  if(category==='out_of_scope'){assert.equal(button,undefined);assert.equal(calls.length,1);return;}
  assert.ok(button);
  if(!auto){assert.equal(calls.length,1);await button.click();}
  assert.equal(calls[1][0],'/api/web-search');assert.equal(calls[1][1].token,'signed');
  if(fail){assert.equal(button.disabled,false);assert.ok(descendants(ids.conversation).some(n=>n.textContent==='Search failed. Try again.'));await button.click();}
  assert.equal(button.hidden,true);
  assert.ok(descendants(ids.conversation).some(n=>n.textContent==='External answer.'));
  if(category==='book')assert.ok(descendants(ids.conversation).some(n=>n.textContent==='Textbook answer.'));
  else assert.equal(button.className,'primary');
}
(async()=>{await scenario(false,true);await scenario(true);await scenario(false,false,'related_outside');await scenario(false,false,'out_of_scope');console.log('Web UI interactions passed');})().catch(e=>{console.error(e);process.exitCode=1;});
