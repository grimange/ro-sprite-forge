async (page) => {
 const assert={equal:(a,b)=>{if(a!==b)throw Error(JSON.stringify({expected:b,actual:a}))},ok:a=>{if(!a)throw Error('Assertion failed')},deepEqual:(a,b)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw Error(JSON.stringify({expected:b,actual:a}))}};
 const url='http://127.0.0.1:8182',pid='rsf18-'+Date.now(),fixtures='/tmp/rsf17-synthetic';
 await page.setViewportSize({width:1600,height:1100});
 const errors=[],failed=[],expectedErrors=[];
 let expectFailure=false;
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',m=>{if(m.type()==='error') (expectFailure?expectedErrors:errors).push(m.text())});
 page.on('requestfailed',r=>failed.push(r.url()+': '+r.failure()?.errorText));
 await page.addInitScript(()=>{window.__confirmations=[];window.confirm=message=>{window.__confirmations.push(message);return true;};});
 const text=id=>page.locator('#'+id).innerText();
 const wait=async fn=>{for(let n=0;n<100;n++){if(await fn())return;await page.waitForTimeout(100)}await page.screenshot({path:'/tmp/rsf18-timeout.png'});throw Error('Condition timeout')};
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
 await page.locator('summary').click();await page.fill('#resource-id','body');await page.setInputFiles('#resource-act',fixtures+'/body.act');await page.setInputFiles('#resource-spr',fixtures+'/body.spr');await page.click('#import-pair');
 await wait(async()=> (await text('operation-status')).includes('Exact resource bytes imported'));
 w=await work();assert.equal(w.resources[0].summary.frame_occurrences,240);assert.equal(w.sources.length,2);
 await select(ids[0]);await page.selectOption('#art-source',w.sources[0].source.id);await wait(()=>page.locator('#source-thumbnail').isVisible());await page.click('#assign-selected');
 await wait(async()=> (await work()).project.ledger?.assignments.length===1);
 await wait(async()=> (await text('operation-status')).includes('Mappings saved'));
 await page.click('[data-filter="ALL"]');
 await select(ids[1]);await page.selectOption('#art-source',w.sources[1].source.id);await page.click('#add-batch');
 await select(ids[2]);await page.selectOption('#art-source',w.sources[0].source.id);await page.click('#add-batch');await page.click('#assign-batch');
 await wait(async()=> (await work()).project.ledger.assignments.length===3);
 await wait(async()=> (await text('operation-status')).includes('Mappings saved'));
 w=await work();let a=w.project.ledger.assignments.find(a=>a.requirement_id===ids[0]);
 await select(ids[3]);await page.selectOption('#reuse-assignment',a.id);await page.check('#reuse-mirror');await page.click('#assign-reuse');
 await wait(async()=> (await work()).project.ledger.assignments.length===4);
 await wait(async()=> (await text('operation-status')).includes('Mappings saved'));
 await select(ids[3]);await wait(()=>page.locator('#reuse-after').isVisible());
 w=await work();assert.equal(w.project.ledger.assignments.filter(a=>a.kind==='DIRECT_SOURCE').length,3);assert.equal(w.project.ledger.assignments.filter(a=>a.kind==='EXPLICIT_REUSE').length,1);assert.ok(w.project.ledger.assignments.every(a=>a.review===null));assert.equal(ids.length-w.project.ledger.assignments.length,44);
 const ledger=JSON.stringify(w.project.ledger);
 await page.click('#save-project-btn');await wait(async()=> (await text('operation-status')).includes('Saved project revision'));
 await page.reload();await wait(async()=>{const t=await text('cnt-layers');if((await text('operation-status')).includes('Error'))console.log(await text('operation-status'));return /^48\b/.test(t)});assert.equal(JSON.stringify((await work()).project.ledger),ledger);
 await page.selectOption('#preview-resource','body');await page.selectOption('#play-action','1');await wait(async()=> (await text('current-frame')).includes('Frame 0 / 5'));
 await page.click('#next-frame');await wait(async()=> (await text('current-frame')).includes('Frame 1 / 5'));
 await page.click('#previous-frame');await wait(async()=> (await text('current-frame')).includes('Frame 0 / 5'));
 await page.locator('#play-frame').fill('3');await wait(async()=> (await text('current-frame')).includes('Frame 3 / 5'));
 await page.click('#play');await wait(async()=> (await text('operation-status')).includes('Timing unresolved'));
 await page.fill('#movement-speed','150');await page.selectOption('#play-speed','2');await page.click('#play');await page.waitForTimeout(450);await page.click('#pause');const paused=await text('current-frame');await page.waitForTimeout(250);assert.equal(await text('current-frame'),paused);assert.equal(JSON.parse(await text('timing-facts')).timing_status,'SUPPORTED');
 await page.click('#stop');await wait(async()=> (await text('current-frame')).includes('Frame 0 / 5'));
 await page.selectOption('#play-view','15');await wait(async()=> (await text('current-frame')).includes('slot 15 · view 7'));
 await page.selectOption('#play-action','2');await wait(async()=> (await text('current-frame')).includes('slot 23'));
 await page.selectOption('#play-action','1');await wait(async()=> (await text('current-frame')).includes('slot 15'));
 // Expected errors are explicitly separated from unexpected browser exceptions.
 expectFailure=true;await page.click('#compare-selected');await wait(async()=> (await text('operation-status')).includes('CANDIDATE_NOT_SELECTED'));expectFailure=false;
 await page.selectOption('#candidate-resource','body');await page.click('#compare-selected');await wait(()=>page.locator('#comparison-preview').isVisible());assert.ok((await text('comparison-facts')).includes('PARTIAL'));
 await page.selectOption('#compare-mode','DIFFERENCE');await page.click('#compare-selected');await wait(async()=> (await text('comparison-facts')).includes('DIFFERENCE'));
 // A second browser window saves first; the stale first window cannot overwrite it.
 const second=await page.context().newPage();await second.goto(url);await second.selectOption('#project-select',pid);await second.waitForTimeout(300);await second.click('#save-project-btn');await second.waitForFunction(()=>document.querySelector('#operation-status').textContent.includes('Saved project revision'));
 expectFailure=true;await page.click('#save-project-btn');await wait(async()=> (await text('operation-status')).toLowerCase().includes('conflict'));expectFailure=false;await second.close();
 await page.reload();await wait(async()=>{const t=await text('cnt-layers');if((await text('operation-status')).includes('Error'))console.log(await text('operation-status'));return /^48\b/.test(t)});
 // Keyboard navigation uses focusable requirement tree rows.
 await select(ids[0]);await page.locator(`[data-node-id="${ids[0]}"] > .tree-row`).focus();await page.keyboard.press('Enter');assert.ok((await text('assignment-facts')).includes(ids[0]));
 // RSF-18: explicit synthetic operator decisions through real workbench controls.
 const count=async state=>(await work()).reviews.counts[state];
 async function decide(selection,decision='APPROVED') {
   await select(selection[0]);await page.selectOption('#review-scope',selection.length===1?'layer':'batch');
   if(selection.length>1)await page.fill('#review-batch',JSON.stringify(selection));
   await page.click('#prepare-review');await page.waitForSelector('#review-dialog[open]');
   const proposal=JSON.parse(await text('review-proposal'));
   assert.deepEqual(proposal.members.map(m=>m.requirement_id),[...selection].sort());
   assert.ok((await text('review-images')).includes('PARTIAL'));
   assert.equal(await page.locator('#review-images img').count(),selection.length);
   await page.click(decision==='APPROVED'?'#approve-review':'#reject-review');
   await page.waitForSelector('#review-dialog[open]',{state:'hidden'});
   await wait(async()=> (await text('operation-status')).includes('Recorded '+decision));
   return proposal;
 }
 await decide([ids[0]]);assert.equal(await count('APPROVED'),1);
 let event=(await work()).project.review_events[0];assert.equal(event.provenance,'EXPLICIT_SINGLE_OPERATOR_WORKBENCH_ACTION');
 await page.reload();await wait(async()=>/^48\b/.test(await text('cnt-layers')));assert.equal(await count('APPROVED'),1);
 await decide([ids[1]],'REJECTED');assert.equal(await count('REJECTED'),1);
 assert.ok((await work()).coverage.occurrences.find(o=>o.requirement_id===ids[1]).issues.includes('REVIEW_REJECTED'));
 async function direct(n,src) {await select(ids[n]);await page.selectOption('#art-source',src);await page.click('#assign-selected');await wait(async()=>(await text('operation-status')).includes('Mappings saved'));}
 async function reuse(n,parent) {const ws=await work();const a=ws.project.ledger.assignments.find(a=>a.requirement_id===ids[parent]);await select(ids[n]);await page.selectOption('#reuse-assignment',a.id);await page.check('#reuse-mirror');await page.click('#assign-reuse');await wait(async()=>(await text('operation-status')).includes('Mappings saved'));}
 w=await work();await direct(3,w.sources[1].source.id);await reuse(1,0);await reuse(2,1);
 await decide(ids.slice(0,4));assert.equal(await count('APPROVED'),4);assert.equal(await count('REJECTED'),0);
 const dBasis=(await work()).reviews.occurrences.find(r=>r.requirement_id===ids[3]).basis_sha256;
 await direct(0,w.sources[1].source.id);
 w=await work();assert.deepEqual(ids.slice(0,4).map(id=>w.reviews.occurrences.find(r=>r.requirement_id===id).state),['STALE','STALE','STALE','APPROVED']);
 assert.equal(w.reviews.occurrences.find(r=>r.requirement_id===ids[3]).basis_sha256,dBasis);
 assert.equal(w.coverage.counts.review.stale,3);assert.equal(w.coverage.status.export_ready,false);
 await page.reload();await wait(async()=>/^48\b/.test(await text('cnt-layers')));assert.equal(await count('STALE'),3);
 // Separate browser context changes the project while an old proposal is displayed.
 await select(ids[3]);await page.selectOption('#review-scope','layer');await page.click('#prepare-review');await page.waitForSelector('#review-dialog[open]');
 const context=await page.context().browser().newContext();const other=await context.newPage();await other.goto(url);await other.selectOption('#project-select',pid);await other.waitForTimeout(500);await other.click('#save-project-btn');await other.waitForFunction(()=>document.querySelector('#operation-status').textContent.includes('Saved project revision'));
 const newest=(await work()).project.revision;
 expectFailure=true;await page.click('#approve-review');await wait(async()=>(await text('operation-status')).toLowerCase().includes('conflict'));expectFailure=false;
 assert.equal((await work()).project.revision,newest);await page.click('#cancel-review');await context.close();
 await page.reload();await wait(async()=>/^48\b/.test(await text('cnt-layers')));
 // Structurally valid unexecuted translation remains visible and cannot be approved.
 w=await work();await select(ids[4]);await page.fill('#batch-mappings',JSON.stringify([{requirement_id:ids[4],kind:'DIRECT_SOURCE',source:w.sources[0].source.id,source_revision:1,recipe:[{id:'offset',op:'translate',version:1,parameters:{x:2,y:0}}]}]));await page.click('#assign-batch');await wait(async()=>(await text('operation-status')).includes('Mappings saved'));
 await select(ids[4]);await page.selectOption('#review-scope','layer');await page.click('#prepare-review');await page.waitForSelector('#review-dialog[open]');assert.equal(await page.locator('#approve-review').isDisabled(),true);assert.ok((await text('review-images')).includes('NOT_EXECUTED'));assert.equal(await page.locator('#review-images img').count(),0);await page.click('#cancel-review');
 await select(ids[0]);await page.screenshot({path:'/home/ra/Documents/ro-sprite-forge/docs/evidence/rsf18/synthetic-review-workbench.png'});
 assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
 return {result:'RSF18_BROWSER_E2E_PASS',browser:page.context().browser().version(),project:pid,journeys:['RSF17 baseline/assign/reuse/playback/comparison','individual approval/reopen','rejection','explicit batch scope','A-B-C invalidation/D preservation','isolated-context stale submission','unexecuted transform blocked'],resource_spr:(await work()).project.resources[0].spr,requirement_ids:ids,review_counts:(await work()).reviews.counts,console_errors:errors,expected_error_responses:expectedErrors,network_failures:failed};
}
