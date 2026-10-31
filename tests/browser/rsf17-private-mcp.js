async (page) => {
 const assert={equal:(a,b)=>{if(a!==b)throw Error(JSON.stringify({expected:b,actual:a}))},ok:a=>{if(!a)throw Error('Assertion failed')},deepEqual:(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error(JSON.stringify({expected:b,actual:a}))}};
 const url='http://127.0.0.1:8180',pid='private-mcp-'+Date.now(),fixtures='/home/ra/Documents/Living-world-Ragnarok/ops/local/novice-mature-sprite-pipeline-e1/reference';
 await page.setViewportSize({width:1600,height:1100});
 const errors=[],failed=[],expectedErrors=[];
 let expectFailure=false;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error') (expectFailure?expectedErrors:errors).push(m.text())});
 page.on('requestfailed',r=>failed.push(r.url()+': '+r.failure()?.errorText));
 await page.addInitScript(()=>{window.__confirmations=[];window.confirm=message=>{window.__confirmations.push(message);return true;};});
 const text=id=>page.locator('#'+id).innerText();
 const wait=async fn=>{for(let n=0;n<100;n++){if(await fn())return;await page.waitForTimeout(100)}await page.screenshot({path:'/tmp/rsf17-timeout.png'});throw Error('Condition timeout')};
 const read=route=>page.evaluate(async route=>{const r=await fetch(route);if(!r.ok) throw Error(await r.text());return r.json()},route);
 const work=()=>read(`/api/projects/${pid}/workspace`);
 async function select(rid){
  const ids=await page.locator(`[data-node-id="${rid}"]`).evaluate(el=>{let x=el.parentElement,a=[];while(x){if(x.matches('.tree-node'))a.unshift(x.dataset.nodeId);x=x.parentElement}return a});
  for(const id of ids){const node=page.locator(`[data-node-id="${id}"]`);if(await node.locator(':scope > .tree-children').evaluate(el=>el.style.display==='none'))await node.locator(':scope > .tree-row > .tree-expander').click()}
  await page.locator(`[data-node-id="${rid}"] > .tree-row`).click();
  await wait(async()=> (await text('assignment-facts')).includes(rid));
 }
 await page.goto(url);
 await page.click('#new-project-btn'); await page.fill('#new-proj-id',pid); await page.fill('#new-proj-name','Browser synthetic Walk'); await page.click('#submit-new-proj-btn');
 await wait(async()=>await page.locator('#project-select').inputValue()===pid && (await text('proj-name'))==='Browser synthetic Walk');
 await page.click('#define-target-btn');await page.fill('#modal-frame-count','6');await page.fill('#modal-layers-input','body');await page.click('#submit-target-btn');
 await wait(async()=>{const t=await text('cnt-layers');if((await text('operation-status')).includes('Error'))console.log(await text('operation-status'));return /^48\b/.test(t)});
 await page.click('[data-filter="UNASSIGNED"]');
 let w=await work();assert.equal(w.requirements.layers.length,48);const ids=w.requirements.layers.map(l=>l.id);
 await select(ids[0]);
 const dl=page.waitForEvent('download');await page.click('#export-json-btn');const download=await dl;assert.ok((await download.suggestedFilename()).includes('.json'));
 await page.reload();await wait(async()=>{const t=await text('cnt-layers');if((await text('operation-status')).includes('Error'))console.log(await text('operation-status'));return /^48\b/.test(t)});
 await page.locator('summary').click();await page.fill('#resource-id','body');await page.setInputFiles('#resource-act',fixtures+'/novice_male_body.act');await page.setInputFiles('#resource-spr',fixtures+'/novice_male_body.spr');await page.click('#import-pair');
 await wait(async()=> (await text('operation-status')).includes('Exact resource bytes imported'));
 w=await work();assert.equal(w.resources[0].summary.frame_occurrences,456);assert.equal(w.resources[0].summary.action_slots,104);

 await select(ids[0]);await page.selectOption('#art-source',w.sources[0].source.id);await page.click('#assign-selected');
 await wait(async()=> (await text('operation-status')).includes('Mappings saved'));
 w=await work();const assignment=w.project.ledger.assignments[0];
 await page.click('[data-filter="ALL"]');await select(ids[1]);await page.selectOption('#reuse-assignment',assignment.id);await page.check('#reuse-mirror');await page.click('#assign-reuse');
 await wait(async()=> (await work()).project.ledger.assignments.length===2);
 await page.selectOption('#preview-resource','body');await page.selectOption('#play-action','1');await wait(async()=> (await text('current-frame')).includes('Frame 0 / 7'));
 await page.fill('#movement-speed','150');await page.locator('#play-frame').fill('3');await wait(async()=> (await text('current-frame')).includes('Frame 3 / 7'));
 const firstResponse=page.waitForResponse(r=>r.url().endsWith('/preview')&&r.request().postDataJSON()?.resume_frame===3);
 await page.click('#play');const first=await (await firstResponse).json();await page.click('#pause');assert.equal(first.report.selection.frame,3);
 await page.selectOption('#play-speed','2');const selected=Number(await page.locator('#play-frame').inputValue());
 const resumedResponse=page.waitForResponse(r=>r.url().endsWith('/preview')&&r.request().postDataJSON()?.resume_frame===selected&&r.request().postDataJSON()?.speed===2);
 await page.click('#play');const resumed=await(await resumedResponse).json();await page.click('#pause');assert.equal(resumed.report.selection.frame,selected);
 await page.selectOption('#play-action','5');await page.fill('#duration-ms','1000');await page.locator('#play-frame').fill('4');await wait(async()=> (await text('current-frame')).includes('Frame 4 / 4'));await page.click('#play');await page.waitForTimeout(300);await page.click('#pause');assert.equal(Number(await page.locator('#play-frame').inputValue()),4);
 const final=await work();assert.equal(final.project.ledger.assignments.length,2);assert.ok(final.project.ledger.assignments.every(a=>a.review===null));
 await page.reload();await wait(async()=>/^48\b/.test(await text('cnt-layers')));
 assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
 return {result:'PRIVATE_UI_IMPORT_AND_QA_PHASE_PASS',project:pid,summary:final.resources[0].summary,hashes:{act:final.project.resources[0].act,spr:final.project.resources[0].spr},assignments:2,approvals:0,first_play_frame:first.report.selection.frame,speed_resume_frame:resumed.report.selection.frame,terminal_frame:4,console_errors:errors,network_failures:failed};
}