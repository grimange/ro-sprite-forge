async (page) => {
  const assert = {
    equal: (a, b) => { if (a !== b) throw Error(JSON.stringify({ expected: b, actual: a })); },
    ok: a => { if (!a) throw Error('Assertion failed'); },
    deepEqual: (a, b) => { if (JSON.stringify(a) !== JSON.stringify(b)) throw Error(JSON.stringify({ expected: b, actual: a })); },
  };
  const url = 'http://127.0.0.1:8182', pid = 'rsf19-' + Date.now(), fixtures = '/tmp/rsf19-synthetic';
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
    await page.screenshot({ path: '/tmp/rsf19-timeout.png' });
    throw Error('Condition timeout');
  };
  const read = route => page.evaluate(async route => {
    const r = await fetch(route);
    if (!r.ok) throw Error(await r.text());
    return r.json();
  }, route);
  const work = () => read(`/api/projects/${pid}/workspace`);

  async function select(rid) {
    const ids = await page.locator(`[data-node-id="${rid}"]`).evaluate(el => {
      let x = el.parentElement, a = [];
      while (x) {
        if (x.matches('.tree-node')) a.unshift(x.dataset.nodeId);
        x = x.parentElement;
      }
      return a;
    });
    for (const id of ids) {
      const node = page.locator(`[data-node-id="${id}"]`);
      if (await node.locator(':scope > .tree-children').evaluate(el => el.style.display === 'none')) {
        await node.locator(':scope > .tree-row > .tree-expander').click();
      }
    }
    await page.locator(`[data-node-id="${rid}"] > .tree-row`).click();
    await wait(async () => (await text('assignment-facts')).includes(rid));
  }

  // Journey A: Load workbench, create new project
  await page.goto(url);
  await page.click('#new-project-btn');
  await page.fill('#new-proj-id', pid);
  await page.fill('#new-proj-name', 'Browser PNG Ingestion Journey');
  await page.click('#submit-new-proj-btn');
  await wait(async () => await page.locator('#project-select').inputValue() === pid && (await text('proj-name')) === 'Browser PNG Ingestion Journey');

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
  const layerIds = w.requirements.layers.map(l => l.id);

  // Journey C: Import ordered PNG sequence via Workbench UI
  await page.locator('#import-png-sequence-details > summary').click();
  await page.fill('#seq-id', 'walk-test-seq');
  await page.fill('#seq-name', 'Walk Test Sequence');
  await page.setInputFiles('#seq-files', [
    fixtures + '/walk_0.png',
    fixtures + '/walk_1.png',
    fixtures + '/walk_2.png',
    fixtures + '/walk_3.png',
  ]);
  await wait(async () => page.locator('#seq-ordering-section').isVisible());
  assert.equal(await page.locator('#seq-frames-table table tr').count(), 5); // 1 header + 4 rows

  await page.click('#seq-natural-sort');
  await page.click('#import-sequence-btn');
  await wait(async () => (await text('seq-status')).includes('imported successfully'));

  // Verify that ingestion did NOT auto-assign or auto-approve
  w = await work();
  assert.equal(w.sequences.length, 1);
  assert.equal(w.sequences[0].id, 'walk-test-seq');
  assert.equal(w.sequences[0].frame_count, 4);
  assert.equal(w.project.ledger?.assignments?.length || 0, 0);
  assert.equal(w.project.review_events?.length || 0, 0);

  // Journey D: Verify sequence frames in source tray dropdown
  assert.equal(w.sources.filter(s => s.source.origin === 'AUTHORED').length, 4);
  const firstAuthoredSource = w.sources.find(s => s.source.origin === 'AUTHORED');
  assert.ok(firstAuthoredSource);
  assert.equal(firstAuthoredSource.availability, 'AVAILABLE');
  assert.equal(firstAuthoredSource.validation, 'VALID');

  await page.selectOption('#art-source', firstAuthoredSource.source.id);
  await wait(() => page.locator('#source-thumbnail').isVisible());
  assert.ok((await text('source-facts')).includes('AUTHORED'));
  assert.ok((await text('source-facts')).includes('PARTIALLY_TRANSPARENT'));

  // Journey E: Direct assignment of authored PNG frame to required occurrence
  await select(layerIds[0]);
  await page.click('#assign-selected');
  await wait(async () => (await work()).project.ledger?.assignments?.length === 1);
  await wait(async () => (await text('operation-status')).includes('Mappings saved'));

  w = await work();
  const assigned = w.project.ledger.assignments[0];
  assert.equal(assigned.requirement_id, layerIds[0]);
  assert.equal(assigned.source.id, firstAuthoredSource.source.id);
  assert.equal(assigned.kind, 'DIRECT_SOURCE');

  // Journey F: Save, reload, and verify persistence
  await page.click('#save-project-btn');
  await wait(async () => (await text('operation-status')).includes('Saved project revision'));
  await page.reload();
  await wait(async () => /^32\b/.test(await text('cnt-layers')));

  w = await work();
  assert.equal(w.sequences.length, 1);
  assert.equal(w.sequences[0].id, 'walk-test-seq');
  assert.equal(w.project.ledger.assignments.length, 1);
  assert.equal(w.project.review_events.length, 0);

  // Capture final screenshot
  await page.screenshot({ path: '/tmp/rsf19-browser-workbench.png' });
  return { status: 'PASS', project_id: pid, sequence_id: 'walk-test-seq', layers: 32 };
};
