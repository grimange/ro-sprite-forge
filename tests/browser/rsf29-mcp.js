async (page) => {
  const root='/home/ra/Documents/ro-sprite-forge', evidence=root+'/docs/verification/rsf-29';
  const pid='rsf29-browser-'+Date.now(), base='/api/projects/'+pid;
  const stable=v=>Array.isArray(v)?v.map(stable):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])])):v;
  const eq=(a,b)=>{if(JSON.stringify(stable(a))!==JSON.stringify(stable(b)))throw Error(JSON.stringify({expected:b,actual:a}));};
  const ok=a=>{if(!a)throw Error('Assertion failed');};
  const errors=[], failures=[], expectedErrors=[];let expecting=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')(expecting?expectedErrors:errors).push(m.text());});
  page.on('requestfailed',r=>failures.push(r.url()+': '+r.failure()?.errorText));
  const wait=async fn=>{for(let i=0;i<150;i++){if(await fn())return;await page.waitForTimeout(100);}throw Error('Condition timeout');};
  const text=id=>page.locator('#'+id).innerText();
  const call=async (route,data,method='POST')=>page.evaluate(async ({route,data,method})=>{
    const csrf=await (await fetch('/api/csrf-token')).json();
    const r=await fetch(route,data===undefined?{}:{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf.csrf_token},body:JSON.stringify(data)});
    const value=await r.json();return {status:r.status,value};
  },{route,data,method});
  const read=async suffix=>{const r=await call(base+suffix);eq(r.status,200);return r.value;};
  await page.setViewportSize({width:1500,height:1100});await page.goto('http://127.0.0.1:8193');
  await page.click('#new-project-btn');await page.fill('#new-proj-id',pid);await page.fill('#new-proj-name','RSF-29 synthetic operator video workflow');
  await page.click('#submit-new-proj-btn');await wait(async()=>await page.locator('#project-select').inputValue()===pid);
  await page.locator('#video-import-details > summary').click();await wait(async()=>(await text('video-capability')).includes('available.'));
  await page.setInputFiles('#video-file',root+'/docs/verification/rsf-28/synthetic/fixtures/vfr.mkv');
  await page.click('#video-inspect');await wait(async()=>(await text('video-status')).startsWith('Metadata inspected'));
  const meta=JSON.parse(await text('video-metadata'));
  eq(meta.source.sha256,'51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d');
  eq(await page.locator('#video-stream').inputValue(),'0');eq(meta.streams[0].time_base,{numerator:'1',denominator:'1000'});
  await page.click('#video-scan');await wait(async()=>(await text('video-status')).startsWith('Actual presentation frames'));
  eq(await page.locator('#video-frames button').count(),5);
  const labels=await page.locator('#video-frames button').allTextContents();for(const p of [0,40,120,160,300])ok(labels.some(l=>l.includes('PTS '+p+' ')));
  await page.selectOption('#video-mode','pts');
  // Keyboard-operable selection preserves the explicit nonchronological order.
  await page.locator('#video-frames button').nth(4).focus();await page.keyboard.press('Enter');
  await page.locator('#video-frames button').nth(0).click();await page.locator('#video-frames button').nth(2).click();
  eq(await page.locator('#video-values').inputValue(),'300, 0, 120');
  const before=await read('');
  await page.click('#video-preview');await wait(async()=>(await text('video-status')).startsWith('Preview '));
  const previewSha=(await text('video-status')).split(' ')[1].replace('.','');
  eq(previewSha,'8f92a9dfd224fdf3275a835caa14a8e04f5b03bf367d026520c28e2aa55a44e3');
  eq(await read(''),before);eq(await page.locator('#video-candidates img').count(),3);
  const pixelHashes=await page.locator('#video-candidates img').evaluateAll(async images=>{
    const out=[];for(const image of images){await image.decode();const c=document.createElement('canvas');c.width=image.naturalWidth;c.height=image.naturalHeight;const x=c.getContext('2d');x.drawImage(image,0,0);const rgba=x.getImageData(0,0,c.width,c.height).data;const sha=await crypto.subtle.digest('SHA-256',rgba);out.push([...new Uint8Array(sha)].map(n=>n.toString(16).padStart(2,'0')).join(''));}return out;
  });
  eq(pixelHashes,['f8630b2a2e8ecb0f293bbd525fad3d6961c8b33c50a098e85568997bb5409c6f','adf63562c07856fcfc2564a135d54d4de89c0ef0136f6c6fc197611515874631','4de13be716c171641092c025d6821c7ffe597e95c207e95a055c11838a0bc94f']);
  await page.locator('#video-candidates').screenshot({path:evidence+'/browser-vfr-preview.png'});
  await page.getByRole('button',{name:'Move earlier candidate 2',exact:true}).click();
  eq(await page.locator('#video-values').inputValue(),'300, 120, 0');ok(await page.locator('#video-stage').isDisabled());
  await page.click('#video-preview');await wait(async()=>(await text('video-status')).startsWith('Preview '));
  const reorderedSha=(await text('video-status')).split(' ')[1].replace('.','');ok(reorderedSha!==previewSha);
  await page.click('#video-stage');await wait(async()=>(await text('video-status')).startsWith('Staged collection'));
  let committed=await read('');eq(committed.video_imports[0].items.map(i=>i.pts),[300,120,0]);eq(committed.video_imports[0].items.map(i=>i.ordinal),[4,2,0]);
  eq(committed.video_imports[0].canonical_sha256,reorderedSha);eq(committed.ledger?.assignments||[],[]);eq(committed.reviews,{});
  // Confirming the same collection is idempotent at the current revision.
  await page.click('#video-stage');await wait(async()=>(await text('video-status')).startsWith('Staged collection'));eq(await read(''),committed);
  await page.reload();await wait(async()=>await page.locator('#project-select').inputValue()===pid);
  await page.locator('#video-import-details > summary').click();await page.getByText('Committed video candidate provenance',{exact:true}).click();await wait(async()=>(await text('video-history')).includes(reorderedSha));
  eq((await read('')).video_imports,committed.video_imports);
  const workspace=await read('/workspace');eq(workspace.sources.filter(s=>s.source.sha256&&committed.video_imports[0].items.some(i=>i.png_sha256===s.source.sha256)).length,3);
  // Inspect a previously staged video without re-uploading it.
  await page.selectOption('#video-staged',meta.source.sha256);await page.click('#video-inspect');await wait(async()=>(await text('video-status')).startsWith('Metadata inspected'));
  await page.selectOption('#video-mode','pts');await page.fill('#video-values','41');expecting=true;await page.click('#video-preview');await wait(async()=>(await text('video-status')).includes('VIDEO_SELECTION_NOT_EXACT'));expecting=false;eq(await read(''),committed);
  await page.selectOption('#video-mode','ordinal');await page.fill('#video-values','5');expecting=true;await page.click('#video-preview');await wait(async()=>(await text('video-status')).includes('VIDEO_SELECTION_NOT_EXACT'));expecting=false;eq(await read(''),committed);
  await page.selectOption('#video-mode','pts');await page.fill('#video-values','9007199254740993');await page.click('#video-preview');await wait(async()=>(await text('video-status')).includes('VIDEO_SELECTION_INTEGER_OUT_OF_RANGE'));ok((await text('video-status')).includes('9007199254740993'));eq(await read(''),committed);
  // Unsupported stream is independently rejected by the real HTTP adapter.
  expecting=true;let bad=await call(base+'/video-frames',{expected_revision:committed.revision,source_sha256:meta.source.sha256,expected_sha256:meta.source.sha256,stream_index:'99'});expecting=false;eq(bad.status,422);ok(JSON.stringify(bad.value).includes('VIDEO_INVALID_STREAM'));
  // A second writer advances the revision; the open page must not silently stage against it.
  const save=await call(base,{expected_revision:committed.revision,project:committed},'PUT');eq(save.status,200);
  await page.fill('#video-values','0');expecting=true;await page.click('#video-preview');await wait(async()=>(await text('video-status')).includes('VIDEO_STALE_PROJECT_REVISION'));expecting=false;
  const result={pid,browser:page.context().browser().version(),video_sha256:meta.source.sha256,previewSha,reorderedSha,pixelHashes,journeys:['A metadata and stream','B exact VFR 300/0/120, keyboard, independent RGBA hashes','C operator reorder 300/120/0','D preview unchanged, explicit immutable stage, idempotency, reopen','F missing PTS, invalid ordinal, unsupported large PTS, unsupported stream, stale revision'],errors,failures,expectedErrors};
  eq(errors,[]);eq(failures,[]);
  return result;
}
