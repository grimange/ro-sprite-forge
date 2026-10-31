async (page) => {
  const assert = {
    equal: (a, b) => { if (a !== b) throw Error(JSON.stringify({ expected: b, actual: a })); },
    ok: a => { if (!a) throw Error('Assertion failed'); },
    deepEqual: (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(JSON.stringify({ expected: b, actual: a })); },
  };
  const url = 'http://127.0.0.1:8182', pid = 'rsf20-' + Date.now(), fixtures = '/tmp/rsf20-synthetic';
  await page.setViewportSize({ width: 1600, height: 1100 });
  const errors = [], failed = [], expectedErrors = [];
  let expectFailure = false;
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error') (expectFailure ? expectedErrors : errors).push(m.text()); });
  page.on('requestfailed', r => failed.push(r.url() + ': ' + r.failure()?.errorText));

  const text = id => page.locator('#' + id).innerText();
  const wait = async fn => {
    for (let n = 0; n < 100; n++) {
      if (await fn()) return;
      await page.waitForTimeout(100);
    }
    await page.screenshot({ path: '/tmp/rsf20-timeout.png' });
    throw Error('Condition timeout');
  };
  const read = route => page.evaluate(async route => {
    const r = await fetch(route);
    if (!r.ok) throw Error(await r.text());
    return r.json();
  }, route);
  const work = () => read(`/api/projects/${pid}/workspace`);

  // Journey A: Load workbench, create new project
  await page.goto(url);
  await page.click('#new-project-btn');
  await page.fill('#new-proj-id', pid);
  await page.fill('#new-proj-name', 'Browser Spritesheet Extraction Journey');
  await page.click('#submit-new-proj-btn');
  await wait(async () => await page.locator('#project-select').inputValue() === pid && (await text('proj-name')) === 'Browser Spritesheet Extraction Journey');

  // Journey B: Define target with Walk 4 frames and explicit layer topology
  await page.click('#define-target-btn');
  await page.fill('#modal-frame-count', '4');
  await page.fill('#modal-layers-input', 'body');
  await page.click('#submit-target-btn');
  await wait(async () => {
    const t = await text('cnt-layers');
    return /^32\b/.test(t);
  });
  let w = await work();
  assert.equal(w.requirements.layers.length, 32);

  // Journey C: Load spritesheet file into Extraction UI
  await page.locator('#import-spritesheet-details > summary').click();
  await page.setInputFiles('#sheet-file', fixtures + '/sheet.png');
  await wait(async () => page.locator('#sheet-preview-container').isVisible());
  assert.ok((await text('sheet-info')).includes('sheet.png (128×64 px'));

  // Journey D: Grid Mode extraction (2 columns x 1 row of 64x64 cells)
  await page.click('#mode-grid');
  await page.fill('#grid-cell-w', '64');
  await page.fill('#grid-cell-h', '64');
  await page.fill('#grid-cols', '2');
  await page.fill('#grid-rows', '1');
  await page.fill('#extraction-id', 'grid-extract-test');
  await page.click('#extract-spritesheet-btn');
  await wait(async () => (await text('extraction-status')).includes('Extracted 2 frames'));

  // Verify that extraction did NOT auto-assign or auto-approve
  w = await work();
  assert.equal(w.extractions.length, 1);
  assert.equal(w.extractions[0].id, 'grid-extract-test');
  assert.equal(w.extractions[0].item_count, 2);
  assert.equal(w.project.ledger?.assignments?.length || 0, 0);
  assert.equal(w.project.review_events?.length || 0, 0);

  // Journey E: Verify extracted frames in source tray dropdown
  assert.equal(w.sources.filter(s => s.source.origin === 'AUTHORED').length, 3); // 1 sheet + 2 crops
  const extractedSources = w.sources.filter(s => s.extraction_id === 'grid-extract-test');
  assert.equal(extractedSources.length, 2);
  assert.equal(extractedSources[0].availability, 'AVAILABLE');
  assert.equal(extractedSources[0].validation, 'VALID');

  // Journey F: Out-of-bounds manual crop error handling
  await page.click('#mode-manual');
  await page.click('#add-rect-row-btn');
  // Fill rectangle exceeding sheet bounds
  const rows = page.locator('#rectangles-table > div');
  const lastRow = rows.last();
  await lastRow.locator('input[data-field="x"]').fill('100');
  await lastRow.locator('input[data-field="width"]').fill('64'); // 100 + 64 = 164 > 128
  expectFailure = true;
  await page.click('#extract-spritesheet-btn');
  await wait(async () => (await text('extraction-status')).includes('RECTANGLE_OUT_OF_BOUNDS') || (await text('operation-status')).includes('RECTANGLE_OUT_OF_BOUNDS'));
  expectFailure = false;

  console.log('ALL RSF-20 BROWSER JOURNEYS COMPLETED SUCCESSFULLY');
};
