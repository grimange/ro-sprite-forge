async (page) => {
  const assert = {
    equal: (a, b) => { if (a !== b) throw Error(JSON.stringify({ expected: b, actual: a })); },
    notEqual: (a, b) => { if (a === b) throw Error(JSON.stringify({ unexpected: b, actual: a })); },
    ok: a => { if (!a) throw Error('Assertion failed'); },
    deepEqual: (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(JSON.stringify({ expected: b, actual: a })); },
  };
  const url = 'http://127.0.0.1:8182', pid = 'rsf22-' + Date.now(), fixtures = '/tmp/rsf22-synthetic';
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
    console.error('TIMEOUT STATUS: single-png-status =', await page.locator('#single-png-status').innerText(), 'operation-status =', await page.locator('#operation-status').innerText());
    await page.screenshot({ path: '/tmp/rsf22-timeout.png' });
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
  const syncPage = async () => {
    await page.reload();
    await wait(async () => await page.locator('#project-select').inputValue() === pid);
  };
  const work = () => read(`/api/projects/${pid}/workspace`);

  // =========================================================================
  // Journey A: Complete bounded Walk declaration and 6-frame PNG ingestion
  // =========================================================================
  await page.goto(url);
  await page.click('#new-project-btn');
  await page.fill('#new-proj-id', pid);
  await page.fill('#new-proj-name', 'Bounded Walk End-to-End Workflow');
  await page.click('#submit-new-proj-btn');
  await wait(async () => await page.locator('#project-select').inputValue() === pid && (await text('proj-name')) === 'Bounded Walk End-to-End Workflow');

  // Declare Walk target: 6 frames per view, layer topology: body
  await page.click('#define-target-btn');
  await page.fill('#modal-frame-count', '6');
  await page.fill('#modal-layers-input', 'body');
  await page.click('#submit-target-btn');
  await wait(async () => {
    const t = await text('cnt-layers');
    return /^48\b/.test(t); // 8 views x 6 frames = 48 layers
  });
  let w = await work();
  assert.equal(w.requirements.layers.length, 48);

  // Ingest 6 synthetic Walk frames as ordered sequence
  await page.locator('#import-png-sequence-details > summary').click();
  await page.fill('#seq-id', 'walk-seq-0');
  await page.fill('#seq-name', 'Walk View 0 Sequence');
  const seqPaths = [0, 1, 2, 3, 4, 5].map(i => `${fixtures}/walk_${i}.png`);
  await page.setInputFiles('#seq-files', seqPaths);
  await wait(async () => page.locator('#seq-ordering-section').isVisible());
  await page.click('#seq-natural-sort');
  await page.click('#import-sequence-btn');
  await wait(async () => (await text('seq-status')).includes('imported successfully'));

  w = await work();
  assert.equal(w.sequences.length, 1);
  const seqFrames = w.sources.filter(s => s.sequence_id === 'walk-seq-0');
  assert.equal(seqFrames.length, 6);

  // Explicitly map all 6 frames to Walk view 0 (frames 0..5)
  const dir0Layers = w.requirements.layers.filter(l => l.view === 0);
  assert.equal(dir0Layers.length, 6);
  const mappings = dir0Layers.map((layer, idx) => ({
    requirement_id: layer.id,
    kind: 'DIRECT_SOURCE',
    source: seqFrames[idx].source.id,
    source_revision: 1,
    recipe: [],
  }));

  await post(`/api/projects/${pid}/assign`, {
    expected_revision: w.project.revision,
    mappings,
  });
  await syncPage();
  w = await work();

  // Verify each assignment is valid and available
  for (let i = 0; i < 6; i++) {
    const assigned = w.ledger.assignments.find(a => a.requirement_id === dir0Layers[i].id);
    assert.ok(assigned);
    assert.equal(assigned.availability, 'AVAILABLE');
    assert.equal(assigned.validation, 'VALID');
    assert.equal(assigned.effective_source.sha256, seqFrames[i].source.sha256);
  }

  // =========================================================================
  // Journey B: Derived artwork via RSF-21 transformation
  // =========================================================================
  // Ingest transform source PNG
  await page.locator('#import-single-png-details > summary').click();
  await page.setInputFiles('#single-png-file', fixtures + '/transform_source.png');
  await wait(async () => page.locator('#import-single-png-btn').isVisible());
  await page.click('#import-single-png-btn');
  await wait(async () => (await text('single-png-status')).includes('Imported frame'));

  w = await work();
  const tSource = w.sources.find(s => s.source.external_ref === 'transform_source.png');
  assert.ok(tSource);

  // Apply horizontal flip transformation recipe
  await page.locator('#transform-recipes-details > summary').click();
  await page.selectOption('#transform-source', tSource.source.sha256);
  await page.fill('#transform-recipe-id', 'recipe-walk-flip');
  await page.fill('#transform-recipe-name', 'Walk Direction Flip');
  await page.click('#clear-transform-steps-btn');
  await page.click('#add-transform-step-btn');
  const step0 = page.locator('#transform-steps-list > div').nth(0);
  await step0.locator('select[data-action="change-op"]').selectOption('flip');
  await step0.locator('select[data-param="direction"]').selectOption('horizontal');

  await page.click('#preview-transform-btn');
  await wait(async () => page.locator('#transform-preview-container').isVisible());

  await page.click('#apply-transform-btn');
  await wait(async () => (await text('transform-status')).includes('Staged derived candidate'));

  w = await work();
  const derivedSrc = w.sources.find(s => s.recipe_id === 'recipe-walk-flip');
  assert.ok(derivedSrc);
  assert.notEqual(derivedSrc.source.sha256, tSource.source.sha256);

  // =========================================================================
  // Journey C: Spritesheet extraction integration
  // =========================================================================
  await page.locator('#import-spritesheet-details > summary').click();
  await page.setInputFiles('#sheet-file', fixtures + '/sheet.png');
  await wait(async () => page.locator('#sheet-preview-container').isVisible());

  await page.click('#mode-grid');
  await page.fill('#grid-cell-w', '64');
  await page.fill('#grid-cell-h', '64');
  await page.fill('#grid-cols', '2');
  await page.fill('#grid-rows', '1');
  await page.fill('#extraction-id', 'walk-sheet-cells');
  await page.click('#extract-spritesheet-btn');
  await wait(async () => (await text('extraction-status')).includes('Extracted 2 frames'));

  w = await work();
  assert.equal(w.extractions.length, 1);
  const sheetCrops = w.sources.filter(s => s.extraction_id === 'walk-sheet-cells');
  assert.equal(sheetCrops.length, 2);

  // =========================================================================
  // Journey D: Human-review mechanics (Approve & Reject)
  // =========================================================================
  // Propose review for Walk direction 0 frames 0..2
  const reviewReqs = [dir0Layers[0].id, dir0Layers[1].id, dir0Layers[2].id];
  const prop = await post(`/api/projects/${pid}/review-proposal`, {
    expected_revision: w.project.revision,
    requirements: reviewReqs,
  });
  assert.ok(prop.proposal.approvable);
  assert.equal(prop.previews.length, 3);

  // Approve proposal
  await post(`/api/projects/${pid}/review`, {
    expected_revision: w.project.revision,
    proposal: prop.proposal,
    decision: 'APPROVED',
  });
  await syncPage();
  w = await work();
  assert.equal(w.reviews.counts.APPROVED, 3);

  // Propose review for frame 3 and Reject
  const propReject = await post(`/api/projects/${pid}/review-proposal`, {
    expected_revision: w.project.revision,
    requirements: [dir0Layers[3].id],
  });
  await post(`/api/projects/${pid}/review`, {
    expected_revision: w.project.revision,
    proposal: propReject.proposal,
    decision: 'REJECTED',
  });
  await syncPage();
  w = await work();
  assert.equal(w.reviews.counts.REJECTED, 1);
  assert.equal(w.reviews.counts.APPROVED, 3);

  // =========================================================================
  // Journey E: Scoped approval invalidation
  // =========================================================================
  // Replace assignment for frame 0 with the derived image
  await post(`/api/projects/${pid}/assign`, {
    expected_revision: w.project.revision,
    mappings: [{
      requirement_id: dir0Layers[0].id,
      kind: 'DIRECT_SOURCE',
      source: derivedSrc.source.id,
      source_revision: 1,
      recipe: [],
    }],
  });
  await syncPage();
  w = await work();

  // Frame 0 basis changed -> STALE!
  // Frame 1 and Frame 2 were untouched -> remain APPROVED!
  const occMap = {};
  for (const o of w.reviews.occurrences) occMap[o.requirement_id] = o.state;
  assert.equal(occMap[dir0Layers[0].id], 'STALE');
  assert.equal(occMap[dir0Layers[1].id], 'APPROVED');
  assert.equal(occMap[dir0Layers[2].id], 'APPROVED');
  assert.equal(occMap[dir0Layers[3].id], 'REJECTED');

  // =========================================================================
  // Journey F: Partial scope & truthful gap reporting
  // =========================================================================
  // Direction 0 has 6 assignments. Directions 1..7 have 42 unassigned occurrences!
  assert.equal(w.coverage.counts.assignments.direct, 6);
  assert.equal(w.coverage.counts.assignments.unassigned, 42);
  // Full profile is incomplete
  assert.equal(w.coverage.status.completeness, 'INCOMPLETE');
  assert.equal(w.coverage.status.assignment_coverage, 'PARTIAL');
  assert.equal(w.coverage.status.export_ready, false);

  // =========================================================================
  // Journey G: Negative integration error handling
  // =========================================================================
  // 1. Invalid review proposal with unassigned requirement ID
  expectFailure = true;
  let rejectedUnassigned = false;
  try {
    await post(`/api/projects/${pid}/review-proposal`, {
      expected_revision: w.project.revision,
      requirements: [w.requirements.layers[10].id], // unassigned view
    });
  } catch (err) {
    rejectedUnassigned = true;
    assert.ok(err.message.includes('UNASSIGNED_OR_NONEXISTENT_REVIEW_REQUIREMENT'));
  }
  assert.ok(rejectedUnassigned);

  // 2. Stale project revision rejection
  let rejectedStale = false;
  try {
    await post(`/api/projects/${pid}/assign`, {
      expected_revision: 9999,
      mappings: [{
        requirement_id: dir0Layers[0].id,
        kind: 'DIRECT_SOURCE',
        source: derivedSrc.source.id,
        source_revision: 1,
        recipe: [],
      }],
    });
  } catch (err) {
    rejectedStale = true;
    assert.ok(err.message.includes('Project revision conflict'));
  }
  assert.ok(rejectedStale);
  expectFailure = false;

  // Confirm project round-trip: save and reload
  await page.click('#save-project-btn');
  await wait(async () => (await text('operation-status')).includes('Saved project revision') || (await text('proj-name')) === 'Bounded Walk End-to-End Workflow');

  console.log('ALL RSF-22 BROWSER JOURNEYS COMPLETED SUCCESSFULLY');
};