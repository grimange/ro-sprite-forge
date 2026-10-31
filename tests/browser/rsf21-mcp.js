async (page) => {
  const assert = {
    equal: (a, b) => { if (a !== b) throw Error(JSON.stringify({ expected: b, actual: a })); },
    ok: a => { if (!a) throw Error('Assertion failed'); },
    deepEqual: (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(JSON.stringify({ expected: b, actual: a })); },
  };
  const url = 'http://127.0.0.1:8182', pid = 'rsf21-' + Date.now(), fixtures = '/tmp/rsf21-synthetic';
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
    await page.screenshot({ path: '/tmp/rsf21-timeout.png' });
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
  const work = () => read(`/api/projects/${pid}/workspace`);

  // Journey A: Load workbench, create new project
  await page.goto(url);
  await page.click('#new-project-btn');
  await page.fill('#new-proj-id', pid);
  await page.fill('#new-proj-name', 'Browser Image Transformations Journey');
  await page.click('#submit-new-proj-btn');
  await wait(async () => await page.locator('#project-select').inputValue() === pid && (await text('proj-name')) === 'Browser Image Transformations Journey');

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

  // Journey C: Stage PNG source image into project
  await page.locator('#import-single-png-details > summary').click();
  await page.setInputFiles('#single-png-file', fixtures + '/source.png');
  await page.click('#import-single-png-btn');
  await wait(async () => (await text('single-png-status')).includes('Imported frame'));

  w = await work();
  const authoredSources = w.sources.filter(s => s.source.origin === 'AUTHORED');
  assert.equal(authoredSources.length, 1);
  const origSourceSha = authoredSources[0].source.sha256;
  assert.ok(origSourceSha);

  // Journey D: Non-destructive Transformation: Crop + Flip
  await page.locator('#transform-recipes-details > summary').click();
  await page.selectOption('#transform-source', origSourceSha);
  await page.fill('#transform-recipe-id', 'recipe-crop-flip');
  await page.fill('#transform-recipe-name', 'Crop and Horizontal Flip');

  // Step 0: Crop (x: 5, y: 5, width: 40, height: 40)
  await page.click('#add-transform-step-btn');
  const step0 = page.locator('#transform-steps-list > div').nth(0);
  await step0.locator('input[data-param="x"]').fill('5');
  await step0.locator('input[data-param="y"]').fill('5');
  await step0.locator('input[data-param="width"]').fill('40');
  await step0.locator('input[data-param="height"]').fill('40');

  // Step 1: Flip (horizontal)
  await page.click('#add-transform-step-btn');
  const step1 = page.locator('#transform-steps-list > div').nth(1);
  await step1.locator('select[data-action="change-op"]').selectOption('flip');
  await step1.locator('select[data-param="direction"]').selectOption('horizontal');

  // Preview before/after
  await page.click('#preview-transform-btn');
  await wait(async () => page.locator('#transform-preview-container').isVisible());
  const factsText = await text('transform-facts');
  assert.ok(factsText.includes('"output_dimensions": [\n    40,\n    40\n  ]'));
  assert.ok(factsText.includes('"CROPPED_DISCARDED_PIXELS"'));

  // Stage derived candidate
  await page.click('#apply-transform-btn');
  await wait(async () => (await text('transform-status')).includes('Staged derived candidate'));

  // Verify workspace after transformation
  w = await work();
  assert.equal(w.recipes.length, 1);
  assert.equal(w.recipes[0].id, 'recipe-crop-flip');
  assert.equal(w.recipes[0].source_sha256, origSourceSha);
  assert.equal(w.recipes[0].operations.length, 2);

  // Verify sources contain derived blob with recipe metadata
  const derivedSources = w.sources.filter(s => s.recipe_id === 'recipe-crop-flip');
  assert.equal(derivedSources.length, 1);
  assert.equal(derivedSources[0].source_sha256, origSourceSha);
  assert.ok(derivedSources[0].loss_report.includes('CROPPED_DISCARDED_PIXELS'));
  // Original source remains unchanged and available
  const origCheck = w.sources.find(s => s.source.sha256 === origSourceSha && !s.recipe_id);
  assert.ok(origCheck);
  assert.equal(origCheck.availability, 'AVAILABLE');

  // Journey E: Matte Background Keying Transformation
  await page.selectOption('#transform-source', origSourceSha);
  await page.fill('#transform-recipe-id', 'recipe-keyed');
  await page.fill('#transform-recipe-name', 'Matte Background Keying');
  await page.click('#clear-transform-steps-btn');
  await page.click('#add-transform-step-btn');
  const matteStep = page.locator('#transform-steps-list > div').nth(0);
  await matteStep.locator('select[data-action="change-op"]').selectOption('matte_key');
  await matteStep.locator('input[data-param="color"]').fill('255,0,255');
  await matteStep.locator('input[data-param="tolerance"]').fill('5');

  await page.click('#preview-transform-btn');
  await wait(async () => (await text('transform-facts')).includes('ALPHA_CHANNEL_KEYED'));

  await page.click('#apply-transform-btn');
  await wait(async () => (await text('transform-status')).includes('recipe-keyed'));

  w = await work();
  assert.equal(w.recipes.length, 2);

  // Journey F: Assignment & Scoped Review Invalidation
  const req0 = w.requirements.layers[0].id;
  const req1 = w.requirements.layers[1].id;

  // Assign original source to req0 and req1
  await post(`/api/projects/${pid}/assign`, {
    expected_revision: w.project.revision,
    mappings: [
      { requirement_id: req0, kind: 'DIRECT_SOURCE', source: 'blob-' + origSourceSha, source_revision: 1, recipe: [] },
      { requirement_id: req1, kind: 'DIRECT_SOURCE', source: 'blob-' + origSourceSha, source_revision: 1, recipe: [] },
    ],
  });
  w = await work();

  // Review & approve req0
  const prop0 = await post(`/api/projects/${pid}/review-proposal`, {
    expected_revision: w.project.revision,
    requirements: [req0],
  });
  await post(`/api/projects/${pid}/review`, {
    expected_revision: w.project.revision,
    proposal: prop0.proposal,
    decision: 'APPROVED',
  });
  w = await work();

  // Review & approve req1
  const prop1 = await post(`/api/projects/${pid}/review-proposal`, {
    expected_revision: w.project.revision,
    requirements: [req1],
  });
  await post(`/api/projects/${pid}/review`, {
    expected_revision: w.project.revision,
    proposal: prop1.proposal,
    decision: 'APPROVED',
  });
  w = await work();

  // Verify both are APPROVED
  const statesBefore = {};
  for (const occ of w.reviews.occurrences) statesBefore[occ.requirement_id] = occ.state;
  assert.equal(statesBefore[req0], 'APPROVED');
  assert.equal(statesBefore[req1], 'APPROVED');

  // Now replace req0 assignment with the derived image
  const derivedSha = derivedSources[0].source.sha256;
  await post(`/api/projects/${pid}/assign`, {
    expected_revision: w.project.revision,
    mappings: [
      { requirement_id: req0, kind: 'DIRECT_SOURCE', source: 'blob-' + derivedSha, source_revision: 1, recipe: [] },
    ],
  });
  w = await work();

  // Verify scoped invalidation: req0 is STALE, req1 remains APPROVED
  const statesAfter = {};
  for (const occ of w.reviews.occurrences) statesAfter[occ.requirement_id] = occ.state;
  assert.equal(statesAfter[req0], 'STALE');
  assert.equal(statesAfter[req1], 'APPROVED');

  // Journey G: Out of bounds crop error handling
  await page.click('#clear-transform-steps-btn');
  await page.click('#add-transform-step-btn');
  const badStep = page.locator('#transform-steps-list > div').nth(0);
  await badStep.locator('input[data-param="x"]').fill('100'); // exceeds 64 width
  await badStep.locator('input[data-param="width"]').fill('50');

  expectFailure = true;
  await page.click('#preview-transform-btn');
  await wait(async () => (await text('operation-status')).includes('CROP_OUT_OF_BOUNDS') || (await text('transform-status')).includes('CROP_OUT_OF_BOUNDS'));
  expectFailure = false;

  console.log('ALL RSF-21 BROWSER JOURNEYS COMPLETED SUCCESSFULLY');
};