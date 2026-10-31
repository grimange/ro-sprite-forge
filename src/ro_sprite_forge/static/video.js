/* RSF-29: transport and operator selection only; RSF-28 owns all decoding. */
'use strict';
window.createVideoImport = function ({apiFetch, operation, endpoint, current, refresh}) {
  const el = id => document.getElementById('video-' + id);
  const pretty = v => JSON.stringify(v, null, 2);
  let project = null, generation = 0, busy = false, capability = null;
  let source = null, metadata = null, frames = null, preview = null, page = 0;
  const status = text => { el('status').textContent = text; };
  function exact(value) {
    if (!/^(0|-?[1-9][0-9]*)$/.test(value) || value.length > 17) throw Error('VIDEO_INVALID_SELECTION: use canonical decimal integers.');
    // BigInt is never serialized. Canonical decimal strings cross JSON unchanged.
    const integer = BigInt(value);
    if (integer < -9007199254740991n || integer > 9007199254740991n) throw Error('VIDEO_SELECTION_INTEGER_OUT_OF_RANGE: ' + value);
    return value;
  }
  function values() {
    const list = el('values').value.trim().split(',').map(v => exact(v.trim()));
    if (!list.length || list.length > 64) throw Error('VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY');
    if (new Set(list).size !== list.length) throw Error('VIDEO_DUPLICATE_SELECTION');
    return list;
  }
  function controls() {
    const available = capability?.available === true;
    el('inspect').disabled = busy || !available;
    el('scan').disabled = busy || !available || !source || el('stream').value === '';
    el('preview').disabled = busy || !available || !source || el('stream').value === '';
    el('stage').disabled = busy || !available || !preview;
    for (const id of ['file','staged','stream','mode','values']) el(id).disabled = busy || !available;
    el('prev').disabled = busy || !frames || page === 0;
    el('next').disabled = busy || !frames || (page + 1) * 50 >= frames.frames.length;
    el('candidates').querySelectorAll('button').forEach(b => { b.disabled = busy || b.dataset.boundary === 'true'; });
    el('frames').querySelectorAll('button').forEach(b => { b.disabled = busy || b.dataset.unsupported === 'true'; });
  }
  function invalidate() { preview = null; el('candidates').replaceChildren(); controls(); }
  function clearSource() {
    generation++; source = metadata = frames = null; page = 0;
    el('metadata').textContent = el('frame-info').textContent = '';
    el('frames').replaceChildren(); el('stream').replaceChildren(new Option('Inspect a video first', ''));
    invalidate(); status('Source changed. Inspect metadata before selection.');
  }
  async function run(fn) {
    if (busy) return;
    const ticket = generation, pid = current(); busy = true; controls();
    // Every async boundary checks this guard before displaying or acting on data.
    const valid = () => ticket === generation && pid === current();
    try { await fn(valid); }
    catch (err) { if (valid()) status(err.message); }
    finally { if (valid()) { busy = false; controls(); } }
  }
  function request() {
    if (!source) throw Error('VIDEO_SOURCE_REQUIRED');
    return {...source, stream_index: el('stream').value, mode: el('mode').value, values: values()};
  }
  function renderFrames() {
    el('frames').replaceChildren();
    if (!frames) return;
    frames.frames.slice(page * 50, (page + 1) * 50).forEach(f => {
      const value = el('mode').value === 'pts' ? f.pts : f.ordinal;
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn';
      b.textContent = `Add ordinal ${f.ordinal} · PTS ${f.pts ?? 'unknown'} (${frames.time_base.numerator}/${frames.time_base.denominator})`;
      try { exact(value); } catch (_) { b.dataset.unsupported = 'true'; }
      b.onclick = () => {
        try {
          const old = el('values').value.trim() ? values() : [];
          if (old.includes(value)) throw Error('VIDEO_DUPLICATE_SELECTION');
          if (old.length >= 64) throw Error('VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY');
          el('values').value = [...old, exact(value)].join(', '); invalidate();
          status('Selection updated in requested order. Preview to resolve actual images.');
        } catch (e) { status(e.message); }
      };
      el('frames').append(b);
    }); controls();
  }
  function renderCandidates() {
    el('candidates').replaceChildren();
    preview.manifest.items.forEach((item, i) => {
      const row = document.createElement('li');
      const facts = document.createElement('p');
      facts.textContent = `Order ${i} · requested ${preview.manifest.request.mode} ${item.requested} → ordinal ${item.ordinal} · PTS ${item.pts ?? 'unknown'} · time base ${item.time_base.numerator}/${item.time_base.denominator} · ${item.width}×${item.height} ${item.mode} · PNG ${item.png_sha256} · video ${preview.manifest.inspection.source.sha256} · validated, visual review UNVERIFIED`;
      const image = document.createElement('img'); image.alt = `Actual candidate ${i}, source ordinal ${item.ordinal}, PTS ${item.pts ?? 'unknown'}`;
      image.src = 'data:image/png;base64,' + preview.pngs[i]; row.append(facts, image);
      for (const [name, offset] of [['Move earlier', -1], ['Move later', 1], ['Remove', 0]]) {
        const b = document.createElement('button'); b.type = 'button'; b.className = 'btn';
        b.textContent = name; b.setAttribute('aria-label', `${name} candidate ${i}`);
        b.dataset.boundary = String(offset !== 0 && (i + offset < 0 || i + offset >= preview.manifest.items.length));
        b.onclick = () => {
          const selected = values();
          if (offset) [selected[i], selected[i + offset]] = [selected[i + offset], selected[i]];
          else selected.splice(i, 1);
          el('values').value = selected.join(', '); invalidate();
          status('Candidate order changed. Preview the revised collection before staging.');
        };
        row.append(b);
      }
      el('candidates').append(row);
    }); controls();
  }
  async function capabilities() {
    await run(async valid => {
      const result = await apiFetch('/api/video-capabilities'); if (!valid()) return;
      capability = result;
      el('capability').textContent = result.available ? 'FFprobe/FFmpeg available. Local candidate extraction is optional.' : pretty(result);
    });
  }
  el('import-details').addEventListener('toggle', () => {
    if (el('import-details').open && !capability && current()) capabilities();
  });
  el('file').onchange = () => { el('staged').value = ''; clearSource(); };
  el('staged').onchange = () => { el('file').value = ''; clearSource(); };
  el('stream').onchange = () => { generation++; frames = null; el('frames').replaceChildren(); el('frame-info').textContent = ''; invalidate(); };
  el('mode').onchange = () => { el('values').value = ''; invalidate(); renderFrames(); };
  el('values').oninput = () => { invalidate(); status('Selection changed; preview required.'); };
  el('prev').onclick = () => { page--; renderFrames(); };
  el('next').onclick = () => { page++; renderFrames(); };
  el('inspect').onclick = () => run(async valid => {
    invalidate(); status('Inspecting container and streams…');
    let next;
    if (el('staged').value) next = {source_sha256:el('staged').value, expected_sha256:el('staged').value};
    else {
      const f = el('file').files[0];
      if (!f || f.size === 0 || f.size > 32 * 1024 * 1024) throw Error('VIDEO_SIZE_EXCEEDED_OR_EMPTY: select a local video up to 32 MiB.');
      const buffer = await f.arrayBuffer(); if (!valid()) return;
      const hash = await crypto.subtle.digest('SHA-256', buffer); if (!valid()) return;
      const sha = [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2,'0')).join('');
      const bytes = new Uint8Array(buffer); let raw = '';
      for (let i = 0; i < bytes.length; i += 8192) raw += String.fromCharCode(...bytes.subarray(i, i + 8192));
      next = {data_base64:btoa(raw), expected_sha256:sha};
    }
    const result = await operation('video-metadata', next); if (!valid()) return;
    source = next; metadata = result; frames = null; el('frames').replaceChildren(); el('frame-info').textContent = '';
    el('metadata').textContent = pretty({filename:el('file').files[0]?.name || 'Immutable staged video', ...result});
    el('stream').replaceChildren(new Option('Choose absolute video stream', ''));
    result.streams.forEach(s => el('stream').add(new Option(`Stream ${s.index}: ${s.codec_name} ${s.width}×${s.height} ${s.pix_fmt} · time base ${s.time_base?.numerator ?? '?'}/${s.time_base?.denominator ?? '?'}`, s.index)));
    if (result.streams.length === 1) el('stream').value = result.streams[0].index;
    status('Metadata inspected. Choose stream, then inspect frames or enter exact selections.');
  });
  el('scan').onclick = () => run(async valid => {
    invalidate(); status('Inspecting bounded presentation frames…');
    const result = await operation('video-frames', {...source, stream_index:el('stream').value}); if (!valid()) return;
    frames = result; page = 0;
    el('frame-info').textContent = pretty({source:result.source, selected_stream:result.selected_stream, time_base:result.time_base, timing:result.timing, decoded_frame_count:result.decoded_frame_count});
    renderFrames(); status('Actual presentation frames inspected. PTS is source metadata, independent of ACT timing.');
  });
  el('preview').onclick = () => run(async valid => {
    invalidate(); const data = request(); status('Extracting exact candidate PNG previews…');
    const result = await operation('video-preview', data); if (!valid()) return;
    preview = result; renderCandidates();
    status(`Preview ${result.manifest.canonical_sha256}. Project unchanged. Confirm this order to stage.`);
  });
  el('stage').onclick = () => run(async valid => {
    const data = {...request(), preview_sha256:preview.manifest.canonical_sha256};
    status('Validating preview identity and staging confirmed candidates…');
    const result = await operation('video-stage', data); if (!valid()) return;
    status(`Staged collection ${result.collection.canonical_sha256} at revision ${result.revision}. Assign manually in the source tray; visual review remains UNVERIFIED.`);
    await refresh();
  });
  controls();
  return {async load(pid) {
    if (project !== pid) {
      project = pid; busy = false; el('file').value = ''; el('values').value = ''; clearSource();
    }
    const ticket = generation;
    const result = await apiFetch(endpoint('video-imports'));
    if (pid !== current() || ticket !== generation) return;
    const old = el('staged').value;
    el('staged').replaceChildren(new Option('Select staged video', ''));
    result.sources.forEach(s => el('staged').add(new Option(`${s.filename} · ${s.sha256}`, s.sha256)));
    if ([...el('staged').options].some(o => o.value === old)) el('staged').value = old;
    el('history').textContent = pretty(result.collections.map(c => ({canonical_sha256:c.canonical_sha256,
      video_sha256:c.inspection.source.sha256, stream:c.request.stream, request:c.request, items:c.items,
      visual_review:c.visual_review, automatic_assignment:c.automatic_assignment})));
    if (el('import-details').open && !capability) await capabilities();
  }};
};
