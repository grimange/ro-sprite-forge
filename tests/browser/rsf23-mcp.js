async (page) => {
  const assert = {
    equal: (a, b) => { if (a !== b) throw Error(JSON.stringify({ expected: b, actual: a })); },
    notEqual: (a, b) => { if (a === b) throw Error(JSON.stringify({ unexpected: b, actual: a })); },
    ok: a => { if (!a) throw Error('Assertion failed'); },
    deepEqual: (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(JSON.stringify({ expected: b, actual: a })); },
  };
  const url = 'http://127.0.0.1:8182', pid = 'rsf23-' + Date.now();
  await page.setViewportSize({ width: 1600, height: 1100 });
  const errors = [], failed = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('requestfailed', r => failed.push(r.url() + ': ' + r.failure()?.errorText));

  const text = id => page.locator('#' + id).innerText();
  const wait = async fn => {
    for (let n = 0; n < 100; n++) {
      if (await fn()) return;
      await page.waitForTimeout(100);
    }
    throw Error('Condition timeout');
  };
  const read = route => page.evaluate(async route => {
    const r = await fetch(route);
    if (!r.ok) throw Error(await r.text());
    return r.json();
  }, route);
  const post = (route, data) => page.evaluate(async ({ route, data }) => {
    const csrfRes = await fetch('/api/csrf-token');
    const csrfData = await csrfRes.json();
    const r = await fetch(route, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfData.csrf_token,
      },
      body: JSON.stringify(data),
    });
    if (!r.ok) throw Error(await r.text());
    return r.json();
  }, { route, data });

  console.log('Journey 1: Create project and initialize workbench');
  await page.goto(url);
  await page.click('#new-project-btn');
  await page.fill('#new-proj-id', pid);
  await page.fill('#new-proj-name', 'RSF-23 Browser Compiler Test');
  await page.selectOption('#new-proj-actor', 'monster');
  await page.selectOption('#new-proj-profile', 'monster');
  await page.click('#submit-new-proj-btn');
  await wait(async () => await page.locator('#project-select').inputValue() === pid);

  console.log('Journey 2: Import synthetic resource pair via API');
  // Small valid ACT 2.4 and SPR 2.1 in base64
  const pal = new Uint8Array(1024);
  pal[4] = 255; pal[7] = 255; // index 1: red
  const sprHeader = new Uint8Array([0x53, 0x50, 0x01, 0x02, 0x01, 0x00, 0x00, 0x00]); // SP 1.2, 1 indexed, 0 rgba
  const imgHeader = new Uint8Array([0x04, 0x00, 0x04, 0x00, 0x02, 0x00]); // 4x4, rle_len 2
  const rleData = new Uint8Array([0x00, 0x10]); // 16 zeroes
  const sprBytes = new Uint8Array(sprHeader.length + imgHeader.length + rleData.length + pal.length);
  sprBytes.set(sprHeader, 0);
  sprBytes.set(imgHeader, sprHeader.length);
  sprBytes.set(rleData, sprHeader.length + imgHeader.length);
  sprBytes.set(pal, sprHeader.length + imgHeader.length + rleData.length);

  // ACT 2.4 with 40 slots
  const actParts = [];
  actParts.push(new Uint8Array([0x41, 0x43, 0x04, 0x02, 0x28, 0x00])); // AC 2.4, 40 slots
  actParts.push(new Uint8Array(10)); // 10 reserved bytes
  for (let s = 0; s < 40; s++) {
    actParts.push(new Uint8Array([0x01, 0x00, 0x00, 0x00])); // 1 motion
    // motion: bounds (32 bytes), clip count 1 (4 bytes)
    const mHead = new Uint8Array(36);
    mHead[32] = 0x01; // nc = 1
    actParts.push(mHead);
    // clip: 9 uint32/int32/float fields (36 bytes): x, y, sprite=0, mirror=0, color=0xFFFFFFFF, scale_x=1.0, scale_y=1.0, angle=0, pool=0
    const clipBuf = new ArrayBuffer(36);
    const clipView = new DataView(clipBuf);
    clipView.setInt32(0, 0, true);
    clipView.setInt32(4, 0, true);
    clipView.setInt32(8, 0, true); // sprite 0
    clipView.setUint32(12, 0, true);
    clipView.setUint32(16, 0xFFFFFFFF, true);
    clipView.setFloat32(20, 1.0, true);
    clipView.setFloat32(24, 1.0, true);
    clipView.setInt32(28, 0, true);
    clipView.setUint32(32, 0, true); // pool 0
    actParts.push(new Uint8Array(clipBuf));
    // event (-1 = 0xFFFFFFFF), anchor count 0
    actParts.push(new Uint8Array([0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00]));
  }
  actParts.push(new Uint8Array([0x00, 0x00, 0x00, 0x00])); // 0 events
  // 40 delays (4.0 float32 each)
  const delBuf = new ArrayBuffer(160);
  const delView = new DataView(delBuf);
  for (let s = 0; s < 40; s++) delView.setFloat32(s * 4, 4.0, true);
  actParts.push(new Uint8Array(delBuf));

  let totalActLen = 0;
  actParts.forEach(p => totalActLen += p.length);
  const actBytes = new Uint8Array(totalActLen);
  let actOff = 0;
  actParts.forEach(p => { actBytes.set(p, actOff); actOff += p.length; });

  const b64 = bytes => {
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  };

  await post(`/api/projects/${pid}/import-pair`, {
    expected_revision: 1,
    id: 'monster-ref',
    part: 'body',
    act_base64: b64(actBytes),
    spr_base64: b64(sprBytes),
  });

  await page.reload();
  await wait(async () => await page.locator('#project-select').inputValue() === pid);

  console.log('Journey 3: Declare target topology via workbench UI');
  await page.click('#define-target-btn');
  await page.fill('#modal-frame-count', '4');
  await page.fill('#modal-layers-input', 'body');
  await page.click('#submit-target-btn');
  await wait(async () => {
    const t = await text('cnt-layers');
    return /^32\b/.test(t); // 8 views x 4 frames = 32 layers
  });

  console.log('Journey 4: Stage replacement PNG and assign to Walk view 0 frame 0 layer 0');
  // Small 4x4 PNG in base64
  const pngB64 = 'iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAYAAACp8Z5+AAAAFUlEQVR4nGP8z8DwnwEJMDGgAcICAIPRAgYCkO9YAAAAAElFTkSuQmCC';
  await post(`/api/projects/${pid}/stage-png`, {
    expected_revision: 3,
    filename: 'test_rep.png',
    data_base64: pngB64,
  });

  let w = await read(`/api/projects/${pid}/workspace`);
  const walkL0 = w.requirements.layers.find(l => l.action === 'Walk' && l.view === 0 && l.frame === 0);
  assert.ok(walkL0);
  const stagedSrc = w.sources.find(s => s.source.external_ref === 'test_rep.png');
  assert.ok(stagedSrc);

  await post(`/api/projects/${pid}/assign`, {
    expected_revision: 4,
    mappings: [{
      requirement_id: walkL0.id,
      kind: 'DIRECT_SOURCE',
      source: stagedSrc.source.id,
      source_revision: 1,
      recipe: [],
    }],
  });

  await page.reload();
  await wait(async () => await page.locator('#project-select').inputValue() === pid);

  assert.equal(await page.locator('#compile-policy').inputValue(), 'preserve_pool');
  console.log('Journey 5: Inspect compilation plan before approval (verifying BLOCKED status)');
  await page.locator('#compile-details > summary').click();
  await page.selectOption('#compile-policy', 'explicit_rgba');
  await page.selectOption('#compile-resource', 'monster-ref');
  await page.click('#plan-compile-btn');
  await wait(async () => (await text('compile-status')).includes('BLOCKED'));
  const blockedStatus = await text('compile-status');
  assert.ok(blockedStatus.includes('UNAPPROVED_REPLACEMENT_ARTWORK'));

  console.log('Journey 6: Record operator visual review approval');
  // Approve walkL0 via UI or API
  const propRes = await post(`/api/projects/${pid}/review-proposal`, {
    expected_revision: 5,
    requirements: [walkL0.id],
  });
  await post(`/api/projects/${pid}/review`, {
    expected_revision: 5,
    decision: 'APPROVED',
    proposal: propRes.proposal,
  });

  await page.reload();
  await wait(async () => await page.locator('#project-select').inputValue() === pid);

  console.log('Journey 7: Inspect compilation plan after approval (verifying READY status)');
  await page.locator('#compile-details > summary').click();
  await page.selectOption('#compile-policy', 'explicit_rgba');
  await page.selectOption('#compile-resource', 'monster-ref');
  await page.click('#plan-compile-btn');
  await wait(async () => (await text('compile-status')).includes('Plan READY'));

  console.log('Journey 8: Compile modified ACT/SPR and register candidate resource');
  await page.fill('#compile-register-resource', 'monster-compiled');
  await page.click('#run-compile-btn');
  await wait(async () => (await text('compile-status')).includes('Compiled'));
  const compileStatus = await text('compile-status');
  assert.ok(compileStatus.includes('native_korangar=UNVERIFIED'));
  assert.ok(compileStatus.includes('decode_after_write=PASS'));

  const compileFacts = await text('compile-facts');
  assert.ok(compileFacts.includes('rsf.compilation-manifest/v1'));
  assert.ok(compileFacts.includes('monster-ref.act'));
  assert.ok(compileFacts.includes('monster-ref.spr'));

  console.log('Journey 9: Verify candidate resource registration and inspection');
  await wait(async () => {
    const opts = await page.locator('#preview-resource option').allInnerTexts();
    return opts.some(o => o.includes('monster-compiled'));
  });

  console.log('Journey 10: Comparison tool between reference and compiled candidate');
  await page.selectOption('#preview-resource', 'monster-ref');
  await page.selectOption('#candidate-resource', 'monster-compiled');
  await page.click('#compare-selected');
  await page.waitForTimeout(500);
  console.log('operation-status is:', await text('operation-status'));
  console.log('comparison-facts is:', await text('comparison-facts'));
  await wait(async () => (await text('comparison-facts')).includes('rsf.preview-comparison/v1'));
  const compReportText = await text('comparison-facts');
  assert.ok(compReportText.includes('SIDE_BY_SIDE'));

  assert.equal(errors.length, 0, 'Browser console/page errors occurred: ' + JSON.stringify(errors));
  console.log('ALL RSF-23 BROWSER JOURNEYS PASSED!');
};
