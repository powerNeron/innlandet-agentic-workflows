
const fs=require('fs');
(async()=>{
 const [port,site,folder]=process.argv.slice(2);
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
 ws.onmessage=e=>{const d=JSON.parse(e.data);if(pending.has(d.id)){const p=pending.get(d.id);pending.delete(d.id);d.error?p.reject(Error(JSON.stringify(d.error))):p.resolve(d.result);return}if(d.method==='Runtime.exceptionThrown')javascriptExceptions.push(d.params.exceptionDetails.text||d.params.exceptionDetails.exception?.description||'JavaScript exception');if(d.method==='Log.entryAdded'&&d.params.entry.level==='error')consoleErrors.push(d.params.entry.text);if(d.method==='Network.requestWillBeSent'){const req=d.params.request,path=new URL(req.url).pathname,row={path,method:req.method,status:null,queryCase:null};if((path==='/api/search'||path==='/api/answer')&&req.method==='POST'&&req.postData){try{row.queryCase=queryCases.get(JSON.parse(req.postData).query)||null}catch{}}observedNetwork.push(row)}if(d.method==='Network.responseReceived'){const row=observedNetwork.findLast(x=>x.path===new URL(d.params.response.url).pathname&&x.status===null);if(row)row.status=d.params.response.status}};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const id=next++;pending.set(id,{resolve,reject});ws.send(JSON.stringify({id,method,params}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);reject(Error(method))}},5000)});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 const typeInto=async(id,value)=>{const quoted=JSON.stringify(id);await evaluate('(()=>{const e=document.getElementById('+quoted+');e.focus();e.value="";e.dispatchEvent(new Event("input",{bubbles:true}));return true})()');await send('Input.insertText',{text:value})};
 const pressEnter=async()=>{await send('Input.dispatchKeyEvent',{type:'rawKeyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,nativeVirtualKeyCode:13})};
 const wait=async expression=>{for(let i=0;i<300;i++){if(await evaluate(expression))return;await new Promise(r=>setTimeout(r,100))}throw Error('Condition failed '+expression+' STATE '+JSON.stringify(await evaluate('({portal:document.getElementById("portal-status").textContent,count:document.getElementById("result-count").textContent,status:document.getElementById("status").textContent,answerArticles:document.querySelectorAll("#answer-content article").length,answerSourceLinks:document.querySelectorAll("#answer-content .source-link").length,answerData:(()=>{try{const x=JSON.parse(document.querySelector("#answer-content pre")?.textContent||"null");return {status:x?.answer_status,claims:x?.result?.claims?.length,findings:x?.result?.verification?.findings?.length,citations:x?.citations?.length}}catch{return null}})()})')))};
 await send('Page.enable');await send('Runtime.enable');await send('Log.enable');await send('Network.enable');
 await send('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:folder});
 await send('Emulation.setDeviceMetricsOverride',{width:1440,height:1100,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:site});await wait('document.querySelectorAll(".category-card").length===8');
 if(await evaluate('document.querySelector(".developer").open'))throw Error('Manual source-selection panel should be optional and collapsed by default');
 await wait('!document.getElementById("provider-model").disabled');
 const providerState=await evaluate('(()=>{const s=document.getElementById("provider-model");return {selected:s.value,label:s.selectedOptions[0]?.textContent,openai:[...s.options].filter(o=>o.value.startsWith("openai|")).map(o=>({disabled:o.disabled,label:o.textContent}))}})()');
 if(providerState.selected!=='ollama|llama3.2:3b'||!providerState.openai.length||providerState.openai.some(o=>!o.disabled))throw Error('Provider selector does not reflect the installed local model and disabled OpenAI state '+JSON.stringify(providerState));
 console.log('PROVIDER_SELECTOR',JSON.stringify(providerState));
 const image=await evaluate('(async()=>{const i=new Image();i.src="/hamar-background.png";await i.decode();return {width:i.naturalWidth,height:i.naturalHeight,active:document.body.classList.contains("has-scenic-image"),css:getComputedStyle(document.querySelector(".landscape")).backgroundImage}})()');
 if(!image.active||image.width<1||!image.css.includes('hamar-background.png'))throw Error('Photo not active');
 console.log('BACKGROUND_IMAGE',JSON.stringify(image));
 const title=await evaluate('document.title');if(title!=='Informasjon Agent for Hamar')throw Error(title);
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
 if(!await evaluate('document.querySelector("#answer-content .answer-text")!==null && document.querySelector("#answer-content .source-excerpt blockquote")!==null && document.querySelector("#answer-content .technical-details").open===false && document.querySelectorAll("#answer-content .citation-card .source-link").length===1'))throw Error('Answer, source excerpt, collapsed technical detail or deduplicated citation presentation is incorrect');
 const sfoLink=await evaluate('document.querySelector("#answer-content .source-link").href');
 if(!sfoLink.startsWith('https://www.hamar.kommune.no/'))throw Error('SFO answer has no official source link');
 await evaluate('document.getElementById("ai-result").scrollIntoView({block:"start",behavior:"instant"})');
 await new Promise(r=>setTimeout(r,250));
 fs.writeFileSync(folder+'/desktop-answer.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
 await evaluate('document.getElementById("portal-download").click();true');
 for(let i=0;i<60&&!fs.existsSync(folder+'/hamar-kildebasert-svar.json');i++)await new Promise(r=>setTimeout(r,100));
 const downloaded=JSON.parse(fs.readFileSync(folder+'/hamar-kildebasert-svar.json','utf8'));
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
 await wait('document.querySelector("#answer-content .technical-details pre")!==null');
 if(!await evaluate('document.querySelector("#answer-content").textContent.includes("Oppfølgingsspørsmål:") && document.querySelector("#answer-content .technical-details pre").textContent.includes("is_follow_up")'))throw Error('Follow-up provenance was not visible');
 const answerBeforeOrdinary=await evaluate('document.querySelector("#answer-content .answer-text")?.textContent||document.querySelector("#answer-content .empty-answer")?.textContent||""');
 console.log('CONTEXTUAL_FOLLOWUP',JSON.stringify({http:contextualFollowup.status,sfoAnswer,followupVisible:Boolean(answerBeforeOrdinary)}));
 await evaluate('document.getElementById("query").value="byggesak";document.getElementById("search-form").requestSubmit();true');
 await wait('!document.getElementById("search-button").disabled && document.querySelectorAll("#search-results .result-card").length>0');
 if(await evaluate('document.querySelector("#answer-content .answer-text")?.textContent||document.querySelector("#answer-content .empty-answer")?.textContent||""')!==answerBeforeOrdinary)throw Error('Ordinary search contaminated the independent AI answer');
 await evaluate('document.getElementById("reset-conversation").click();true');
 await wait('document.getElementById("answer-state").textContent==="Samtalen er nullstilt"');
 if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download").hidden'))throw Error('Conversation reset left a stale answer or downloadable result');
 await typeInto('ai-query','hva med priser?');await pressEnter();
 for(let i=0;i<100&&!observedNetwork.findLast(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup');i++)await new Promise(r=>setTimeout(r,50));
 await wait('!document.getElementById("ai-button").disabled && document.getElementById("answer-state").textContent==="Kan du presisere spørsmålet?"');
 const afterReset=observedNetwork.findLast(r=>r.path==='/api/answer'&&r.method==='POST'&&r.queryCase==='followup');
 const afterResetData=await evaluate('JSON.parse(document.querySelector("#answer-content .technical-details pre").textContent)');
 if(!afterReset||afterReset.status!==200||afterResetData.answer_status!=='clarification_required'||afterResetData.is_follow_up||!await evaluate('document.querySelector("#answer-content .official-menu-fallback a")?.href==="https://www.hamar.kommune.no/meny/"'))throw Error('Safe ambiguous question after reset did not request clarification without prior context '+JSON.stringify({afterReset,answer:afterResetData}));
 console.log('RESET_CONTEXT_ISOLATION',JSON.stringify({http:afterReset.status,status:afterResetData.answer_status,is_follow_up:afterResetData.is_follow_up,menu:afterResetData.official_menu_url}));
  await evaluate('document.getElementById("ai-query").value="Hva gjelder for byggesak?";document.getElementById("ai-query").dispatchEvent(new Event("input",{bubbles:true}));true');
  if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download").hidden'))throw Error('Old answer remained visible when a new AI question was entered');
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
  if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download").hidden'))throw Error('Unsupported question produced a stale or downloadable answer');
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
   if(!await evaluate('document.querySelectorAll("#answer-content .answer-text").length===0 && document.getElementById("portal-download").hidden'))throw Error('A previous answer remained visible for a new question '+query);
   await pressEnter();
   await wait('!document.getElementById("ai-button").disabled && document.querySelector("#answer-content .technical-details pre")!==null');
   await wait('(()=>{const r=document.getElementById("ai-result").getBoundingClientRect();return r.top>=-2&&r.top<innerHeight})()');
   const state=await evaluate('(()=>{const a=JSON.parse(document.querySelector("#answer-content .technical-details pre").textContent);const r=document.getElementById("ai-result").getBoundingClientRect();return {status:a.answer_status,provider:a.result?.provider||null,claims:a.result?.claims?.length||0,citations:a.citations.map(c=>c.source_id),citation_records:a.citations.length,links:[...document.querySelectorAll("#answer-content .source-link")].map(x=>x.href),visible:r.top>=-2&&r.top<innerHeight}})()');
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
 await evaluate('document.querySelector(".developer").open=true;document.getElementById("source").value="hamar-drikkevann";document.getElementById("run").click();true');
 await wait('!document.getElementById("result").hidden && document.querySelectorAll("#claims article").length>0');
 await evaluate('document.getElementById("download").click();true');
 for(let i=0;i<60&&!fs.existsSync(folder+'/hamar-result.json');i++)await new Promise(r=>setTimeout(r,100));
 if(JSON.parse(fs.readFileSync(folder+'/hamar-result.json','utf8')).source.id!=='hamar-drikkevann')throw Error('Source selection failed');
 if(/linda|jesper|guttormsen|svela/i.test(fs.readFileSync(folder+'/hamar-result.json','utf8')))throw Error('Student names leaked into workflow JSON');
 for(const [name,width,height] of [['tablet',820,1180],['mobile',390,844]]){
  await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:width<500});
  await send('Page.navigate',{url:site});await wait('document.querySelectorAll(".category-card").length===8');
  await evaluate('document.querySelector("[data-service=vann]").click();true'); await wait('!document.getElementById("search-button").disabled'); if(!await evaluate('/^[1-9]/.test(document.getElementById("result-count").textContent)'))throw Error('Responsive search failed'); if(!await evaluate('document.documentElement.scrollWidth<=window.innerWidth'))throw Error('Horizontal overflow '+name); if(!await evaluate('document.querySelector("#ai-form").offsetWidth>0 && document.getElementById("ai-button").textContent.includes("Spør AI-agenten")'))throw Error('Independent AI form is unavailable at '+name+' viewport');
  fs.writeFileSync(folder+'/'+name+'.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));
  if(name==='mobile'){await evaluate('document.getElementById("ai-form").scrollIntoView({block:"start",behavior:"instant"})');await new Promise(r=>setTimeout(r,250));fs.writeFileSync(folder+'/mobile-ai.png',Buffer.from((await send('Page.captureScreenshot',{format:'png'})).data,'base64'));}
 }
 await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
 await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});
  if(javascriptExceptions.length)throw Error('Browser JavaScript exceptions '+JSON.stringify(javascriptExceptions));
  console.log('BROWSER_CONSOLE',JSON.stringify({javascript_exceptions:javascriptExceptions,console_errors:consoleErrors}));
  console.log('HTTP_FAILURES',JSON.stringify(observedNetwork.filter(r=>r.status>=400)));
 console.log(JSON.stringify({title,service_searches:8,answer_claims:downloaded.result.claims.length,downloads:2,responsive:['desktop','tablet','mobile'],keyboard_focus:await evaluate('document.activeElement.tagName')}));ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
