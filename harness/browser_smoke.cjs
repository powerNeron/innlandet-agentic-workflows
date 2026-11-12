
const fs=require('fs');
async function chatUnitTests(sourcePath,apiResponse=null){
 const assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path');
 const root=path.resolve(__dirname,'..');
 const file=sourcePath?path.resolve(sourcePath):path.join(root,'hamar_agent/web_assets/app.js');
 assert(file.startsWith(root+path.sep),'UI source must remain in the project');
 const fullSource=fs.readFileSync(file,'utf8');
 const htmlPath=path.join(path.dirname(file),'index.html');
 const shellMarkup=fs.readFileSync(fs.existsSync(htmlPath)?htmlPath:path.join(root,'hamar_agent/web_assets/index.html'),'utf8');
 const source=fullSource.split('// General AI chat never shares municipal answers, sources or conversation state.')[1];
 assert(source,'Chat source marker missing');
 const checks=[];
 function environment(){
  class Element{
   constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.attributes={};this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.checked=false;this.textContent='';this.className='';this.listeners={};this.scrollHeight=400;this.scrollTop=0;this.classList={add:name=>{this.className+=' '+name}};}
   appendChild(child){this.children.push(child);child.parent=this;return child}
   prepend(child){this.children.unshift(child);child.parent=this}
   replaceChildren(...children){this.children=[];children.forEach(c=>this.appendChild(c))}
   addEventListener(name,fn){const old=this.listeners[name];this.listeners[name]=old?(event=>{old(event);return fn(event)}):fn}
   dispatchEvent(event){return this.listeners[event.type]?.(event)}
   setAttribute(name,value){this.attributes[name]=value}
   querySelector(selector){return this.children.find(c=>selector==='.'+c.className)||null}
   remove(){if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this)}
   cloneNode(){return new Element('span')}
   focus(){for(let e=this;e;e=e.parent)if(e.hidden||e.disabled)return;this.focused=true}
   requestSubmit(){this.listeners.submit?.({preventDefault(){}})}
  }
  const ids=new Map(),get=id=>{if(!ids.has(id))ids.set(id,new Element(id.includes('provider')?'select':'div'));return ids.get(id)};
  get('chat-mode').hidden=false;get('municipal-mode').hidden=true;get('ai-result').hidden=true;get('chat-message').tagName='TEXTAREA';get('chat-retry').hidden=true;
  const resetTag=shellMarkup.match(/<button\b[^>]*\bid="reset-conversation"[^>]*>/u)?.[0]||'';
  get('reset-conversation').hidden=/\shidden(?:[\s=>])/u.test(resetTag);
  if(shellMarkup.indexOf('id="reset-conversation"')>shellMarkup.indexOf('id="ai-result"'))get('reset-conversation').parent=get('ai-result');
  const sendLabel=new Element('span');sendLabel.className='chat-send-label';get('chat-send').appendChild(sendLabel);
  const skip=new Element('a'),robot=new Element('span');
  let revision=0,messages=[],posts=0,resets=0,provider='openai',holdState=null,holdReset=null,fault=null;
  const state=()=>({revision,messages:structuredClone(messages),turns:messages.length/2,busy:false});
  const data={choices:[{provider:'openai',model:'synthetic-cloud-fixture',available:true,label:'Mock OpenAI'},
                       {provider:'ollama',model:'synthetic-local-fixture',available:true,label:'Mock Ollama'}],web_search_allowed:false};
  const api=async(url,options={})=>{
   if(url==='/api/chat/options')return structuredClone(data);
   if(url==='/api/chat/state'){const snapshot=state();if(holdState){const hold=holdState;holdState=null;await hold}return snapshot}
   if(url==='/api/chat/reset'){resets++;messages=[];revision++;const snapshot={reset:true,revision,busy:false};if(holdReset){const hold=holdReset;holdReset=null;await hold}return snapshot}
   if(url==='/api/chat'){
    posts++;const request=JSON.parse(options.body);
    if(fault){const code=fault;fault=null;const error=new Error('AI kan ikke kontaktes. Prøv igjen senere.');error.code=code;throw error}
    assert.equal(request.revision,revision,'Obsolete request submitted');
    const reply={role:'assistant',text:'Syntetisk svar.',web_search_used:false,citations:[],ai_generated:true,municipal_verified:false};
    messages.push({role:'user',text:request.message},reply);revision++;
    return {reply,revision,turns:messages.length/2};
   }
   throw Error('Unexpected route '+url);
  };
  const documentListeners={};
  const context=vm.createContext({document:{getElementById:get,createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),querySelector:selector=>selector==='.skip'?skip:robot,
   addEventListener:(name,callback)=>{documentListeners[name]=callback}},
   $:get,token:'synthetic-session-token',item:(parent,tag,text)=>{const e=new Element(tag);e.textContent=text;parent.appendChild(e);return e},
   api,visibleRequestError:(error,fallback)=>error.message||fallback,AbortController,Event,URL,console,refreshMunicipalOptions:async()=>{}});
  vm.runInContext(source,context);
  const evaluate=script=>vm.runInContext(script,context);
  const ready=async(provider='openai')=>{await evaluate('loadChat()');if(provider){get('chat-provider').value=provider==='openai'?'openai|synthetic-cloud-fixture':'ollama|synthetic-local-fixture';await get('chat-provider').listeners.change()}evaluate('updateChatControls()')};
  const delayState=()=>{let release;holdState=new Promise(r=>release=r);return release};
  const delayReset=()=>{let release;holdReset=new Promise(r=>release=r);return release};
  return {get,evaluate,ready,delayState,delayReset,state,data,documentListeners,counts:()=>({posts,resets}),
          setApi:fn=>{context.api=fn},getApi:()=>context.api,
          failNext:code=>{fault=code},
          seed:()=>{messages=[{role:'user',text:'Et syntetisk spørsmål.'},{role:'assistant',text:'Et tidligere syntetisk svar.'}];revision=1},
          tick:()=>new Promise(resolve=>setImmediate(resolve))};
 }
 function municipalEnvironment(){
  const e=environment(),original=e.getApi(),calls=[];
  const data={choices:[{provider:'ollama',model:'synthetic-local-fixture',available:true,processing:'local'},
   {provider:'openai',model:'gpt-4.1-mini',available:true,processing:'external',availability_status:'configured'}]};
  let hold=null,resetFailure=false;
  e.setApi(async(route,options={})=>{
   if(route==='/api/providers'){calls.push(route);const snapshot=structuredClone(data);if(hold){const wait=hold;hold=null;await wait}return snapshot}
   if(route==='/api/conversation/reset'){calls.push(route);if(resetFailure){resetFailure=false;throw Error('Synthetic reset failure')}return {reset:true}}
   if(route==='/api/answer'){calls.push(route);throw Error('UI metadata/selection may not generate')}
   return original(route,options);
  });
  e.evaluate('let providerChoices=[],chosenProvider=null,chosenModel=null,municipalSelectionKey="",municipalResetRequired=false,providerBusy=false,portalReady=true,aiBusy=false,answerGeneration=0,answerAbort=null,lastAnsweredQuery=null,conversationActive=false;');
  const component=fullSource.slice(fullSource.indexOf('function providerDescription('),fullSource.indexOf('// Category rendering keeps the original'));
  assert(component.includes('async function refreshMunicipalOptions()'));
  e.evaluate(component);e.get('ai-query').value='vann';
  return {...e,data,calls,failReset:()=>{resetFailure=true},delay:()=>{let release;hold=new Promise(r=>release=r);return release}};
 }
 if(apiResponse!==null){
  assert.equal(apiResponse.answer?.answer_status,'insufficient_evidence');
  const e=environment();e.evaluate('let officialMenuUrl="https://www.hamar.kommune.no/meny/"');
  e.evaluate(fullSource.slice(fullSource.indexOf('function sourceLink('),fullSource.indexOf('async function searchPortal(')));
  e.evaluate(fullSource.slice(fullSource.indexOf('function renderAnswer('),fullSource.indexOf('function providerDescription(')));
  const initialHidden=e.get('ai-result').hidden;
  const original=JSON.stringify(apiResponse);e.evaluate('const actualApiPayload='+original+';renderAnswer(actualApiPayload.answer)');
  const all=n=>[n,...n.children.flatMap(all)],nodes=[...all(e.get('answer-content')),...all(e.get('answer-state'))];
  console.log(JSON.stringify({method:'Actual in-process API payload rendered by actual JS in synthetic DOM; not browser pixels',
   text:nodes.map(n=>n.textContent).join('\n'),links:nodes.filter(n=>n.tagName==='A').map(n=>n.href),
   has_claim:nodes.some(n=>n.className==='answer-text'),payload_unchanged:e.evaluate('JSON.stringify(actualApiPayload)')===original,
   generation_requests:e.counts().posts,initial_hidden:initialHidden,panel_hidden:e.get('ai-result').hidden}));return;
 }
 {
  const e=environment();await e.ready();assert.equal(e.counts().posts,0);
  assert.equal(e.get('chat-provider').value,'openai|synthetic-cloud-fixture');
  await e.evaluate('selectAishaMode(true)');assert.equal(e.get('municipal-mode').hidden,true);assert.equal(e.get('chat-mode').hidden,false);
  e.evaluate('selectAishaMode(false)');assert.equal(e.get('chat-mode').hidden,true);
  assert.equal(e.get('chat-web-search').disabled,true);assert.equal(e.get('chat-web-search').checked,false);
  checks.push('mode switching and default-off search; no automatic model calls');
 }
 {
  const e=environment();await e.ready();e.seed();await e.evaluate('syncChatState()');
  const release=e.delayState();const stale=e.evaluate('loadChat()');await e.tick();await e.evaluate('resetChat()');
  const expected=e.state().revision;release();await stale;
  assert.equal(e.evaluate('chatRevision'),expected,'Delayed state rolled revision backward');
  assert.equal(e.get('chat-log').children.filter(x=>x.tagName==='ARTICLE').length,0,'Delayed state restored old history');
  checks.push('CHAT-01 delayed state cannot undo reset');
 }
 {
  const e=environment();await e.ready();const release=e.delayReset();
  const first=e.evaluate('resetChat()');await e.tick();const second=e.evaluate('resetChat()');await e.tick();
  assert.equal(e.counts().resets,1,'Reset POSTs overlap');release();await Promise.all([first,second]);
  assert.equal(e.counts().resets,2);assert.equal(e.evaluate('chatRevision'),e.state().revision);
  assert.equal(e.evaluate('chatResetting'),false);checks.push('CHAT-01 serialized reset ownership');
 }
 {
  const e=environment();await e.ready();
  e.evaluate('chatLastRequest={message:"Syntetisk spørsmål.",provider:"openai",model:"synthetic-cloud-fixture",web_search:false,revision:0}');
  const release=e.delayState();const retry=e.evaluate('sendChat(true)');await e.tick();
  e.get('chat-provider').value='ollama|synthetic-local-fixture';await e.evaluate('resetChat()');release();await retry;
  assert.equal(e.counts().posts,0,'Obsolete retry made a model request');assert.equal(e.evaluate('chatChecking'),false);
  checks.push('CHAT-01 reset/provider change cancels obsolete retry verification');
 }
 {
  const e=environment();await e.ready();e.get('chat-message').value='Forklar en algoritme.';await e.evaluate('sendChat()');
  e.get('chat-message').value='Forklar det enklere.';await e.evaluate('sendChat()');
  assert.equal(e.counts().posts,2);assert.equal(e.state().messages.length,4);
  assert.equal(e.evaluate('chatRevision'),2);assert.equal(e.get('chat-log').attributes['aria-busy'],'false');
  const unsafeCitationUrls=['javascript:alert(1)','https://localhost./','https://host.local./','https://127.1/',
   'https://0x7f.0.0.1/','https://0x7f.0x0.0x0.0x1/','https://127。0。0。1/','https://127。0.0.1/','https://localhost｡/','https://１２７.０.０.１/'];
  const annotationFixture={role:'assistant',text:'<script>syntheticAttack=true</script>',web_search_used:true,
   citations:[...unsafeCitationUrls.map(url=>({url,title:'unsafe'})),{url:'https://example.org/test',title:'Syntetisk kilde'}]};
  e.evaluate('renderChatMessage('+JSON.stringify(annotationFixture)+')');
  assert.equal(e.evaluate('typeof syntheticAttack'),'undefined');
  const row=e.get('chat-log').children.at(-1),bubble=row.children.at(-1),list=bubble.children.find(x=>x.tagName==='UL');
  assert.equal(list.children.length,1);assert.equal(list.children[0].children[0].href,'https://example.org/test');
  checks.push('followup bubbles, loading reset and inert text/safe source links');
 }
 {
  const e=environment();await e.ready();
  e.evaluate('renderChatMessage('+JSON.stringify({role:'assistant',text:'Velg Kommunal informasjon.',ai_generated:false,response_origin:'application_guidance',web_search_used:false,citations:[]})+')');
  const bubble=e.get('chat-log').children.at(-1).children.at(-1);
  const label=bubble.children.find(n=>n.className==='chat-answer-label');
  assert.equal(label.textContent,'Veiledning fra Aisha · ikke kildekontrollert');
  assert(!label.textContent.includes('AI-generert'));assert.equal(e.counts().posts,0);
  checks.push('zero-call application guidance is not labelled as model-generated');
 }
 {
  const e=environment();await e.ready(null);
  assert.equal(e.get('chat-provider').value,'ollama|synthetic-local-fixture');assert.equal(e.counts().posts,0);
  await e.evaluate('loadChat()');await e.evaluate('selectAishaMode(false)');await e.evaluate('selectAishaMode(true)');
  assert.equal(e.counts().posts,0);
  const text=e.get('chat-provider').children.map(n=>n.textContent).join(' ');
  assert(text.includes('Lokal AI (Ollama)'));assert(!text.includes('synthetic-cloud-fixture')&&!text.includes('synthetic-local-fixture'));
  const welcome=e.get('chat-log').children.find(n=>n.className==='chat-empty');
  const prompts=welcome.children.find(n=>n.className==='chat-prompts');prompts.children[0].listeners.click();
  assert(e.get('chat-message').value.length>0);assert.equal(e.counts().posts,0);
  checks.push('available local default, friendly names and suggestions never generate');
 }
 {
  const e=environment();e.data.choices=e.data.choices.filter(c=>c.provider==='openai');await e.ready(null);
  assert.equal(e.get('chat-provider').value,'');assert.equal(e.counts().posts,0);
  e.get('chat-message').value='Syntetisk spørsmål.';e.evaluate('updateChatControls()');assert(e.get('chat-send').disabled);
  checks.push('cloud-only availability never becomes automatic default');
 }
 {
  const e=environment();e.data.choices.find(c=>c.provider==='openai').available=false;await e.ready(null);
  assert.equal(e.get('chat-provider').value,'ollama|synthetic-local-fixture');
  const cloud=e.get('chat-provider').children.find(n=>n.value.startsWith('openai|'));
  assert(cloud.disabled);assert(cloud.textContent.includes('må klargjøres'));
  assert.equal(e.get('chat-openai-help').hidden,false);assert(!e.get('chat-status').textContent.includes('feil'));
  e.get('chat-message').value='Syntetisk melding.';await e.evaluate('sendChat()');assert.equal(e.counts().posts,1);
  checks.push('paused OpenAI is informational and does not block local chat');
 }
 {
  const e=environment();await e.ready(null);e.get('chat-message').value='En lokal melding.';await e.evaluate('sendChat()');
  e.data.choices.find(c=>c.provider==='ollama').model='synthetic-new-local-fixture';await e.evaluate('loadChat()');
  assert.equal(e.get('chat-provider').value,'');assert.equal(e.counts().posts,1);
  e.get('chat-message').value='Fortsett.';e.evaluate('updateChatControls()');assert(e.get('chat-send').disabled);
  e.get('chat-provider').value='ollama|synthetic-new-local-fixture';await e.get('chat-provider').listeners.change();
  assert.equal(e.state().messages.length,0);assert.equal(e.counts().posts,1);
  checks.push('disappearing local choice requires explicit selection and completed reset');
 }
 {
  const e=environment();await e.ready();await e.evaluate('loadChat()');
  assert.equal(e.get('chat-provider').value,'openai|synthetic-cloud-fixture');assert.equal(e.counts().posts,0);
  assert.equal(typeof e.documentListeners.DOMContentLoaded,'function');
  checks.push('explicit cloud selection survives refresh without inference');
 }
 {
  for(const provider of ['ollama','openai']){
   const e=environment();await e.ready(provider);
   const welcome=e.get('chat-log').children.find(n=>n.className==='chat-empty');
   assert(welcome.children.some(n=>n.className==='robot-avatar chat-welcome-avatar'));
   assert(welcome.children.some(n=>n.tagName==='H2'&&n.textContent==='Hva kan jeg hjelpe deg med?'));
   const prompts=welcome.children.find(n=>n.className==='chat-prompts').children;
   assert.deepEqual(prompts.map(b=>b.children.find(n=>n.tagName==='SPAN').textContent),['Forklar et tema','Hjelp meg å skrive','Hjelp med læring','Still et spørsmål']);
   for(const b of prompts){assert.equal(b.type,'button');assert(b.children.some(n=>n.tagName==='SVG'));b.listeners.click();assert(e.get('chat-message').value.length>0);assert(e.get('chat-message').focused);assert.equal(e.counts().posts,0)}
   await e.evaluate('sendChat()');assert.equal(e.counts().posts,1);
   const rows=e.get('chat-log').children.filter(n=>n.tagName==='ARTICLE');
   assert(rows.some(n=>n.className==='chat-row user'));assert(rows.some(n=>n.className==='chat-row assistant'));
   assert(rows.find(n=>n.className==='chat-row assistant').children.length>=2);
  }
  checks.push('four icon suggestions prefill only; identical local/cloud bubbles and robot avatar');
 }
 {
  const e=environment();e.data.choices.find(c=>c.provider==='openai').model='gpt-4.1-mini';await e.ready(null);
  const option=()=>e.get('chat-provider').children.find(n=>n.value==='openai|gpt-4.1-mini');
  assert.equal(option().textContent,'OpenAI GPT-4.1 mini · konfigurert');assert.equal(e.counts().posts,0);
  assert.equal(e.get('chat-provider').value,'ollama|synthetic-local-fixture');
  e.get('chat-provider').value='openai|gpt-4.1-mini';await e.get('chat-provider').listeners.change();
  e.failNext('provider_timeout');e.get('chat-message').value='Syntetisk test.';await e.evaluate('sendChat()');
  assert.equal(option().textContent,'OpenAI GPT-4.1 mini · utilgjengelig etter feil');assert.equal(e.counts().posts,1);
  await e.evaluate('loadChat()');assert(option().textContent.includes('etter feil'));assert.equal(e.counts().posts,1);
  await e.evaluate('sendChat(true)');assert.equal(e.counts().posts,2);assert(option().textContent.includes('konfigurert'));
  e.data.choices.find(c=>c.provider==='openai').available=false;e.data.choices.find(c=>c.provider==='openai').availability_status='paused';await e.ready(null);
  assert(option().disabled);assert.equal(option().textContent,'OpenAI GPT-4.1 mini · deaktivert av eier');
  assert.equal(e.get('chat-provider').value,'');assert.equal(e.counts().posts,2);
  checks.push('GPT-4.1 mini configured, owner-disabled and observed-error states; manual retry only');
 }
 {
  const e=environment();const source=fullSource.split('// Category rendering keeps the original source-search mapping and click behavior.')[1]?.split('async function loadPortal()')[0];
  assert(source,'Category rendering seam missing');
  e.evaluate('let selectedCategory=null,selectedService=null,searches=0; function searchPortal(){searches++}');e.evaluate(source);
  const data={synthetic:false,categories:['oppvekst','bolig','helse','teknisk','miljo','kultur','politikk'].map(id=>({id}))};
  e.evaluate('renderCategories('+JSON.stringify(data)+')');const cards=e.get('categories').children;
  assert.deepEqual(cards.map(c=>c.children[1].textContent),['Skole','Bolig','Helse','Vann','Miljø','Transport','Kultur','Politikk']);
  const queries=['skole','byggesak','helse','vann','miljø','parkering','kultur','planer'];
  for(let i=0;i<cards.length;i++){
   const c=cards[i];assert.equal(c.type,'button');assert(!c.disabled);assert.equal(c.children.length,2);
   assert.equal(c.children[0].className,'category-icon');assert.equal(c.children[0].children[0].tagName,'SVG');
   assert.equal(c.children[1].className,'category-label');assert(c.attributes['aria-label'].startsWith(c.children[1].textContent));
   c.listeners.click();assert.equal(e.get('query').value,queries[i]);assert.equal(e.evaluate('selectedService'),c.dataset.service);assert.equal(e.evaluate('selectedCategory'),c.dataset.category);
  }
  assert.equal(e.evaluate('searches'),8);data.categories=data.categories.filter(c=>c.id!=='politikk');e.evaluate('renderCategories('+JSON.stringify(data)+')');assert(e.get('categories').children[7].disabled);
  checks.push('all eight category buttons retain source-search mapping, icons, labels and approval-category gate');
 }
 {
  const e=environment();await e.ready(null);const buttons=e.get('chat-model-choices').children;
  assert.equal(buttons.length,2);assert(buttons.every(b=>b.type==='button'));
  assert.equal(buttons[1].attributes['aria-pressed'],'true');const count=e.counts();await buttons[1].listeners.click();assert.deepEqual(e.counts(),count);
  await buttons[0].listeners.click();assert.equal(e.get('chat-provider').value,'openai|synthetic-cloud-fixture');assert.equal(e.counts().posts,0);
  e.data.choices[0].available=false;await e.evaluate('loadChat()');assert.equal(e.get('chat-provider').value,'');
  const cloud=e.get('chat-model-choices').children[0];assert(cloud.disabled);await cloud.listeners.click();assert.equal(e.counts().posts,0);
  assert.equal(e.get('chat-provider').value,'');checks.push('rounded chat choices are explicit non-submit buttons; missing cloud never falls back');
 }
 {
  const e=municipalEnvironment();e.evaluate('populateProviders('+JSON.stringify(e.data)+', "")');
  assert.equal(e.get('provider-model').value,'ollama|synthetic-local-fixture');assert.equal(e.calls.length,0);
  const buttons=e.get('municipal-model-choices').children;assert(buttons.every(b=>b.type==='button'));
  assert(buttons[1].textContent.includes('OpenAI GPT-4.1 mini'));assert.equal(e.get('refresh-providers').hidden,true);
  await buttons[0].listeners.click();assert.equal(e.calls.length,0);
  await buttons[1].listeners.click();assert.equal(e.get('provider-model').value,'openai|gpt-4.1-mini');assert.deepEqual(e.calls,['/api/conversation/reset']);
  assert(e.get('refresh-providers').hidden,'UI-M02 healthy manual selection must hide recovery');
  await e.evaluate('selectAishaMode(true)');assert.equal(e.counts().posts,0);
  await e.evaluate('selectAishaMode(false)');assert.equal(e.get('provider-model').value,'openai|gpt-4.1-mini');
  assert.deepEqual(e.calls,['/api/conversation/reset','/api/providers']);assert.equal(e.get('chat-provider').value,'ollama|synthetic-local-fixture');
  const only=municipalEnvironment();only.data.choices=only.data.choices.filter(c=>c.provider==='openai');only.evaluate('populateProviders('+JSON.stringify(only.data)+', "")');
  assert.equal(only.evaluate('chosenProvider'),null);assert(only.get('ai-button').disabled);
  await only.get('municipal-model-choices').children[0].listeners.click();assert.equal(only.evaluate('chosenProvider'),'openai');assert(!only.get('ai-button').disabled);
  checks.push('municipal rounded choices retain local default and manual cloud-only selection; navigation makes no generation or reset');
 }
 {
  const e=municipalEnvironment();e.evaluate('populateProviders('+JSON.stringify(e.data)+', "")');
  await e.get('municipal-model-choices').children[1].listeners.click();
  e.evaluate('conversationActive=true;lastAnsweredQuery="vann"');e.get('answer-content').textContent='Et tidligere kildekontrollert svar.';
  const release=e.delay(),pending=e.evaluate('refreshMunicipalOptions()');await e.tick();
  assert(e.get('municipal-model-choices').children.every(b=>b.disabled));const count=e.calls.length;
  await e.get('municipal-model-choices').children[0].listeners.click();await e.get('reset-conversation').listeners.click();await e.evaluate('askAi()');
  assert.equal(e.calls.length,count);release();await pending;
  assert.equal(e.get('provider-model').value,'openai|gpt-4.1-mini');assert.equal(e.get('ai-query').value,'vann');
  assert.equal(e.get('answer-content').textContent,'Et tidligere kildekontrollert svar.');assert(e.evaluate('conversationActive'));assert.equal(e.evaluate('lastAnsweredQuery'),'vann');
  e.data.choices[1].available=false;e.data.choices[1].availability_status='paused';e.data.choices[1].reason='OpenAI er deaktivert av eier.';
  await e.evaluate('refreshMunicipalOptions()');assert.equal(e.evaluate('chosenProvider'),null);assert(e.get('ai-button').disabled);
  assert(e.get('municipal-model-choices').children[1].disabled);assert(!e.get('provider-openai-help').hidden);
  await e.get('municipal-model-choices').children[1].listeners.click();assert.equal(e.calls.filter(c=>c==='/api/conversation/reset').length,1);
  await e.get('municipal-model-choices').children[0].listeners.click();assert.equal(e.evaluate('chosenProvider'),'ollama');assert.equal(e.calls.filter(c=>c==='/api/conversation/reset').length,2);
  assert(!e.calls.includes('/api/answer'));checks.push('delayed municipal metadata preserves query/answer/context and blocks competing mutations; disabled cloud requires manual switch');
 }
 {
  const chat=environment();await chat.ready(null);chat.data.choices.find(c=>c.provider==='ollama').available=false;
  await chat.evaluate('loadChat()');assert.equal(chat.get('chat-provider').value,'');assert(!chat.get('chat-refresh').hidden);assert(chat.get('chat-send').disabled);
  chat.data.choices.find(c=>c.provider==='ollama').available=true;await chat.get('chat-refresh').listeners.click();
  assert.equal(chat.get('chat-provider').value,'ollama|synthetic-local-fixture');assert.deepEqual(chat.counts(),{posts:0,resets:0});
  const e=municipalEnvironment();e.evaluate('populateProviders('+JSON.stringify(e.data)+', "");conversationActive=true');e.get('answer-content').textContent='Tidligere kontrollert svar.';
  e.data.choices[0].available=false;await e.evaluate('refreshMunicipalOptions()');assert.equal(e.evaluate('chosenProvider'),null);
  assert(!e.get('refresh-providers').hidden);assert(e.get('ai-button').disabled);
  e.data.choices[0].available=true;await e.get('refresh-providers').listeners.click();assert.equal(e.evaluate('chosenProvider'),'ollama');
  assert(e.evaluate('conversationActive'));assert.equal(e.get('answer-content').textContent,'Tidligere kontrollert svar.');
  assert(e.calls.every(c=>c==='/api/providers'));checks.push('UI-M01 unavailable sticky local choice keeps recovery visible and restores same provider without reset or generation');
 }
 {
  const e=municipalEnvironment();e.evaluate('populateProviders('+JSON.stringify(e.data)+', "");conversationActive=true');e.failReset();
  await e.get('municipal-model-choices').children[1].listeners.click();assert(e.evaluate('municipalResetRequired'));assert.equal(e.evaluate('chosenProvider'),null);
  await e.evaluate('refreshMunicipalOptions()');await e.evaluate('askAi()');assert.equal(e.evaluate('chosenProvider'),null);
  assert.equal(e.calls.filter(c=>c==='/api/conversation/reset').length,1);assert(!e.get('refresh-providers').hidden);
  await e.get('refresh-providers').listeners.click();assert(!e.evaluate('municipalResetRequired'));assert.equal(e.evaluate('chosenProvider'),'openai');
  assert.equal(e.calls.filter(c=>c==='/api/conversation/reset').length,2);assert(!e.calls.includes('/api/answer'));
  checks.push('metadata cannot bypass failed-reset ownership; explicit recovery confirms reset before enabling Ask');
 }
 {
  const e=environment();e.evaluate('let officialMenuUrl="https://www.hamar.kommune.no/meny/"');
  e.evaluate(fullSource.slice(fullSource.indexOf('function sourceLink('),fullSource.indexOf('async function searchPortal(')));
  e.evaluate(fullSource.slice(fullSource.indexOf('function renderAnswer('),fullSource.indexOf('function providerDescription(')));
  const all=n=>[n,...n.children.flatMap(all)],text=n=>all(n).map(c=>c.textContent).join('\n');
  const caution='Opplysningene kan ha endret seg. Se kommunens nettside for siste informasjon.';
  const source={title:'Fictional service fixture',synthetic:false,url:'https://www.hamar.kommune.no/fictional-ui-test/?topic=vann',
   excerpt:'Ordrett syntetisk eksempel: vann koster 250 kroner.',paragraph_id:'fictional:p1',approval_status:'historical_expired',
   historical_warning:'Historisk kildemateriale. Godkjenningen er utløpt. Ikke nygodkjent.',reviewed_on:'2001-01-02',approval_expires:'2001-02-03',
   retrieved_at:'2000-12-01T10:00:00Z',indexed_at:'2004-03-04T10:00:00Z'};
  const raw=JSON.stringify(source),forbidden=/Historisk kildemateriale|Godkjenningen er utløpt|Ikke nygodkjent|Gjennomgått:|Registrert godkjenningsfrist|Indeksert:|UTLØPT GODKJENNING|INNEN REGISTRERT PERIODE|STATUS IKKE OPPGITT|2001|2004/iu;
  const check=(node,expectedCaution=true)=>{
   const nodes=all(node),content=text(node);assert(!forbidden.test(content));assert.equal(nodes.filter(n=>n.textContent===caution).length,expectedCaution?1:0);
   assert(nodes.some(n=>n.tagName==='A'&&n.href===source.url&&n.target==='_blank'&&n.rel==='noopener noreferrer'));
   return nodes;
  };
  e.evaluate('const publicSourceFixture='+raw+';renderSearch({results:[publicSourceFixture]})');
  let nodes=check(e.get('search-results'));assert(nodes.some(n=>n.textContent==='Kilde'));assert(nodes.some(n=>n.textContent===source.excerpt));assert(!text(e.get('search-results')).includes('Hentet fra kommunens nettside:'));assert(!text(e.get('search-results')).includes('2000'));
  const unknown={...source,approval_status:undefined,historical_warning:null,retrieved_at:undefined};
  e.evaluate('renderSearch('+JSON.stringify({results:[unknown]})+')');nodes=check(e.get('search-results'),false);assert(!text(e.get('search-results')).includes('ikke oppgitt'));
  const current={...source,approval_status:'within_recorded_period',historical_warning:null};e.evaluate('renderSearch('+JSON.stringify({results:[current]})+')');check(e.get('search-results'),false);
  e.evaluate('renderSearch('+JSON.stringify({results:[{...source,synthetic:true,url:null}]})+')');assert(text(e.get('search-results')).includes('SYNTETISK EKSEMPEL'));assert(!all(e.get('search-results')).some(n=>n.tagName==='A'));
  const answer={answer_status:'evidence_checked',message:'Kildebasert svar; les kilden.',citations:[source],result:{
   claims:[{text:source.excerpt,evidence_quote:source.excerpt,paragraph_id:source.paragraph_id}],verification:{findings:[]},warnings:[source.historical_warning],evidence_policy:'whole_reviewed_paragraph_verbatim'}};
  const rawAnswer=JSON.stringify(answer);e.evaluate('const publicAnswerFixture='+rawAnswer+';renderAnswer(publicAnswerFixture)');nodes=check(e.get('answer-content'));
  assert.equal(e.get('answer-state').textContent,'Svar med kilder');assert(nodes.some(n=>n.tagName==='H3'&&n.textContent==='Fra kilden'));
  assert(nodes.some(n=>n.className==='answer-text'&&n.textContent===source.excerpt));assert(nodes.some(n=>n.tagName==='BLOCKQUOTE'&&n.textContent===source.excerpt));
  assert(!nodes.some(n=>n.className==='technical-details'));assert.equal(e.evaluate('JSON.stringify(publicSourceFixture)'),raw);assert.equal(e.evaluate('JSON.stringify(publicAnswerFixture)'),rawAnswer);
  e.evaluate('renderAnswer('+JSON.stringify({...answer,answer_status:'insufficient_evidence',result:null})+')');nodes=check(e.get('answer-content'));
  assert.equal(e.get('answer-state').textContent,'Utilstrekkelig kildegrunnlag');assert(!nodes.some(n=>n.className==='answer-text'));
  checks.push('public provenance hides approval metadata, preserves exact excerpts and links, warns about currency and keeps refusals');
 }
 {
  const e=municipalEnvironment();
  e.evaluate('let officialMenuUrl="https://www.hamar.kommune.no/meny/";function revealInView(){}');
  e.evaluate(fullSource.slice(fullSource.indexOf('function queryInputProblem('),fullSource.indexOf('let searchGeneration')));
  e.evaluate(fullSource.slice(fullSource.indexOf('function sourceLink('),fullSource.indexOf('async function searchPortal(')));
  e.evaluate(fullSource.slice(fullSource.indexOf('function renderAnswer('),fullSource.indexOf('function providerDescription(')));
  await e.evaluate('refreshMunicipalOptions()');assert(e.get('ai-result').hidden);
  const original=e.getApi();let release,submissions=0;
  e.setApi(async(route,options)=>{
   if(route==='/api/answer'){submissions++;await new Promise(r=>release=r);return {answer:{answer_status:'insufficient_evidence',message:'Teknisk indeksert-melding',result:null,citations:[]}}}
   return original(route,options);
  });
  const pending=e.evaluate('askAi()');await e.tick();
  assert.equal(submissions,1);assert.equal(e.get('ai-result').hidden,false);assert.equal(e.get('ai-result').attributes['aria-busy'],'true');
  release();await pending;assert.equal(e.get('ai-result').hidden,false);
  assert.equal(e.get('ai-result').attributes['aria-busy'],'false');
  assert(e.get('answer-content').children.some(n=>n.textContent.includes('Vi fant ikke nok informasjon')));
  e.get('ai-query').value='bibliotek';await e.get('ai-query').listeners.input();
  assert.equal(e.get('ai-result').hidden,true);assert.equal(e.evaluate('conversationActive'),true);
  const reset=e.get('reset-conversation');reset.focus();assert(reset.focused,'Editing must retain keyboard-accessible reset outside hidden answer');
  const resets=e.calls.filter(route=>route==='/api/conversation/reset').length;
  await reset.listeners.click();assert.equal(e.evaluate('conversationActive'),false);
  assert.equal(e.calls.filter(route=>route==='/api/conversation/reset').length,resets+1);
  assert.equal(e.get('ai-result').hidden,true);
  await e.evaluate('selectAishaMode(true)');await e.evaluate('selectAishaMode(false)');
  assert.equal(e.get('ai-result').hidden,true);assert.equal(submissions,1);
  checks.push('municipal panel hidden before submission; visible while loading/after response; reset/navigation never generate or show empty panel');
 }
 {
  const e=environment();e.data.web_search_allowed=true;await e.ready('ollama');
  assert.equal(e.get('chat-search-control').hidden,false);
  assert.equal(e.get('chat-web-search').disabled,false);assert.equal(e.get('chat-web-search').checked,false);
  assert.equal(e.counts().posts,0);
  e.evaluate('renderChatMessage({role:"assistant",text:"Fiktivt kildeutdrag.",ai_generated:true,web_search_used:true,research_verified:true,citations:[{url:"https://www.ssb.no/synthetic-offline/",title:"Fiktiv kilde"}]})');
  const all=n=>[n,...n.children.flatMap(all)],nodes=all(e.get('chat-log'));
  assert(nodes.some(n=>n.textContent.includes('ikke kommunal verifisering eller sannhetsgaranti')));
  assert(nodes.some(n=>n.tagName==='A'&&n.href==='https://www.ssb.no/synthetic-offline/'&&n.rel==='noopener noreferrer'));
  await e.ready('openai');assert.equal(e.get('chat-web-search').disabled,false);assert.equal(e.counts().posts,0);
  checks.push('approved-source research is opt-in for local/cloud; exact source links and limited verification label');
 }
 console.log(JSON.stringify({method:'Deterministic Node VM/DOM model; no browser rendering, network, SDK or inference',passed:checks.length,checks}));
}
(async()=>{
 if(process.argv[2]==='--unit'){await chatUnitTests(process.argv[3]);return}
 if(process.argv[2]==='--render-api-answer'){await chatUnitTests(process.argv[3],JSON.parse(fs.readFileSync(0,'utf8')));return}
 const [port,site,folder,mode='real']=process.argv.slice(2);
 const targets=await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
 const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((ok,no)=>{ws.onopen=ok;ws.onerror=no});
 let next=1;const pending=new Map(),observedNetwork=[],consoleErrors=[],javascriptExceptions=[];
 const queryCases=new Map([
  ['Hvordan fungerer gratis SFO for elever i Hamar?','sfo'],['Hva gjelder for byggesak?','byggesak'],['hva med priser?','followup'],
  ['Hvem får gratis SFO-tid i Hamar?','q1'],['Hva gjelder for gratis SFO?','q2'],['Hvordan søker jeg om SFO?','q3'],
  ['Hva kan jeg bygge uten å søke?','q4'],['Bygge uten søknad','q5'],['Hvordan søker jeg om byggetillatelse?','q6'],['Hva koster parkering i Hamar?','q7'],
  ['Må jeg søke om å bygge garasje?','garage'],['Hvor kan jeg parkere?','park-where'],
  ['Hvor kommer drikkevannet fra?','water-origin'],['Hvordan fungerer vannforsyningen?','water-service'],
  ['Hva kan jeg låne på biblioteket?','library-loan'],['Hva gjelder teleportering?','unsupported']
 ]);
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);return}if(d.method==='Runtime.exceptionThrown')javascriptExceptions.push(d.params.exceptionDetails.text||d.params.exceptionDetails.exception?.description||'JavaScript exception');if(d.method==='Log.entryAdded'&&d.params.entry.level==='error')consoleErrors.push(d.params.entry.text);if(d.method==='Network.requestWillBeSent'){const req=d.params.request,path=new URL(req.url).pathname,row={path,method:req.method,status:null,mimeType:null,queryCase:null};if((path==='/api/search'||path==='/api/answer')&&req.method==='POST'&&req.postData){try{row.queryCase=queryCases.get(JSON.parse(req.postData).query)||null}catch{}}observedNetwork.push(row)}if(d.method==='Network.responseReceived'){const row=observedNetwork.findLast(x=>x.path===new URL(d.params.response.url).pathname&&x.status===null);if(row){row.status=d.params.response.status;row.mimeType=d.params.response.mimeType}}};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=next++;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error(method))}},5000)});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 const typeInto=async(id,value)=>{const quoted=JSON.stringify(id);await evaluate('(()=>{const e=document.getElementById('+quoted+');e.focus();e.value="";e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');await send('Input.insertText',{text:value})};
 const pressEnter=async()=>{await send('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13})};
 // Native summary activation needs the character event as well as keydown.
 const pressDisclosureEnter=async()=>{await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',text:'\r',unmodifiedText:'\r',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13})};
 const wait=async expression=>{for(let i=0;i<300;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100))}throw Error('Condition failed '+expression+' STATE '+JSON.stringify(await evaluate('({portal:document.getElementById("portal-status").textContent,count:document.getElementById("result-count").textContent,status:document.getElementById("answer-state").textContent,answerArticles:document.querySelectorAll("#answer-content article").length,answerSourceLinks:document.querySelectorAll("#answer-content .source-link").length,answerData:(()=>{try{const x=window.__lastAnswer;return {status:x?.answer_status,claims:x?.result?.claims?.length,findings:x?.result?.verification?.findings?.length,citations:x?.citations?.length}}catch{return null}})()})')))};
 await send('Page.enable');await send('Runtime.enable');await send('Log.enable');await send('Network.enable');
 // Inspect API results in the test driver; the website no longer renders raw JSON.
 await send('Page.addScriptToEvaluateOnNewDocument',{source:`
  const originalFetch=window.fetch.bind(window);
  window.__initialProviderCalls=0;
  window.fetch=async(...args)=>{
   const path=new URL(args[0],location.href).pathname;
   if(${JSON.stringify(mode)}==='synthetic'&&path==='/api/providers'&&++window.__initialProviderCalls===1){
    await new Promise(resolve=>window.__releaseInitialProvider=resolve);
   }
   const answer=path==='/api/answer';
   if(answer)window.__lastAnswer=null;
   const response=await originalFetch(...args);
   if(answer&&response.ok){window.__answerResponse=await response.clone().json();window.__lastAnswer=window.__answerResponse.answer;}
   return response;
  };
 `});
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:site});
 if(mode==='synthetic'){
  await wait('typeof window.__releaseInitialProvider==="function"');
  if(!await evaluate('providerBusy && document.getElementById("refresh-providers").disabled && document.getElementById("reset-conversation").disabled && document.getElementById("ai-button").disabled'))throw Error('Initial discovery must hold provider controls');
  await evaluate('document.getElementById("refresh-providers").click();document.getElementById("ai-form").requestSubmit();true');
  if(!await evaluate('window.__initialProviderCalls===1 && !window.__answerResponse'))throw Error('Initial discovery raced a refresh or answer');
  await evaluate('window.__releaseInitialProvider();true');
 }
 await wait('document.querySelectorAll(".category-card").length===8');
 await wait('chatReady && !chatLoading');
 if(!await evaluate('!document.getElementById("chat-mode").hidden && document.getElementById("municipal-mode").hidden && document.getElementById("mode-chat").getAttribute("aria-pressed")==="true"'))throw Error('Chat must be the primary visible mode');
 if(observedNetwork.some(r=>r.path==='/api/chat'&&r.method==='POST'))throw Error('Initial page dispatched inference');
 if(mode==='synthetic'){
  const welcomeLayouts=[];
  for(const [width,height] of [[1440,1100],[768,1024],[390,844],[320,900]]){
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<650});
   const layout=await evaluate(`(()=>{const prompts=[...document.querySelectorAll('.chat-prompts button')];return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
    heading:document.querySelector('.chat-empty h2').textContent,avatar:document.querySelector('.chat-welcome-avatar').checkVisibility(),
    prompts:prompts.map(b=>({label:b.textContent.trim(),height:b.getBoundingClientRect().height,width:b.getBoundingClientRect().width,icon:!!b.querySelector('svg'),radius:parseFloat(getComputedStyle(b).borderRadius)})),
    inputFont:parseFloat(getComputedStyle(document.getElementById('chat-message')).fontSize),sendHeight:document.getElementById('chat-send').getBoundingClientRect().height}})()`);
   if(layout.overflow||!layout.avatar||layout.heading!=='Hva kan jeg hjelpe deg med?'||layout.prompts.length!==4||!layout.prompts.every(p=>p.icon&&p.width>=44&&p.height>=44&&p.radius>=20)||layout.inputFont<16||layout.sendHeight<44)throw Error('Welcome responsive failure '+JSON.stringify(layout));
   welcomeLayouts.push(layout);
  }
  await evaluate('document.querySelector(".chat-prompts button").focus();true');await pressDisclosureEnter();
  if(!await evaluate('document.getElementById("chat-message").value.length>0')||observedNetwork.some(r=>r.path==='/api/chat'&&r.method==='POST'))throw Error('Suggestion did not prefill safely');
  await evaluate('document.getElementById("chat-message").value="";updateChatControls();true');
  for(const provider of ['openai','ollama']){
   await evaluate('document.querySelector('+JSON.stringify('#chat-model-choices [data-value^="'+provider+'|"]')+').focus();true');
   await pressDisclosureEnter();
   if(!await evaluate('document.getElementById("chat-provider").value.startsWith('+JSON.stringify(provider+'|')+')')||observedNetwork.some(r=>r.path==='/api/chat'&&r.method==='POST'))throw Error('Native chat model activation submitted generation');
  }
  console.log('CHAT_WELCOME_LAYOUTS',JSON.stringify(welcomeLayouts));
 }
 await evaluate('document.getElementById("mode-municipal").click();true');
 if(mode==='synthetic'){
  const probe=async(fn,arg)=>evaluate('('+fn.toString()+')('+JSON.stringify(arg)+')');
  const assert=(condition,message)=>{if(!condition)throw Error(message)};
  const shot=async name=>fs.writeFileSync(folder+'/'+name+'.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'),{flag:'wx'});
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  const layouts=[];
  for(const [width,height] of [[1440,1100],[768,1024],[390,844],[320,900]]){
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<650});
   await probe(()=>{scrollTo({top:0,behavior:'instant'});return true});
   const layout=await probe(()=>{
    const cards=[...document.querySelectorAll('.category-card')];
    const color=s=>s.match(/[\d.]+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4});
    const luminance=a=>.2126*a[0]+.7152*a[1]+.0722*a[2];
    const ratios=cards.map(card=>{const c=getComputedStyle(card);const a=luminance(color(c.color)),b=luminance(color(c.backgroundColor));return (Math.max(a,b)+.05)/(Math.min(a,b)+.05)});
    return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,cards:cards.length,
     targetSizes:cards.map(c=>{const r=c.getBoundingClientRect();return [r.width,r.height]}),
     iconsAboveLabels:cards.every(c=>c.querySelector('.category-label').getBoundingClientRect().top>=c.querySelector('.category-icon').getBoundingClientRect().bottom),
     circularIcons:cards.every(c=>{const icon=c.querySelector('.category-icon'),r=icon.getBoundingClientRect(),radius=getComputedStyle(icon).borderRadius;return Math.abs(r.width-r.height)<1&&(radius.endsWith('%')?parseFloat(radius)>=50:parseFloat(radius)>=r.width/2)}),
     connectorArrows:document.querySelectorAll('.category-card .arrow').length,
     textContrast:Math.min(...ratios),inputFont:parseFloat(getComputedStyle(document.getElementById('ai-query')).fontSize),
     privacyVisible:document.getElementById('privacy').checkVisibility(),
     searchLabelVisible:getComputedStyle(document.querySelector('#search-button .button-label')).display!=='none'};
   });
   assert(!layout.overflow&&layout.cards===8&&layout.iconsAboveLabels&&layout.circularIcons&&layout.connectorArrows===0&&layout.targetSizes.every(([w,h])=>w>=44&&h>=44)&&layout.textContrast>=4.5&&layout.inputFont>=16&&layout.privacyVisible&&layout.searchLabelVisible,'Responsive/accessibility check '+JSON.stringify(layout));
   layouts.push(layout);await shot('synthetic-'+width);
  }
  await probe(()=>{document.querySelector('[data-service="vann"]').focus();return true});
  await pressDisclosureEnter();
  await wait('document.querySelectorAll("#search-results .result-card").length>0 && !document.getElementById("search-button").disabled');
  assert(await probe(()=>document.querySelector('[data-service="vann"]').getAttribute('aria-pressed')==='true'),'Topic keyboard selection did not update');
  await typeInto('ai-query','vann');await pressEnter();
  await wait('window.__lastAnswer?.answer_status==="demo" && !document.getElementById("ai-button").disabled');
  assert(await probe(()=>window.__lastAnswer.result.source.synthetic===true && window.__lastAnswer.result.verification.findings.length===0),'Synthetic answer must remain explicit and checked');
  const exportValid=await probe(async()=>{
   const response=await fetch('/api/results/'+window.__answerResponse.run_id,{headers:{'X-Hamar-Token':document.querySelector('meta[name="hamar-token"]').content}});
   const result=await response.json();return response.ok&&JSON.stringify(result.result.claims)===JSON.stringify(window.__lastAnswer.result.claims);
  });
  assert(exportValid,'Owned answer export changed');
  await shot('synthetic-answer-mobile');
  await probe(()=>{
   window.__uiRealFetch=window.fetch.bind(window);window.__uiAnswerCalls=0;
   window.fetch=async(...args)=>{
    const path=new URL(args[0],location.href).pathname;
    if(path==='/api/answer'){
     window.__uiAnswerCalls++;
     if(window.__uiFault){const fault=window.__uiFault;window.__uiFault=null;return new Response(fault.body,{status:fault.status,headers:{'Content-Type':'application/json'}})}
    }
    if(path==='/api/providers'&&window.__uiProviderFault){window.__uiProviderFault=false;return new Response('{"error":"Syntetisk oppdateringsfeil"}',{status:503,headers:{'Content-Type':'application/json'}})}
    if(path==='/api/providers'&&window.__uiDelayProviders){window.__uiDelayProviders=false;await new Promise(resolve=>window.__uiReleaseProviders=resolve)}
    if(path==='/api/conversation/reset'&&window.__uiResetFault){window.__uiResetFault=false;return new Response('{"error":"Syntetisk nullstillingsfeil"}',{status:503,headers:{'Content-Type':'application/json'}})}
    if(path==='/api/conversation/reset'&&window.__uiDelayReset){window.__uiDelayReset=false;await new Promise(resolve=>window.__uiReleaseReset=resolve)}
    return window.__uiRealFetch(...args);
   };return true;
  });
  for(const [name,status,retryable] of [['provider_timeout',422,true],['provider_authentication',422,false],['provider_rate_limit',429,true]]){
   await probe(fault=>{window.__uiFault={status:fault.status,body:JSON.stringify({error:'Syntetisk leverandorfeil: '+fault.name,error_code:fault.name,retryable:fault.retryable})};window.__uiBefore=window.__uiAnswerCalls;return true},{name,status,retryable});
   await probe(()=>{document.getElementById('ai-form').requestSubmit();return true});
   await wait('!document.getElementById("ai-query").disabled && document.getElementById("answer-state").textContent==="Svarfeil"');
   assert(await probe(expected=>document.getElementById('retry-answer').hidden===!expected&&document.querySelectorAll('#answer-content .answer-text').length===0&&window.__uiAnswerCalls===window.__uiBefore+1,retryable),'Error/retry/no-automatic-request contract '+name);
   if(retryable){
    await probe(()=>{document.getElementById('retry-answer').click();return true});
    await wait('window.__lastAnswer?.answer_status==="demo" && !document.getElementById("ai-query").disabled && document.querySelector("#answer-content .answer-text")!==null');
   }
  }
  await probe(()=>{window.__uiFault={status:502,body:'<html>synthetic malformed response</html>'};document.getElementById('ai-form').requestSubmit();return true});
  await wait('!document.getElementById("ai-query").disabled && document.getElementById("answer-state").textContent==="Svarfeil"');
  assert(await probe(()=>document.getElementById('answer-content').textContent.includes('uleselig')&&!document.getElementById('answer-content').textContent.includes('<html>')),'Malformed HTTP response exposed raw diagnostics');
  await probe(()=>{window.__uiProviderFault=true;document.getElementById('refresh-providers').click();return true});
  await wait('!document.getElementById("refresh-providers").disabled');
  assert(await probe(()=>document.getElementById('provider-model').disabled&&document.getElementById('ai-button').disabled),'Failed discovery left stale AI choice usable');
  await probe(()=>{window.__uiDelayProviders=true;window.__uiBefore=window.__uiAnswerCalls;document.getElementById('refresh-providers').click();return true});
  await wait('typeof window.__uiReleaseProviders==="function"');
  assert(await probe(()=>{askAi();return document.getElementById('ai-query').disabled&&window.__uiAnswerCalls===window.__uiBefore}),'Answer dispatched while provider metadata was pending');
  await probe(()=>{window.__uiReleaseProviders();window.__uiReleaseProviders=null;return true});
  await wait('!document.getElementById("refresh-providers").disabled && !document.getElementById("provider-model").disabled');
  assert(await probe(()=>document.getElementById('provider-model').value==='mock|mock'),'Discovery recovery silently chose cloud');
  await probe(()=>{window.__uiDelayReset=true;window.__uiBefore=window.__uiAnswerCalls;document.getElementById('reset-conversation').click();return true});
  await wait('typeof window.__uiReleaseReset==="function"');
  assert(await probe(()=>{askAi();return document.getElementById('ai-query').disabled&&document.getElementById('answer-state').classList.contains('loading')&&window.__uiAnswerCalls===window.__uiBefore}),'Answer dispatched while conversation reset was pending');
  await probe(()=>{window.__uiReleaseReset();window.__uiReleaseReset=null;return true});
  await wait('!providerBusy && !document.getElementById("ai-query").disabled');
  await probe(()=>{window.__uiResetFault=true;document.getElementById('reset-conversation').click();return true});
  await wait('!providerBusy');
  assert(await probe(()=>chosenProvider===null&&document.getElementById('ai-button').disabled&&document.getElementById('answer-state').classList.contains('warning')),'Failed reset left stale context usable or loading');
  await probe(()=>{document.getElementById('refresh-providers').click();return true});
  await wait('!providerBusy && chosenProvider==="mock"');
  await probe(()=>{
   populateProviders({choices:[{provider:'openai',model:'synthetic-cloud-fixture',label:'Syntetisk test av OpenAI-valg',available:true,availability_status:'configured',processing:'external',reason:'Tilkobling er ikke testet.'}]},'');
   return true;
  });
  assert(await probe(()=>chosenProvider===null&&document.getElementById('ai-button').disabled&&!document.getElementById('provider-model').disabled&&document.getElementById('provider-model').value===''),'Cloud must remain manually selectable without automatic selection');
  await probe(()=>{window.__selectionCallsBefore=window.__uiAnswerCalls;document.querySelector('#municipal-model-choices [data-value="openai|synthetic-cloud-fixture"]').focus();return true});
  await pressDisclosureEnter();
  await wait('!providerBusy');
  assert(await probe(()=>window.__uiAnswerCalls===window.__selectionCallsBefore),'Native provider button submitted a potentially paid municipal answer');
  assert(await probe(()=>document.getElementById('provider-processing').textContent.includes('betalt')&&document.getElementById('provider-model').selectedOptions[0].textContent==='OpenAI · konfigurert'&&!document.getElementById('provider-processing').textContent.includes('synthetic-cloud-fixture')),'Cloud label must explain payment without claiming connectivity or exposing model IDs');
  await probe(()=>{document.getElementById('refresh-providers').click();return true});
  await wait('!providerBusy');
  assert(await probe(()=>chosenProvider===null&&document.getElementById('ai-button').disabled),'Missing cloud silently switched to another provider');
  await probe(()=>{document.querySelector('#municipal-model-choices [data-value="mock|mock"]').focus();return true});await pressDisclosureEnter();
  await wait('!providerBusy && chosenProvider==="mock"');
  await probe(()=>{
   renderSearch({results:[{title:'Syntetisk historisk kilde',excerpt:'Oppdiktet informasjon om vann.',synthetic:false,url:'https://www.hamar.kommune.no/',approval_status:'historical_expired',historical_warning:'Syntetisk test av utlopte kilder',retrieved_at:'2026-10-21T10:00:00Z',approval_expires:'2026-10-28'}]});return true;
  });
  assert(await probe(()=>{const t=document.getElementById('search-results').textContent;return t.includes('Opplysningene kan ha endret seg. Se kommunens nettside for siste informasjon.')&&!t.includes('Hentet fra kommunens nettside:')&&!/HISTORISK|GODKJENNING|Indeksert:|Invalid Date/u.test(t)}),'Public source caution or hidden approval metadata is incorrect');
  await probe(()=>{renderSearch({results:[{title:'Syntetisk test av registrert periode',excerpt:'Oppdiktet eksempel.',synthetic:false,approval_status:'within_recorded_period'}]});return true});
  assert(await probe(()=>{const t=document.getElementById('search-results').textContent;return t.includes('Kilde')&&!/REGISTRERT PERIODE|ikke oppgitt|Invalid Date/u.test(t)}),'Unknown source date or internal status leaked into the public UI');
  const calendarDates=[];
  for(const timezoneId of ['America/Los_Angeles','Asia/Tokyo']){
   await send('Emulation.setTimezoneOverride',{timezoneId});
   const value=await probe(()=>({date:sourceDate('2026-10-28'),dateWithTime:sourceDate('2026-10-28',true),invalid:sourceDate('2026-02-31')}));
   assert(value.date==='28.10.2026'&&value.dateWithTime==='28.10.2026'&&value.invalid==='ikke oppgitt','Calendar date shifted in '+timezoneId+' '+JSON.stringify(value));
   calendarDates.push({timezoneId,...value});
  }
  await send('Emulation.setTimezoneOverride',{timezoneId:'Europe/Oslo'});
  await probe(()=>{
   const answer=structuredClone(window.__lastAnswer);
   const citation=answer.citations.find(c=>c.paragraph_id===answer.result.claims[0].paragraph_id);
   answer.result.claims=answer.result.claims.slice(0,1);answer.citations=[{...citation,url:'https://www.hamar.kommune.no/',historical_warning:'Syntetisk historisk varsel'}];
   renderAnswer(answer);return true;
  });
  assert(await probe(()=>document.querySelectorAll('.citation-card .notice').length===1&&document.querySelector('.citation-card .notice').textContent==='Opplysningene kan ha endret seg. Se kommunens nettside for siste informasjon.'),'Plain citation currency caution must appear once');
  const ax=await send('Accessibility.getFullAXTree');
  assert(ax.nodes.some(n=>n.role?.value==='group'&&n.name?.value==='Velg AI'),'Provider choice group lacks accessible name');
  assert(ax.nodes.some(n=>n.role?.value==='button'&&n.name?.value==='Syntetisk demo'),'Explicit provider button lacks accessible name');
  assert(ax.nodes.some(n=>n.role?.value==='button'&&n.name?.value==='Søk'),'Search button lacks accessible name');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await probe(()=>{scrollTo({top:0,behavior:'instant'});return true});await shot('synthetic-final-desktop');
  // General chat uses injected SDK/transport fakes in the existing Python demo server.
  await probe(()=>{
   window.__chatPosts=0;window.__chatResetPosts=0;const original=window.fetch;
   window.fetch=async(...args)=>{
    const path=new URL(args[0],location.href).pathname;
    if(path==='/api/chat/state'){
     const response=await original(...args);
     if(window.__chatStateDelay){window.__chatStateDelay=false;await new Promise(resolve=>window.__releaseChatState=resolve)}
     return response;
    }
    if(path==='/api/chat/reset'){
     window.__chatResetPosts++;const response=await original(...args);
     if(window.__chatResetDelay){window.__chatResetDelay=false;await new Promise(resolve=>window.__releaseChatReset=resolve)}
     return response;
    }
    if(path==='/api/chat'){
     window.__chatPosts++;
     if(window.__chatMalformed){window.__chatMalformed=false;return new Response('not-json',{status:200})}
     const response=await original(...args);
     if(window.__chatDelay){window.__chatDelay=false;await new Promise(resolve=>window.__releaseChat=resolve)}
     return response;
    }
    return original(...args);
   };return true;
  });
  assert(await probe(()=>document.getElementById('chat-mode').hidden&&!document.getElementById('municipal-mode').hidden),'Municipal mode selection was lost');
  await probe(()=>{document.getElementById('mode-chat').focus();return true});await pressDisclosureEnter();
  await wait('chatReady && !chatLoading');
  assert(await probe(()=>document.getElementById('municipal-mode').hidden&&!document.getElementById('chat-mode').hidden&&document.getElementById('mode-chat').getAttribute('aria-pressed')==='true'),'Mode switch failed');
  assert(await probe(()=>window.__chatPosts===0&&document.getElementById('chat-provider').value==='ollama|synthetic-local-fixture'&&document.getElementById('chat-send').disabled&&document.getElementById('chat-web-search').disabled&&!document.getElementById('chat-web-search').checked),'Entering chat failed to choose local AI safely');
  await probe(()=>{const e=document.getElementById('chat-provider');e.value='openai|synthetic-cloud-fixture';e.dispatchEvent(new Event('change'));return true});
  await typeInto('chat-message','Forklar hva en algoritme er.');
  await probe(()=>{window.__chatDelay=true;return true});await pressEnter();
  await wait('typeof window.__releaseChat==="function" && chatBusy');
  assert(await probe(()=>document.getElementById('chat-log').getAttribute('aria-busy')==='true'&&document.querySelector('.chat-row.pending')&&document.getElementById('chat-send').disabled),'Chat loading state missing');
  await probe(()=>{document.getElementById('chat-reset').click();return true});
  await wait('chatReady && !chatBusy');
  await probe(()=>{window.__releaseChat();return true});
  await wait('!document.querySelector(".chat-row")');
  assert(await probe(()=>chatLastRequest===null),'Reset retained pending retry');
  await typeInto('chat-message','Forklar en algoritme.');await pressEnter();
  await wait('!chatBusy && document.querySelectorAll(".chat-row.assistant").length===1');
  await typeInto('chat-message','Kan du forklare det enklere?');await pressEnter();
  await wait('!chatBusy && document.querySelectorAll(".chat-row.assistant").length===2');
  assert(await probe(()=>document.querySelectorAll('.chat-row.user').length===2&&document.getElementById('chat-log').textContent.includes('AI-generert svar · kan inneholde feil')),'Followup bubbles or unverified label missing');
  // CHAT-01: stale state cannot undo reset, and reset POSTs are serialized.
  await probe(()=>{window.__releaseChatState=null;window.__chatStateDelay=true;window.__staleLoad=loadChat();return true});
  await wait('typeof window.__releaseChatState==="function"');
  await probe(()=>{window.__resetDuringLoad=resetChat();return true});
  await wait('chatReady && !chatResetting');
  await probe(async()=>{window.__releaseChatState();await window.__staleLoad;return true});
  assert(await probe(()=>document.querySelectorAll('.chat-row').length===0),'Delayed pre-reset GET restored old bubbles');
  await probe(()=>{window.__resetCountBefore=window.__chatResetPosts;window.__chatResetDelay=true;window.__resetOne=resetChat();return true});
  await wait('typeof window.__releaseChatReset==="function"');
  await probe(()=>{window.__resetTwo=resetChat();return true});
  await new Promise(resolve=>setTimeout(resolve,100));
  assert(await probe(()=>window.__chatResetPosts===window.__resetCountBefore+1),'Reset requests overlapped');
  await probe(async()=>{window.__releaseChatReset();await Promise.all([window.__resetOne,window.__resetTwo]);return true});
  assert(await probe(async()=>{const s=await api('/api/chat/state',{headers:{'X-Hamar-Token':token}});return chatRevision===s.revision&&s.messages.length===0&&!chatResetting}),'Serialized resets left stale revision');
  await probe(()=>{window.__chatMalformed=true;return true});
  await typeInto('chat-message','Gi et kort eksempel.');await pressEnter();
  await wait('!chatBusy && !document.getElementById("chat-retry").hidden');
  const postsBeforeRetry=await probe(()=>window.__chatPosts);
  await new Promise(resolve=>setTimeout(resolve,150));
  assert(await probe(()=>window.__chatPosts)===postsBeforeRetry,'Chat automatically retried a potentially paid request');
  await probe(()=>{document.getElementById('chat-retry').click();return true});
  await wait('!chatBusy && document.getElementById("chat-retry").hidden && document.querySelectorAll(".chat-row.assistant").length===1');
  await probe(()=>{window.__chatMalformed=true;return true});
  await typeInto('chat-message','Forklar et annet eksempel.');await pressEnter();
  await wait('!chatBusy && !document.getElementById("chat-retry").hidden');
  await probe(()=>{window.__retryPostsBefore=window.__chatPosts;window.__releaseChatState=null;window.__chatStateDelay=true;window.__obsoleteRetry=sendChat(true);return true});
  await wait('chatChecking && typeof window.__releaseChatState==="function"');
  await probe(()=>{const e=document.getElementById('chat-provider');e.value='ollama|synthetic-local-fixture';e.dispatchEvent(new Event('change'));return true});
  await wait('chatReady && !chatResetting && !document.querySelector(".chat-row")');
  await probe(async()=>{window.__releaseChatState();await window.__obsoleteRetry;return true});
  assert(await probe(()=>window.__chatPosts===window.__retryPostsBefore&&!chatBusy&&!chatChecking),'Obsolete retry submitted after provider/reset change');
  await typeInto('chat-message','Forklar en løkke.');await pressEnter();
  await wait('!chatBusy && document.getElementById("chat-log").textContent.includes("syntetisk lokalt chatsvar")');
  await probe(()=>{
   renderChatMessage({role:'user',text:'<img src=x onerror="window.syntheticAttack=true">'});
   renderChatMessage({role:'assistant',text:'Syntetisk kildevisning, ikke et ekte nettsøk.',web_search_used:true,
    citations:[{title:'Syntetisk eksempel',url:'https://example.org/synthetic'},{title:'unsafe',url:'javascript:alert(1)'}]});return true;
  });
  assert(await probe(()=>!window.syntheticAttack&&document.querySelectorAll('#chat-log img,#chat-log script').length===0&&document.querySelectorAll('.chat-citations a').length===1&&document.querySelector('.chat-citations a').rel==='noopener noreferrer'),'Chat HTML/source rendering is unsafe');
  const chatLayouts=[];
  for(const [width,height] of [[1440,1100],[768,1024],[390,844],[320,900]]){
   await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<650});
   const layout=await probe(()=>{
    const user=document.querySelector('.chat-row.user').getBoundingClientRect(),assistant=document.querySelector('.chat-row.assistant').getBoundingClientRect();
    return {width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth,
     inputFont:parseFloat(getComputedStyle(document.getElementById('chat-message')).fontSize),
     userOnRight:user.left>=assistant.left,avatarVisible:document.querySelector('.chat-row.assistant .robot-avatar').checkVisibility(),
     sendHeight:document.getElementById('chat-send').getBoundingClientRect().height,
     chatLogScrollable:getComputedStyle(document.getElementById('chat-log')).overflowY==='auto'};
   });
   assert(!layout.overflow&&layout.inputFont>=16&&layout.userOnRight&&layout.avatarVisible&&layout.sendHeight>=44&&layout.chatLogScrollable,'Chat responsive failure '+JSON.stringify(layout));
   chatLayouts.push(layout);await probe(()=>{document.getElementById('chat-title').scrollIntoView({block:'start',behavior:'instant'});return true});await shot('chat-'+width);
  }
  const chatAx=await send('Accessibility.getFullAXTree');
  assert(chatAx.nodes.some(n=>n.role?.value==='log'&&n.name?.value==='Samtale med Aisha'),'Chat log accessible name missing');
  assert(chatAx.nodes.some(n=>n.role?.value==='textbox'&&n.name?.value==='Din melding til Aisha'),'Chat input accessible name missing');
  await probe(()=>{document.getElementById('mode-municipal').click();return true});
  assert(await probe(()=>document.getElementById('chat-mode').hidden&&!document.getElementById('municipal-mode').hidden&&document.querySelectorAll('.category-card').length===8),'Mode switching damaged municipal workflow');
  console.log('CHAT_UI',JSON.stringify({method:'Synthetic SDK/transport fakes only; zero genuine provider/search calls',layouts:chatLayouts,
   no_automatic_cloud_selection:true,no_automatic_paid_retry:true,followup:true,reset_stale_ui:true,local_selection:true,
   stale_state_after_reset_blocked:true,serialized_reset_requests:true,obsolete_retry_after_provider_change_blocked:true,
   search_default_off:true,source_links_mock_only:true,inert_html:true,accessible_log_and_input:true,municipal_preserved:true}));
  assert(javascriptExceptions.length===0&&consoleErrors.length===0,'Browser console failure '+JSON.stringify({javascriptExceptions,consoleErrors}));
  console.log('SYNTHETIC_UI',JSON.stringify({provider_calls:'mocked only; zero inference providers constructed',layouts,initial_discovery_guard:true,calendar_dates:calendarDates,single_historical_notice:true,keyboard_topic:true,owned_export:exportValid,manual_retry:true,malformed_response:true,provider_recovery:true,pending_reset_guard:true,no_automatic_cloud_selection:true,configured_not_connected:true,source_status_dates:true,accessibility_names:true,javascript_exceptions:javascriptExceptions,console_errors:consoleErrors}));
  ws.close();return;
 }

 for(let i=0;i<100&&!observedNetwork.findLast(r=>r.path==='/favicon.ico'&&r.status!==null);i++)await new Promise(r=>setTimeout(r,50));
 const favicon=observedNetwork.findLast(r=>r.path==='/favicon.ico');
 if(!favicon||favicon.status!==200||favicon.mimeType!=='image/vnd.microsoft.icon')throw Error('Project favicon failed to load as an ICO '+JSON.stringify(favicon));
 console.log('FAVICON',JSON.stringify(favicon));
 if(!await evaluate('document.querySelector(".developer, #source, #run, #download, #portal-download, #result, #json")===null && !/Kildevalg|Kontrollert arbeidsflyt|Last ned.*JSON/i.test(document.body.innerText)'))throw Error('Removed source/workflow/export controls remain in the website');
 await wait('!document.getElementById("provider-model").disabled');
 const providerState=await evaluate('(()=>{const s=document.getElementById("provider-model");return {selected:s.value,label:s.selectedOptions[0]?.textContent,openai:[...s.options].filter(o=>o.value.startsWith("openai|")).map(o=>({disabled:o.disabled,label:o.textContent}))}})()');
 if(providerState.selected!=='ollama|llama3.2:3b'||!providerState.openai.length||providerState.openai.some(o=>!o.disabled))throw Error('Provider selector does not reflect the installed local model and visible disabled OpenAI state '+JSON.stringify(providerState));
 console.log('PROVIDER_SELECTOR',JSON.stringify(providerState));
 const image=await evaluate('(async()=>{const i=new Image();i.src="/hamar-background.png";await i.decode();return {width:i.naturalWidth,height:i.naturalHeight,active:document.body.classList.contains("has-scenic-image"),css:getComputedStyle(document.querySelector(".landscape")).backgroundImage}})()');
 if(!image.active||image.width<1||!image.css.includes('hamar-background.png'))throw Error('Photo not active');
 console.log('BACKGROUND_IMAGE',JSON.stringify(image));
 const simpleCopy=await evaluate(`({heading:document.querySelector('h1').textContent,intro:document.querySelector('.intro').textContent,subtitle:document.querySelector('.subtitle').textContent,label:document.querySelector('label[for="query"]').textContent,placeholder:document.getElementById('query').placeholder,aiHeading:document.getElementById('ai-title').textContent,ai:document.querySelector('.ai-intro').textContent,removed:document.querySelector('.workflow-steps,.mode-strip,#mode,#coverage,.source-policy,#ai-privacy')!==null,aboutClosed:!document.getElementById('about-service').open})`);
 if(simpleCopy.heading!=='Aisha Agent'||simpleCopy.intro!=='Søk etter informasjon om Hamar og kommunale tjenester.'||simpleCopy.subtitle!=='Din AI-guide til informasjon og kommunale tjenester i Hamar.'||simpleCopy.label!=='Søk etter en tjeneste'||simpleCopy.placeholder!=='F.eks. parkering, vann eller byggesak'||simpleCopy.aiHeading!=='Spør Aisha'||simpleCopy.ai!=='Still et spørsmål om informasjon og kommunale tjenester i Hamar.'||simpleCopy.removed||!simpleCopy.aboutClosed)throw Error('Aisha branding/copy/layout mismatch '+JSON.stringify(simpleCopy));
 const expectedHeroCopy=['Aisha Agent','Din AI-guide til informasjon og kommunale tjenester i Hamar.','Hva kan vi hjelpe deg med?','Søk etter informasjon om Hamar og kommunale tjenester.'];
 const checkHeroLayout=async(viewport)=>{
  await evaluate('window.scrollTo({top:0,behavior:"instant"});true');
  const state=await evaluate('(()=>{const nodes=[...document.querySelector(".hero").children].slice(0,4);return {headings:document.querySelectorAll("h1").length,tags:nodes.map(e=>e.tagName),copy:nodes.map(e=>e.textContent),sizes:nodes.map(e=>parseFloat(getComputedStyle(e).fontSize)),boxes:nodes.map(e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right}}),width:innerWidth,height:innerHeight,overflow:document.documentElement.scrollWidth>innerWidth}})()');
  if(state.headings!==1||JSON.stringify(state.tags)!==JSON.stringify(['H1','P','H2','P'])||JSON.stringify(state.copy)!==JSON.stringify(expectedHeroCopy)||state.sizes[0]<=state.sizes[2]||state.overflow||state.boxes.some((r,i)=>r.left<0||r.right>state.width+1||(i>0&&r.top<state.boxes[i-1].bottom))||state.boxes[0].top<0||state.boxes[0].bottom>state.height)throw Error('Main heading order, prominence or responsive layout failed at '+viewport+' '+JSON.stringify(state));
  console.log('AISHA_HERO_LAYOUT',viewport,JSON.stringify(state));
 };
 await checkHeroLayout('desktop');
 await evaluate('document.querySelector("#about-service summary").click();true');
 if(!await evaluate('document.getElementById("about-service").open && document.getElementById("privacy").checkVisibility()'))throw Error('Privacy/coverage help is inaccessible');
 await evaluate('document.querySelector("#about-service summary").click();true');
 console.log('SIMPLIFIED_COPY',JSON.stringify(simpleCopy));
 const title=await evaluate('document.title');if(title!=='Aisha Agent')throw Error(title);
 if(!await evaluate('document.querySelector(".brand").getAttribute("aria-label")==="Aisha Agent, forsiden" && document.querySelector(".brand").innerText.startsWith("Aisha Agent") && !/KommuneAgent|Informasjon Agent for Hamar|Hamar-agenten/.test(document.body.textContent)'))throw Error('Legacy agent branding remains visible or in the accessible brand name');
 const projectCopy=await evaluate('(()=>{const p=document.getElementById("about-project");return {closed:!p.open,afterService:document.getElementById("about-service").nextElementSibling===p,summary:p.querySelector("summary").textContent,title:p.querySelector("h2").textContent,goal:p.querySelector("h3").textContent,paragraphs:[...p.querySelectorAll("p")].map(x=>x.textContent)}})()');
 const expectedProjectParagraphs=['Studentprosjekt i kunstig intelligens ved Universitetet i Innlandet.','Å utvikle og evaluere en trygg og pålitelig AI-agent som automatisk henter, behandler og kontrollerer offentlig informasjon, slik at den blir enklere og mer tilgjengelig for alle i samfunnet.','Dette er et studentprosjekt og ikke en offisiell tjeneste fra Hamar kommune.'];
 if(!projectCopy.closed||!projectCopy.afterService||projectCopy.summary!=='Om prosjektet'||projectCopy.title!=='KIUA-2003 – Aisha Agent'||projectCopy.goal!=='Prosjektets læringsmål'||JSON.stringify(projectCopy.paragraphs)!==JSON.stringify(expectedProjectParagraphs))throw Error('Project disclosure copy, order or default state mismatch '+JSON.stringify(projectCopy));
 await evaluate('document.querySelector("#about-project summary").focus();true');await pressDisclosureEnter();
 await wait('document.getElementById("about-project").open');
 if(!await evaluate('document.querySelector("#about-project h2").checkVisibility() && document.documentElement.scrollWidth<=innerWidth'))throw Error('Project disclosure is not accessible or overflows');
 await evaluate('document.getElementById("about-project").scrollIntoView({block:"start",behavior:"instant"});true');
 await wait('(()=>{const r=document.getElementById("about-project").getBoundingClientRect();return r.top>=-2&&r.top<innerHeight})()');
 fs.writeFileSync(folder+'/desktop-project.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await pressDisclosureEnter();await wait('!document.getElementById("about-project").open');
 await evaluate('window.scrollTo({top:0,behavior:"instant"});true');
 console.log('AISHA_PROJECT_DISCLOSURE',JSON.stringify(projectCopy));
 const footer=await evaluate('document.querySelector("footer").textContent');
 if(footer!=='Studentprosjekt ved Universitetet i Innlandet.')throw Error(footer);
 if(await evaluate('/linda|jesper|guttormsen|svela/i.test(document.body.innerText)'))throw Error('Personal author information is visible');
 fs.writeFileSync(folder+'/desktop.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 const choices=['skole','bolig','helse','vann','miljo','transport','kultur','politikk'];
 for(const choice of choices){console.log("SEARCH",choice);
  await evaluate(`document.querySelector('[data-service="${choice}"]').click();true`);
  await wait('!document.getElementById("search-button").disabled && document.querySelectorAll(".result-card").length>0');
  if(!await evaluate('/^[1-9][0-9]* treff/.test(document.getElementById("result-count").textContent)'))throw Error('Bad service '+choice);
 }
 await evaluate('document.getElementById("clear-category").click();true');
 await wait('!document.getElementById("search-button").disabled');
  await typeInto('ai-query','Hvordan fungerer gratis SFO for elever i Hamar?');
 await evaluate('window.__keyEvents=[];window.__formSubmits=0;document.getElementById("ai-query").addEventListener("keydown",e=>window.__keyEvents.push(e.key));document.getElementById("ai-form").addEventListener("submit",()=>window.__formSubmits++)');
 const gateBeforeEnter=await evaluate('(()=>({query:document.getElementById("ai-query").value,allowed:isAllowedRealQuery(document.getElementById("ai-query").value,conversationActive),terms:(document.getElementById("ai-query").value.normalize("NFC").toLocaleLowerCase("nb-NO").replaceAll("æ","ae").replaceAll("ø","o").replaceAll("å","a").match(/[\\p{L}\\p{N}]+/gu)||[]),stopwords:[...queryStopwords],aliases:[...queryAliases],allowedTerms:[...allowedRealQueryTerms]}))()');
 console.log('AI_QUERY_GATE_BEFORE_ENTER',JSON.stringify(gateBeforeEnter));
 if(!gateBeforeEnter.allowed)throw Error('Natural-language SFO question was not accepted by the current portal contract '+JSON.stringify(gateBeforeEnter));
 await pressEnter();
 for(let i=0;i<100&&!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='sfo');i++)await new Promise(r=>setTimeout(r,50));
  if(!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='sfo'))throw Error('Enter key did not send the direct AI question to /api/answer '+JSON.stringify({requests:observedNetwork.filter(r=>r.path==='/api/answer'),gate:await evaluate('({allowed:isAllowedRealQuery(document.getElementById("ai-query").value,conversationActive),query:document.getElementById("ai-query").value,buttonDisabled:document.getElementById("ai-button").disabled,active:document.activeElement.id,ready:portalReady,provider:chosenProvider,conversationActive,keyEvents:window.__keyEvents,submits:window.__formSubmits,status:document.getElementById("answer-state").textContent,portal:document.getElementById("portal-status").textContent,content:document.getElementById("answer-content").textContent})'),exceptions:javascriptExceptions,consoleErrors}));
 await wait('!document.getElementById("ai-button").disabled');
 await wait('document.querySelectorAll("#answer-content article").length>0 && document.querySelector("#answer-content .source-link")!==null');
 if(!await evaluate('document.querySelector("#answer-content .answer-text")!==null && document.querySelector("#answer-content .source-excerpt blockquote")!==null && document.querySelector("#answer-content .technical-details")==null && document.querySelectorAll("#answer-content .citation-card .source-link").length===1'))throw Error('Answer, source excerpt, hidden technical detail or deduplicated citation presentation is incorrect');
 const sfoLink=await evaluate('document.querySelector("#answer-content .source-link").href');
 if(!sfoLink.startsWith('https://www.hamar.kommune.no/'))throw Error('SFO answer has no official source link');
 await evaluate('document.getElementById("ai-result").scrollIntoView({block:"start",behavior:"instant"})');
 await new Promise(r=>setTimeout(r,250));
 fs.writeFileSync(folder+'/desktop-answer.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 // Export remains available through the authenticated backend, without a UI control.
 const downloaded=await evaluate(`(async()=>{const r=await fetch("/api/results/"+window.__answerResponse.run_id,{headers:{"X-Hamar-Token":document.querySelector('meta[name="hamar-token"]').content}});if(!r.ok)throw Error("Backend export failed");return r.json()})()`);
 if(downloaded.result.verification.findings.length)throw Error('Unexpected findings'); if(downloaded.result.source.synthetic || downloaded.result.provider!=='ollama:llama3.2:3b')throw Error('Not real municipal inference'); if(!downloaded.citations.some(c=>c.source_id==='hamar-sfo'&&c.url.startsWith('https://www.hamar.kommune.no/')))throw Error('Missing SFO municipality citation');
 if(/linda|jesper|guttormsen|svela/i.test(JSON.stringify(downloaded)))throw Error('Student names leaked into answer JSON');
 if(observedNetwork.some(r=>r.path==='/api/search'&&r.method==='POST'&&r.queryCase==='sfo'))throw Error('Direct AI question was incorrectly mixed into ordinary search');
 if(!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='sfo'&&r.status===200))throw Error('Verified answer endpoint did not receive the natural SFO question or return HTTP 200');
 console.log('REAL_PROVIDER',downloaded.result.provider,'SFO_CITATIONS',downloaded.citations.length,'API',JSON.stringify(observedNetwork.filter(r=>r.path.startsWith('/api/'))));
 const sfoAnswer=await evaluate('document.querySelector("#answer-content .answer-text").textContent');
 await evaluate('document.getElementById("ai-query").value="hva med priser?";document.getElementById("ai-query").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("ai-form").requestSubmit();true');
 for(let i=0;i<200&&!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup'&&r.status!==null);i++)await new Promise(r=>setTimeout(r,50));
 const contextualFollowup=observedNetwork.find(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup');
 if(!contextualFollowup||contextualFollowup.status!==200)throw Error('Context-aware follow-up did not reach the verified workflow '+JSON.stringify(contextualFollowup));
 await wait('window.__lastAnswer!=null');
 if(!await evaluate('document.querySelector("#answer-content").textContent.includes("Oppfølgingsspørsmål:") && window.__lastAnswer.is_follow_up'))throw Error('Follow-up provenance was not visible');
 const answerBeforeOrdinary=await evaluate('document.querySelector("#answer-content .answer-text")?.textContent||document.querySelector("#answer-content .empty-answer")?.textContent||""');
 console.log('CONTEXTUAL_FOLLOWUP',JSON.stringify({http:contextualFollowup.status,sfoAnswer,followupVisible:Boolean(answerBeforeOrdinary)}));
 await evaluate('document.getElementById("query").value="byggesak";document.getElementById("search-form").requestSubmit();true');
 await wait('!document.getElementById("search-button").disabled && document.querySelectorAll("#search-results .result-card").length>0');
 if(await evaluate('document.querySelector("#answer-content .answer-text")?.textContent||document.querySelector("#answer-content .empty-answer")?.textContent||""')!==answerBeforeOrdinary)throw Error('Ordinary search contaminated the independent AI answer');
 await evaluate('document.getElementById("reset-conversation").click();true');
 await wait('document.getElementById("answer-state").textContent==="Samtalen er nullstilt"');
 if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download")===null'))throw Error('Conversation reset left a stale answer or downloadable result');
 await typeInto('ai-query','hva med priser?');await pressEnter();
 for(let i=0;i<100&&!observedNetwork.findLast(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup');i++)await new Promise(r=>setTimeout(r,50));
 await wait('!document.getElementById("ai-button").disabled && document.getElementById("answer-state").textContent==="Kan du presisere spørsmålet?"');
 const afterReset=observedNetwork.findLast(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup');
 const afterResetData=await evaluate('window.__lastAnswer');
 if(!afterReset||afterReset.status!==200||afterResetData.answer_status!=='clarification_required'||afterResetData.is_follow_up||!await evaluate('document.querySelector("#answer-content .official-menu-fallback a")?.href==="https://www.hamar.kommune.no/meny/"'))throw Error('Safe ambiguous question after reset did not request clarification without prior context '+JSON.stringify({afterReset,answer:afterResetData}));
 console.log('RESET_CONTEXT_ISOLATION',JSON.stringify({http:afterReset.status,status:afterResetData.answer_status,is_follow_up:afterResetData.is_follow_up,menu:afterResetData.official_menu_url}));
  await evaluate('document.getElementById("ai-query").value="Hva gjelder for byggesak?";document.getElementById("ai-query").dispatchEvent(new Event("input",{bubbles:true}));true');
  if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download")===null'))throw Error('Old answer remained visible when a new AI question was entered');
  await evaluate('document.getElementById("ai-form").requestSubmit();true');
  for(let i=0;i<100&&!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='byggesak');i++)await new Promise(r=>setTimeout(r,50));
  if(!observedNetwork.some(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='byggesak'))throw Error('Building-permit AI question was not sent');
  await wait('document.querySelectorAll("#answer-content .answer-text").length>0');
 if(await evaluate('document.querySelector("#answer-content").textContent.includes("Alle barn")'))throw Error('SFO answer remained visible after building-permit search');
  await wait('document.querySelector("#answer-content .answer-text")!==null && document.querySelector("#answer-content .source-link")!==null');
 if(!await evaluate('document.querySelector("#answer-content .source-link").href.includes("bygge-uten-a-soke")'))throw Error('Building-permit answer did not cite the approved official page');
 await evaluate('document.getElementById("ai-result").scrollIntoView({block:"start",behavior:"instant"})');
 await new Promise(r=>setTimeout(r,250));
 fs.writeFileSync(folder+'/building-permit-answer.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 console.log('BUILDING_PERMIT_SOURCE',await evaluate('document.querySelector("#answer-content .source-link").href'));
  await evaluate('document.getElementById("ai-query").value="service";document.getElementById("ai-query").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("ai-form").requestSubmit();true');
  await wait('!document.getElementById("ai-button").disabled && document.getElementById("answer-state").textContent==="Utilstrekkelig kildegrunnlag"');
  if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download")===null'))throw Error('Unsupported question produced a stale or downloadable answer');
  console.log('INSUFFICIENT_EVIDENCE',await evaluate('document.getElementById("answer-content").textContent'));
  const requiredQuestions=[
   ['Hvem får gratis SFO-tid i Hamar?','evidence_checked','hamar-sfo'],
   ['Hva gjelder for gratis SFO?','evidence_checked','hamar-sfo'],
   ['Hvordan søker jeg om SFO?','insufficient_evidence','hamar-sfo'],
   ['Hva kan jeg bygge uten å søke?','evidence_checked','hamar-byggesak'],
   ['Bygge uten søknad','evidence_checked','hamar-byggesak'],
   ['Hvordan søker jeg om byggetillatelse?','insufficient_evidence','hamar-byggesak'],
   ['Hva koster parkering i Hamar?','insufficient_evidence','hamar-parkering'],
   ['M\u00e5 jeg s\u00f8ke om \u00e5 bygge garasje?','evidence_checked','hamar-byggesak'],
   ['Hvor kan jeg parkere?','evidence_checked','hamar-parkering'],
   ['Hvor kommer drikkevannet fra?','insufficient_evidence','hamar-drikkevann'],
   ['Hvordan fungerer vannforsyningen?','evidence_checked','hamar-drikkevann'],
   ['Hva kan jeg l\u00e5ne p\u00e5 biblioteket?','insufficient_evidence','hamar-bibliotek'],
   ['Hva gjelder teleportering?','clarification_required',null]
  ];
  const questionResults=[];
  for(const [query,expected,sourceId] of requiredQuestions){
   await typeInto('ai-query',query);
   if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download")===null'))throw Error('A previous answer remained visible for a new question '+query);
   await pressEnter();
   await wait('!document.getElementById("ai-button").disabled && window.__lastAnswer!=null');
   await wait('(()=>{const r=document.getElementById("ai-result").getBoundingClientRect();return r.top>=-2&&r.top<innerHeight})()');
   const state=await evaluate('(()=>{const a=window.__lastAnswer;const r=document.getElementById("ai-result").getBoundingClientRect();return {status:a.answer_status,provider:a.result?.provider||null,claims:a.result?.claims?.length||0,citations:a.citations.map(c=>c.source_id),citation_records:a.citations.length,links:[...document.querySelectorAll("#answer-content .source-link")].map(x=>x.href),visible:r.top>=-2&&r.top<innerHeight}})()');
   if(state.status!==expected||(sourceId&&!state.citations.includes(sourceId))||!state.visible)throw Error('Wrong or off-screen answer for '+query+' '+JSON.stringify(state));
   const network=observedNetwork.findLast(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase===queryCases.get(query));
   if(!network||network.status!==200)throw Error('Expected local answer API response was not observed for '+query+' '+JSON.stringify(network));
   if(expected==='evidence_checked'&&(state.provider!=='ollama:llama3.2:3b'||state.claims<1||!state.links.some(url=>url.startsWith('https://www.hamar.kommune.no/'))))throw Error('Grounded answer or official citation missing for '+query+' '+JSON.stringify(state));
   if(query==='Hvor kan jeg parkere?'&&state.links.filter(url=>url==='https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/').length!==1)throw Error('Parking source URL was not presented exactly once in the answer '+JSON.stringify(state));
   if(query==='Hva koster parkering i Hamar?'&&(state.links.filter(url=>url==='https://www.hamar.kommune.no/parkering/parkeringsplasser-og-betaling/').length!==1||state.citation_records<2))throw Error('Insufficient-evidence parking view must deduplicate links while retaining paragraph citations '+JSON.stringify(state));
   if(expected==='insufficient_evidence'&&(state.claims!==0||!state.links.some(url=>url.startsWith('https://www.hamar.kommune.no/'))))throw Error('Insufficient-evidence explanation did not expose its reviewed source '+query+' '+JSON.stringify(state));
   if(expected==='clarification_required'&&(!await evaluate('document.querySelector("#answer-content .official-menu-fallback a")?.href==="https://www.hamar.kommune.no/meny/"')||state.provider!==null))throw Error('Safe unsupported question did not show the official menu fallback without invoking Ollama '+query+' '+JSON.stringify(state));
   questionResults.push({query,http_status:network.status,status:state.status,provider:state.provider,claims:state.claims,citations:state.citations,source_links:state.links,answer_panel_visible:state.visible});
   if(query==='Hva kan jeg bygge uten å søke?')fs.writeFileSync(folder+'/natural-building-answer.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  }
  console.log('REQUIRED_AI_QUESTIONS',JSON.stringify(questionResults));
  const callsBeforePrivacy=observedNetwork.filter(r=>r.path==='/api/answer'&&r.method==='POST').length;
  await evaluate('document.getElementById("ai-query").value="Synthetic Example lives at Example Street 12";document.getElementById("ai-query").dispatchEvent(new Event("input",{bubbles:true}));document.getElementById("ai-form").requestSubmit();true');
  if(!await evaluate('document.getElementById("answer-state").textContent==="Personvernfilter"&&document.getElementById("ai-query").value===""&&!document.getElementById("answer-content").textContent.includes("Synthetic Example")'))throw Error('Private synthetic input was not locally rejected safely');
  if(observedNetwork.filter(r=>r.path==='/api/answer'&&r.method==='POST').length!==callsBeforePrivacy)throw Error('Privacy-rejected question was sent to the backend');
  console.log('PRIVACY_REJECTION','passed; synthetic name/address were cleared locally without an API request');
  await evaluate('document.getElementById("query").value="familie";document.getElementById("search-form").requestSubmit();true');
  await wait('!document.getElementById("search-button").disabled && document.querySelector("#search-results .result-card")!==null');
  await wait('(()=>{const r=document.getElementById("search-area").getBoundingClientRect();return r.top>=-2&&r.top<innerHeight})()');
  if(!await evaluate('(()=>{const r=document.getElementById("search-area").getBoundingClientRect();return !document.getElementById("search-area").hidden&&document.getElementById("result-count").textContent.startsWith("0 treff")&&r.top>=-2&&r.top<innerHeight})()'))throw Error('A zero-result ordinary search did not show visible, in-view no-results feedback');
  await evaluate('document.getElementById("query").value="Bygge uten søknad";document.getElementById("query").focus();document.getElementById("query").dispatchEvent(new Event("input",{bubbles:true}));true');
  await send('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});
  await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});
  await wait('!document.getElementById("search-button").disabled && document.querySelector("#search-results .source-link")!==null');
  if(!await evaluate('document.querySelector("#search-results .source-link").href.includes("bygge-uten-a-soke")'))throw Error('Ordinary building search did not link to the approved source');
  if(!observedNetwork.some(r=>r.path==='/api/search'&&r.method==='POST'&&r.queryCase==='q5'&&r.status===200))throw Error('Ordinary Norwegian building search did not reach the backend');
  const callsBeforeSearchPrivacy=observedNetwork.filter(r=>r.path==='/api/search'&&r.method==='POST').length;
  await evaluate('document.getElementById("query").value="Kari Eksempel bor i Storgata 12";document.getElementById("search-form").requestSubmit();true');
  if(!await evaluate('document.getElementById("search-area").hidden===false&&document.getElementById("result-count").textContent==="Søket ble avvist"&&document.getElementById("query").value===""'))throw Error('Rejected ordinary search did not show visible, non-echoing feedback');
  if(observedNetwork.filter(r=>r.path==='/api/search'&&r.method==='POST').length!==callsBeforeSearchPrivacy)throw Error('Privacy-rejected ordinary search was sent to the backend');
  await typeInto('query','Hva gjelder teleportering?');await pressEnter();
  await wait('!document.getElementById("search-button").disabled&&document.querySelector("#search-results .official-menu-fallback a")?.href==="https://www.hamar.kommune.no/meny/"');
  const unsupportedSearch=observedNetwork.findLast(r=>r.path==='/api/search'&&r.method==='POST'&&r.queryCase==='unsupported');
  if(!unsupportedSearch||unsupportedSearch.status!==200)throw Error('Safe unsupported ordinary query did not return visible guidance and official municipal link '+JSON.stringify(unsupportedSearch));
  console.log('UNSUPPORTED_SEARCH_FALLBACK',JSON.stringify({http:unsupportedSearch.status,menu:await evaluate('document.querySelector("#search-results .official-menu-fallback a").href')}));
  await evaluate('document.getElementById("search-form").requestSubmit();true');
  await wait('!document.getElementById("search-button").disabled && document.getElementById("search-area").hidden===false');
 await send('Network.setBlockedURLs',{urls:[`*://127.0.0.1:${new URL(site).port}/api/search*`]});
 await evaluate('document.getElementById("query").value="gratis";document.getElementById("search-form").requestSubmit();true');
 await wait('!document.getElementById("search-button").disabled && document.getElementById("portal-status").textContent.startsWith("Kan ikke kontakte den lokale tjenesten.")');
 console.log('NETWORK_FAILURE_MESSAGE',await evaluate('document.getElementById("portal-status").textContent'));
 await send('Network.setBlockedURLs',{urls:[]});
 await evaluate('document.getElementById("query").value="miljo";document.getElementById("search-form").requestSubmit();true');
 await wait('!document.getElementById("search-button").disabled && document.querySelectorAll(".result-card").length>0');
 await evaluate('document.querySelector(\'[data-service="vann"]\').click();true');
 await wait('!document.getElementById("search-button").disabled');
 if(!await evaluate('document.querySelector("#answer-content pre, #download, #portal-download, .developer")===null && !/JSON/.test(document.getElementById("answer-content").innerText)'))throw Error('JSON or removed developer UI appeared after answering');
 for(const [name,width,height] of [['tablet',820,1180],['mobile',390,844]]){
  await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<500});
  await send('Page.navigate',{url:site});await wait('document.querySelectorAll(".category-card").length===8');
  await checkHeroLayout(name);
  fs.writeFileSync(folder+'/'+name+'-hero.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  await evaluate('document.querySelector("[data-service=vann]").click();true'); await wait('!document.getElementById("search-button").disabled'); if(!await evaluate('/^[1-9]/.test(document.getElementById("result-count").textContent)'))throw Error('Responsive search failed'); if(!await evaluate('document.documentElement.scrollWidth<=window.innerWidth'))throw Error('Horizontal overflow '+name); if(!await evaluate('document.querySelector("#ai-form").offsetWidth>0 && document.getElementById("ai-button").textContent==="Spør Aisha"'))throw Error('Independent Aisha form is unavailable at '+name+' viewport');
  fs.writeFileSync(folder+'/'+name+'.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  if(name==='mobile'){
   if(!await evaluate('!document.getElementById("about-project").open && !document.getElementById("about-service").open'))throw Error('Disclosures must remain closed by default on mobile');
   await evaluate('document.querySelector("#about-project summary").focus();true');await pressDisclosureEnter();
   await wait('document.getElementById("about-project").open');
   if(!await evaluate('document.querySelector("#about-project h2").checkVisibility() && document.documentElement.scrollWidth<=innerWidth'))throw Error('Mobile project disclosure overflows or is inaccessible');
   await evaluate('document.getElementById("about-project").scrollIntoView({block:"start",behavior:"instant"});true');
   await wait('(()=>{const r=document.getElementById("about-project").getBoundingClientRect();return r.top>=-2&&r.top<innerHeight})()');
   fs.writeFileSync(folder+'/mobile-project.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
   await pressDisclosureEnter();await wait('!document.getElementById("about-project").open');
   await wait('!document.getElementById("provider-model").disabled');
   await typeInto('ai-query','Hva kan jeg bygge uten å søke?');await pressEnter();
   await wait('!document.getElementById("ai-button").disabled && document.querySelector("#answer-content .answer-text")!==null');
   if(!await evaluate('window.__lastAnswer.answer_status==="evidence_checked" && window.__lastAnswer.result.provider==="ollama:llama3.2:3b" && document.querySelector("#answer-content .source-link").href.includes("bygge-uten-a-soke") && document.documentElement.scrollWidth<=innerWidth'))throw Error('Mobile AI answer or official citation failed');
   await evaluate('document.getElementById("ai-result").scrollIntoView({block:"start",behavior:"instant"})');await new Promise(r=>setTimeout(r,250));fs.writeFileSync(folder+'/mobile-ai.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
   console.log('MOBILE_AI','evidence_checked; official building citation visible');
  }
 }
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  if(javascriptExceptions.length||consoleErrors.length)throw Error('Browser console failures '+JSON.stringify({javascriptExceptions,consoleErrors}));
  console.log('BROWSER_CONSOLE',JSON.stringify({javascript_exceptions:javascriptExceptions,console_errors:consoleErrors}));
  console.log('HTTP_FAILURES',JSON.stringify(observedNetwork.filter(r=>r.status>=400)));
 console.log(JSON.stringify({title,service_searches:8,answer_claims:downloaded.result.claims.length,backend_exports:1,responsive:['desktop','tablet','mobile'],keyboard_focus:await evaluate('document.activeElement.tagName')}));ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
