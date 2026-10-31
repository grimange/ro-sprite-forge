/**
 * RO Sprite Forge — Requirements-First Operator Workbench (RSF-16)
 * Pure standard ES6, zero external web libraries.
 */

(function () {
  'use strict';

  // Application State
  const state = {
    csrfToken: null,
    projects: [],
    currentProject: null,
    manifest: null,
    requirements: null,
    coverage: null,
    selectedNode: null,
    activeFilter: 'ALL',
    searchQuery: '',
    expandedNodes: new Set(),
  };

  // DOM Elements
  const el = {};

  function initElements() {
    el.projectSelect = document.getElementById('project-select');
    el.newProjectBtn = document.getElementById('new-project-btn');
    el.saveProjectBtn = document.getElementById('save-project-btn');
    el.exportTextBtn = document.getElementById('export-text-btn');
    el.exportJsonBtn = document.getElementById('export-json-btn');
    el.defineTargetBtn = document.getElementById('define-target-btn');

    el.projName = document.getElementById('proj-name');
    el.projActor = document.getElementById('proj-actor');
    el.projProfile = document.getElementById('proj-profile');
    el.projRevision = document.getElementById('proj-revision');
    el.projStatusBadge = document.getElementById('proj-status-badge');

    el.targetScope = document.getElementById('target-scope');
    el.targetTopology = document.getElementById('target-topology');
    el.topologyAlert = document.getElementById('topology-alert');

    el.searchInput = document.getElementById('tree-search');
    el.filterBar = document.getElementById('filter-bar');
    el.treeContainer = document.getElementById('tree-container');

    el.inspectorCard = document.getElementById('inspector-card');
    el.issuesCard = document.getElementById('issues-card');
    el.diagnosticsList = document.getElementById('diagnostics-list');

    el.detailReqId = document.getElementById('detail-req-id');
    el.detailCoordinates = document.getElementById('detail-coordinates');
    el.detailTopology = document.getElementById('detail-topology');
    el.detailAvail = document.getElementById('detail-avail');
    el.detailValid = document.getElementById('detail-valid');
    el.detailReview = document.getElementById('detail-review');
    el.detailRuntime = document.getElementById('detail-runtime');

    el.cntSlots = document.getElementById('cnt-slots');
    el.cntFrames = document.getElementById('cnt-frames');
    el.cntLayers = document.getElementById('cnt-layers');
    el.cntUnassigned = document.getElementById('cnt-unassigned');
    el.cntSources = document.getElementById('cnt-sources');

    el.statusCompleteness = document.getElementById('status-completeness');
    el.statusSpecification = document.getElementById('status-specification');
    el.statusCoverage = document.getElementById('status-coverage');
    el.statusValidation = document.getElementById('status-validation');
    el.statusReview = document.getElementById('status-review');

    el.newProjectModal = document.getElementById('new-project-modal');
    el.targetModal = document.getElementById('target-modal');
  }

  // Network helpers
  async function apiFetch(endpoint, options = {}) {
    const headers = { ...options.headers };
    if (state.csrfToken && (options.method === 'POST' || options.method === 'PUT' || options.method === 'DELETE')) {
      headers['X-CSRF-Token'] = state.csrfToken;
    }
    const res = await fetch(endpoint, { credentials: 'same-origin', ...options, headers });
    if (!res.ok) {
      let errData = {};
      try {
        errData = await res.json();
      } catch (e) {
        // fallback
      }
      const msg = errData?.error?.message || `HTTP ${res.status}: ${res.statusText}`;
      const err = new Error(msg);
      err.status = res.status;
      err.data = errData;
      throw err;
    }
    const contentType = res.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      return await res.json();
    }
    return await res.text();
  }

  async function loadCsrfToken() {
    try {
      const data = await apiFetch('/api/csrf-token');
      state.csrfToken = data.csrf_token;
    } catch (err) {
      console.warn('Could not fetch CSRF token:', err);
    }
  }

  async function refreshProjectsList(selectId = null) {
    try {
      const data = await apiFetch('/api/projects');
      state.projects = data.projects || [];
      el.projectSelect.innerHTML = '<option value="">-- Select Project --</option>';
      for (const p of state.projects) {
        const opt = document.createElement('option');
        opt.value = p.project_id;
        opt.textContent = `${p.name} (${p.project_id}) - Rev ${p.revision}`;
        el.projectSelect.appendChild(opt);
      }
      if (selectId) {
        el.projectSelect.value = selectId;
        await loadProject(selectId);
      } else if (state.projects.length > 0 && !state.currentProject) {
        let remembered;
        try {remembered = localStorage.getItem('rsf.currentProject');} catch (_) {}
        const chosen = state.projects.find(p=>p.project_id===remembered)?.project_id || state.projects[0].project_id;
        el.projectSelect.value = chosen;
        await loadProject(chosen);
      }
    } catch (err) {
      showError('Failed to list projects: ' + err.message);
    }
  }

  async function loadProject(projectId) {
    if (!projectId) {
      resetProjectView();
      return;
    }
    try {
      pausePlayback();
      state.currentProject = projectId;
      try {localStorage.setItem('rsf.currentProject',projectId);} catch (_) {}
      state.selectedNode = null;
      state.manifest = await apiFetch(`/api/projects/${encodeURIComponent(projectId)}`);
      updateProjectHeader();
      await loadRequirementsAndCoverage();
    } catch (err) {
      showError('Failed to load project: ' + err.message);
    }
  }

  function resetProjectView() {
    state.currentProject = null;
    state.manifest = null;
    state.requirements = null;
    state.coverage = null;
    state.selectedNode = null;
    el.projName.textContent = 'None Selected';
    el.projActor.textContent = '-';
    el.projProfile.textContent = '-';
    el.projRevision.textContent = 'Rev -';
    el.projStatusBadge.textContent = '[ ] NO PROJECT';
    el.targetScope.textContent = '-';
    el.targetTopology.textContent = '-';
    el.topologyAlert.style.display = 'none';
    el.treeContainer.innerHTML = '<div style="padding:16px;color:var(--text-dim);">No project active.</div>';
    resetCounters();
  }

  function updateProjectHeader() {
    if (!state.manifest) return;
    el.projName.textContent = state.manifest.name || state.manifest.project_id;
    el.projActor.textContent = state.manifest.actor || 'player';
    el.projProfile.textContent = state.manifest.profile || 'player';
    el.projRevision.textContent = `Rev ${state.manifest.revision}`;

    const target = state.manifest.target;
    if (!target) {
      el.projStatusBadge.textContent = '[!] NO TARGET';
      el.projStatusBadge.className = 'badge badge-underspecified';
      el.targetScope.textContent = 'NOT_SET';
      el.targetTopology.textContent = 'NONE';
      el.topologyAlert.style.display = 'flex';
      el.topologyAlert.querySelector('.alert-title').textContent = 'TARGET NOT DECLARED';
      el.topologyAlert.querySelector('.alert-msg').textContent =
        'This project has no active target declaration. Define a target and declare layer topology before artwork.';
      return;
    }

    el.targetScope.textContent = target.scope || 'scoped';
    const topKind = getTopologySummary(target);
    el.targetTopology.textContent = topKind.summary;

    if (topKind.isUnderspecified) {
      el.projStatusBadge.textContent = '[!] UNDERSPECIFIED';
      el.projStatusBadge.className = 'badge badge-underspecified';
      el.topologyAlert.style.display = 'flex';
      el.topologyAlert.querySelector('.alert-title').textContent = 'UNDERSPECIFIED_LAYER_TOPOLOGY';
      el.topologyAlert.querySelector('.alert-msg').textContent =
        'Target contains actions or views without declared layer topology or frame counts. Artwork assignments cannot proceed without declared topology.';
    } else {
      el.projStatusBadge.textContent = '[✓] SPECIFIED';
      el.projStatusBadge.className = 'badge badge-ready';
      el.topologyAlert.style.display = 'none';
    }
  }

  function getTopologySummary(target) {
    if (!target || !target.actions || target.actions.length === 0) {
      return { summary: 'UNDERSPECIFIED', isUnderspecified: true };
    }
    let hasExplicit = false;
    let hasInherited = false;
    let hasUnderspecified = false;

    for (const act of target.actions) {
      if (act.requirement === 'OUT_OF_SCOPE') continue;
      if (!act.parts || act.parts.length === 0) {
        hasUnderspecified = true;
        continue;
      }
      for (const p of act.parts) {
        if (!p.views || p.views.length === 0) {
          hasUnderspecified = true;
          continue;
        }
        for (const v of p.views) {
          if (!v.topology) {
            hasUnderspecified = true;
          } else if (v.topology.kind === 'explicit') {
            hasExplicit = true;
          } else if (v.topology.kind === 'inherited') {
            hasInherited = true;
          }
        }
      }
    }

    if (hasUnderspecified) {
      return { summary: 'UNDERSPECIFIED', isUnderspecified: true };
    }
    if (hasExplicit && hasInherited) return { summary: 'MIXED (Explicit + Inherited)', isUnderspecified: false };
    if (hasExplicit) return { summary: 'EXPLICIT_TOPOLOGY', isUnderspecified: false };
    if (hasInherited) return { summary: 'INHERITED_TOPOLOGY', isUnderspecified: false };
    return { summary: 'UNDERSPECIFIED', isUnderspecified: true };
  }

  async function loadRequirementsAndCoverage() {
    if (!state.currentProject) return;
    try {
      // Fetch requirements
      const reqRes = await apiFetch(`/api/projects/${encodeURIComponent(state.currentProject)}/requirements`);
      state.requirements = reqRes.resolved ? reqRes.requirements : null;

      // Fetch coverage
      const covRes = await apiFetch(`/api/projects/${encodeURIComponent(state.currentProject)}/coverage`);
      state.coverage = covRes.evaluated ? covRes.coverage : null;

      renderTree();
      renderCounters();
      renderIssues();
      await loadInteractive();
    } catch (err) {
      console.warn('Requirements/Coverage fetch note:', err);
      renderTree();
      renderCounters();
      renderIssues();
    }
  }

  // Hierarchical Tree Rendering
  function renderTree() {
    el.treeContainer.innerHTML = '';
    if (!state.requirements || !state.requirements.layers || state.requirements.layers.length === 0) {
      const emptyMsg = document.createElement('div');
      emptyMsg.style.padding = '16px';
      emptyMsg.style.color = 'var(--text-dim)';
      emptyMsg.textContent = state.manifest?.target
        ? 'No layers resolved. Check target definition or topology.'
        : 'Target not defined. Use "Define Target & Topology" above.';
      el.treeContainer.appendChild(emptyMsg);
      return;
    }

    const occurrences = state.coverage?.occurrences || [];
    const occByLayerId = new Map(occurrences.map(o => [o.requirement_id, o]));

    // Build hierarchy: Action -> View -> Frame -> Layer
    const actionMap = new Map();

    for (const layer of state.requirements.layers) {
      const occ = occByLayerId.get(layer.id) || {
        requirement_id: layer.id,
        part: layer.part,
        action: layer.action,
        numeric_slot: layer.runtime_slot,
        view: layer.view,
        frame: layer.frame,
        layer: layer.ordinal,
        role: layer.role,
        requirement: layer.requirement || 'REQUIRED',
        availability: 'UNVERIFIED',
        validation: 'UNVERIFIED',
        visual_review: 'UNVERIFIED',
        runtime_support: 'UNVERIFIED',
      };

      if (!matchesFilter(occ) || !matchesSearch(occ)) {
        continue;
      }

      const actKey = `${layer.action}`;
      if (!actionMap.has(actKey)) {
        actionMap.set(actKey, new Map());
      }
      const viewMap = actionMap.get(actKey);

      const viewKey = `view-${layer.view}-slot-${layer.runtime_slot ?? 'UNMAPPED'}`;
      if (!viewMap.has(viewKey)) {
        viewMap.set(viewKey, new Map());
      }
      const frameMap = viewMap.get(viewKey);

      const frameKey = `frame-${layer.frame}`;
      if (!frameMap.has(frameKey)) {
        frameMap.set(frameKey, []);
      }
      frameMap.get(frameKey).push({ layer, occ });
    }

    if (actionMap.size === 0) {
      const noMatch = document.createElement('div');
      noMatch.style.padding = '16px';
      noMatch.style.color = 'var(--text-dim)';
      noMatch.textContent = 'No occurrences match current filter or search.';
      el.treeContainer.appendChild(noMatch);
      return;
    }

    // Render tree nodes
    for (const [actionName, viewMap] of actionMap.entries()) {
      const actionNode = createTreeNode({
        id: `action-${actionName}`,
        label: actionName,
        icon: '📁',
        badge: `${viewMap.size} views`,
        badgeClass: 'badge-unsupported',
        level: 0,
      });

      const childrenContainer = actionNode.querySelector('.tree-children');

      for (const [viewKey, frameMap] of viewMap.entries()) {
        const viewParts = viewKey.split('-');
        const viewNum = viewParts[1];
        const slotNum = viewParts[3];

        const viewNode = createTreeNode({
          id: `view-${actionName}-${viewKey}`,
          label: `View ${viewNum} (Slot ${slotNum})`,
          icon: '🧭',
          badge: `${frameMap.size} frames`,
          badgeClass: 'badge-unsupported',
          level: 1,
        });

        const frameChildren = viewNode.querySelector('.tree-children');

        for (const [frameKey, layerItems] of frameMap.entries()) {
          const frameNum = frameKey.split('-')[1];

          const frameNode = createTreeNode({
            id: `frame-${actionName}-${viewNum}-${frameKey}`,
            label: `Frame ${frameNum}`,
            icon: '🎞️',
            badge: `${layerItems.length} layers`,
            badgeClass: 'badge-unsupported',
            level: 2,
          });

          const layerChildren = frameNode.querySelector('.tree-children');

          for (const item of layerItems) {
            const statusBadge = getStatusBadge(item.occ);
            const layerNode = createTreeNode({
              id: item.layer.id,
              label: `Layer ${item.layer.ordinal}: ${item.layer.role || 'unnamed'}`,
              icon: '🎨',
              badge: statusBadge.text,
              badgeClass: statusBadge.className,
              level: 3,
              isLeaf: true,
              data: item,
            });
            layerChildren.appendChild(layerNode);
          }

          frameChildren.appendChild(frameNode);
        }

        childrenContainer.appendChild(viewNode);
      }

      el.treeContainer.appendChild(actionNode);
    }
  }

  function createTreeNode({ id, label, icon, badge, badgeClass, level, isLeaf = false, data = null }) {
    const node = document.createElement('div');
    node.className = 'tree-node';
    node.dataset.nodeId = id;

    const row = document.createElement('div');
    row.className = 'tree-row';
    row.tabIndex = 0; // Accessible keyboard focus
    row.setAttribute('role', 'treeitem');
    row.setAttribute('aria-level', level + 1);

    if (!isLeaf) {
      const expander = document.createElement('span');
      expander.className = 'tree-expander';
      const isExpanded = state.expandedNodes.has(id);
      expander.textContent = isExpanded ? '▼' : '▶';
      expander.onclick = (e) => {
        e.stopPropagation();
        toggleNodeExpansion(id);
      };
      row.appendChild(expander);
    } else {
      const spacer = document.createElement('span');
      spacer.style.width = '14px';
      row.appendChild(spacer);
    }

    const iconSpan = document.createElement('span');
    iconSpan.className = 'tree-icon';
    iconSpan.textContent = icon;
    row.appendChild(iconSpan);

    const labelSpan = document.createElement('span');
    labelSpan.className = 'tree-label';
    labelSpan.textContent = label;
    row.appendChild(labelSpan);

    if (badge) {
      const badgeSpan = document.createElement('span');
      badgeSpan.className = `badge ${badgeClass} tree-badge`;
      badgeSpan.textContent = badge;
      row.appendChild(badgeSpan);
    }

    row.onclick = () => {
      selectTreeNode(row, id, data);
      if (!isLeaf) toggleNodeExpansion(id);
    };

    row.onkeydown = (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectTreeNode(row, id, data);
        if (!isLeaf) toggleNodeExpansion(id);
      } else if (e.key === 'ArrowRight' && !isLeaf && !state.expandedNodes.has(id)) {
        e.preventDefault();
        toggleNodeExpansion(id);
      } else if (e.key === 'ArrowLeft' && !isLeaf && state.expandedNodes.has(id)) {
        e.preventDefault();
        toggleNodeExpansion(id);
      }
    };

    node.appendChild(row);

    if (!isLeaf) {
      const children = document.createElement('div');
      children.className = 'tree-children';
      children.style.display = state.expandedNodes.has(id) ? 'block' : 'none';
      node.appendChild(children);
    }

    return node;
  }

  function toggleNodeExpansion(nodeId) {
    if (state.expandedNodes.has(nodeId)) {
      state.expandedNodes.delete(nodeId);
    } else {
      state.expandedNodes.add(nodeId);
    }
    renderTree();
  }

  function selectTreeNode(rowEl, id, data) {
    document.querySelectorAll('.tree-row.selected').forEach(r => r.classList.remove('selected'));
    rowEl.classList.add('selected');
    state.selectedNode = data;
    renderDetails(data);
    inspectAssignment();
  }

  function getStatusBadge(occ) {
    if (!occ) return { text: '[?] UNVERIFIED', className: 'badge-unreviewed' };

    // Priority non-color status indicators
    if (occ.reason === 'UNDERSPECIFIED_LAYER_TOPOLOGY' || occ.reason === 'UNDERSPECIFIED_FRAME_COUNT') {
      return { text: '[!] UNDERSPECIFIED', className: 'badge-underspecified' };
    }
    if (occ.runtime_support === 'UNSUPPORTED') {
      return { text: '[ø] UNSUPPORTED', className: 'badge-unsupported' };
    }
    if (occ.validation === 'INVALID') {
      return { text: '[x] INVALID', className: 'badge-invalid' };
    }
    if (occ.availability === 'MISSING' || occ.assignment_id === null) {
      return { text: '[-] UNASSIGNED', className: 'badge-unassigned' };
    }
    if (occ.visual_review === 'UNVERIFIED') {
      return { text: '[?] UNREVIEWED', className: 'badge-unreviewed' };
    }
    if (occ.availability === 'REUSED') {
      return { text: '[~] REUSED', className: 'badge-reused' };
    }
    if (occ.validation === 'VALID' && (occ.visual_review === 'APPROVED' || occ.visual_review === 'NOT_REQUIRED')) {
      return { text: '[✓] READY', className: 'badge-ready' };
    }
    return { text: '[?] UNVERIFIED', className: 'badge-unreviewed' };
  }

  function matchesFilter(occ) {
    if (state.activeFilter === 'ALL') return true;
    if (state.activeFilter === 'UNDERSPECIFIED') {
      return occ.reason === 'UNDERSPECIFIED_LAYER_TOPOLOGY' || occ.reason === 'UNDERSPECIFIED_FRAME_COUNT';
    }
    if (state.activeFilter === 'UNASSIGNED') {
      return occ.assignment_id === null || occ.availability === 'MISSING';
    }
    if (state.activeFilter === 'INVALID') {
      return occ.validation === 'INVALID';
    }
    if (state.activeFilter === 'UNREVIEWED') {
      return occ.visual_review === 'UNVERIFIED';
    }
    if (state.activeFilter === 'UNSUPPORTED') {
      return occ.runtime_support === 'UNSUPPORTED';
    }
    if (state.activeFilter === 'REUSED') {
      return occ.availability === 'REUSED';
    }
    if (state.activeFilter === 'READY') {
      return occ.validation === 'VALID' && (occ.visual_review === 'APPROVED' || occ.visual_review === 'NOT_REQUIRED');
    }
    return true;
  }

  function matchesSearch(occ) {
    if (!state.searchQuery) return true;
    const q = state.searchQuery.toLowerCase();
    const targetStr = `${occ.requirement_id} ${occ.action} ${occ.part} ${occ.role} view${occ.view} slot${occ.numeric_slot}`.toLowerCase();
    return targetStr.includes(q);
  }

  // Occurrence Details Rendering
  function renderDetails(item) {
    if (!item) {
      el.detailReqId.textContent = 'None selected';
      el.detailCoordinates.textContent = '-';
      el.detailTopology.textContent = '-';
      el.detailAvail.textContent = '-';
      el.detailValid.textContent = '-';
      el.detailReview.textContent = '-';
      el.detailRuntime.textContent = '-';
      return;
    }

    const { layer, occ } = item;
    el.detailReqId.textContent = layer.id;
    el.detailCoordinates.textContent =
      `Part: ${layer.part} | Action: ${layer.action} | Slot: ${layer.runtime_slot ?? 'UNVERIFIED'} | View: ${layer.view} | Frame: ${layer.frame} | Layer: ${layer.ordinal} (${layer.role || 'no-role'})`;

    // Topology Provenance
    const target = state.manifest?.target;
    let prov = 'Explicit target declaration';
    if (layer.authority) prov = `Authority: ${layer.authority}`;
    el.detailTopology.textContent = prov;

    // Orthogonal Status Details
    el.detailAvail.textContent = `${occ.availability || 'UNVERIFIED'} (Source: ${occ.source_id || 'None'})`;
    el.detailValid.textContent = `${occ.validation || 'UNVERIFIED'}`;
    el.detailReview.textContent = `${occ.visual_review || 'UNVERIFIED'} (Binding: ${occ.review_binding || 'UNRECORDED'})`;
    el.detailRuntime.textContent = `${occ.runtime_support || 'UNVERIFIED'}`;

    // Issues if any
    el.diagnosticsList.innerHTML = '';
    if (occ.issues && occ.issues.length > 0) {
      el.issuesCard.style.display = 'flex';
      for (const issue of occ.issues) {
        const li = document.createElement('li');
        li.style.marginBottom = '6px';
        li.innerHTML = `<strong>${issue}</strong>: ${occ.action_needed || 'Required action undefined'}`;
        el.diagnosticsList.appendChild(li);
      }
    } else {
      el.issuesCard.style.display = 'none';
    }
  }

  // Counters & Global Status
  function renderCounters() {
    if (!state.coverage || !state.coverage.counts) {
      resetCounters();
      return;
    }
    const counts = state.coverage.counts;
    const status = state.coverage.status;

    el.cntSlots.textContent = `${counts.structural.required_slots} req / ${counts.structural.underspecified_slots} under`;
    el.cntFrames.textContent = `${counts.structural.required_frames} req`;
    el.cntLayers.textContent = `${counts.structural.required_layers} req`;
    el.cntUnassigned.textContent = `${counts.assignments.unassigned}`;
    el.cntSources.textContent = `${counts.assignments.unique_selected_sources} (${counts.assignments.distinct_source_contents} distinct)`;

    el.statusCompleteness.textContent = status.completeness;
    el.statusSpecification.textContent = status.structural_specification;
    el.statusCoverage.textContent = status.assignment_coverage;
    el.statusValidation.textContent = status.technical_validation;
    el.statusReview.textContent = status.accepted_artwork_coverage;
  }

  function resetCounters() {
    el.cntSlots.textContent = '0 req / 0 under';
    el.cntFrames.textContent = '0 req';
    el.cntLayers.textContent = '0 req';
    el.cntUnassigned.textContent = '0';
    el.cntSources.textContent = '0 (0 distinct)';

    el.statusCompleteness.textContent = 'NOT_EVALUATED';
    el.statusSpecification.textContent = 'UNDERSPECIFIED';
    el.statusCoverage.textContent = 'UNASSIGNED';
    el.statusValidation.textContent = 'NOT_RUN';
    el.statusReview.textContent = 'INCOMPLETE';
  }

  function renderIssues() {
    if (!state.coverage?.unresolved_items || state.coverage.unresolved_items.length === 0) {
      return;
    }
    // Summary of diagnostics is accessible in work order export
  }

  // Target & Topology Editor
  function openTargetModal() {
    el.targetModal.style.display = 'flex';
    const target = state.manifest?.target;
    document.getElementById('modal-scope').value = target?.scope || 'scoped';

    // Populate actions
    const currentActions = target?.actions || [];
    const walkAction = currentActions.find(a => a.id === 'Walk') || {};
    const walkBody = walkAction.parts?.find(p => p.part === 'body') || {};
    const walkView = walkBody.views?.[0] || {};

    document.getElementById('modal-walk-enabled').checked = !target || walkAction.requirement === 'REQUIRED';
    document.getElementById('modal-frame-count').value = walkView.frame_count || 4;

    const topology = walkView.topology;
    if (topology && topology.kind === 'explicit') {
      document.getElementById('modal-topology-type').value = 'explicit';
      document.getElementById('modal-layers-input').value = (topology.layers || ['body']).join(', ');
    } else {
      document.getElementById('modal-topology-type').value = 'explicit';
      document.getElementById('modal-layers-input').value = 'torso, cloak';
    }
  }

  function closeTargetModal() {
    el.targetModal.style.display = 'none';
  }

  async function saveTargetModal() {
    if (!state.currentProject || !state.manifest) return;
    const scope = document.getElementById('modal-scope').value;
    const walkEnabled = document.getElementById('modal-walk-enabled').checked;
    const frameCount = parseInt(document.getElementById('modal-frame-count').value, 10);
    const topType = document.getElementById('modal-topology-type').value;
    const layersStr = document.getElementById('modal-layers-input').value;
    const layers = layersStr.split(',').map(s => s.trim()).filter(Boolean);

    if (layers.length === 0) {
      alert('Error: Ordered layer topology requires at least one layer name (e.g. "body" or "torso, cloak").');
      return;
    }

    const actions = [];
    if (walkEnabled) {
      // Standard 8 views
      const views = [];
      for (let v = 0; v < 8; v++) {
        views.push({
          view: v,
          frame_count: frameCount,
          topology: {
            kind: 'explicit',
            layers: layers,
          },
        });
      }
      actions.push({
        id: 'Walk',
        requirement: 'REQUIRED',
        parts: [
          {
            part: 'body',
            views: views,
          },
        ],
      });
    }

    const newTarget = {
      schema: 'rsf.target/v2',
      id: `${state.currentProject}-target`,
      revision: (state.manifest.target?.revision || 0) + 1,
      previous_sha256: state.manifest.target?.canonical_sha256 || null,
      scope: scope,
      parts: ['body'],
      compatibility: { status: 'UNVERIFIED', declarations: [] },
      actions: actions,
    };

    const updatedProject = {
      ...state.manifest,
      target: newTarget,
    };

    try {
      const result = await operation('target', {target: newTarget});
      state.manifest = result.project;
      closeTargetModal();
      updateProjectHeader();
      await loadRequirementsAndCoverage();
      showSuccess(`Target updated to Revision ${state.manifest.revision}`);
    } catch (err) {
      showError('Failed to save target: ' + err.message);
    }
  }

  // Work Order Exports
  async function exportWorkOrder(format) {
    if (!state.currentProject) return;
    try {
      const url = `/api/projects/${encodeURIComponent(state.currentProject)}/work-order?format=${format}`;
      const data = await apiFetch(url);
      const content = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
      const mime = format === 'json' ? 'application/json' : 'text/plain';
      const ext = format === 'json' ? 'json' : 'txt';

      const blob = new Blob([content], { type: mime });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${state.currentProject}-work-order.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(a.href);
      showSuccess(`Exported work order (${ext})`);
    } catch (err) {
      showError('Failed to export work order: ' + err.message);
    }
  }

  // Notifications
  function showError(msg) {
    const status = document.getElementById('operation-status');
    status.textContent = '[ERROR] ' + msg;
    status.classList.remove('status-success');
    status.classList.add('status-error');
    status.setAttribute('role','alert');
  }

  function showSuccess(msg) {
    const status = document.getElementById('operation-status');
    status.textContent = '[OK] ' + msg;
    status.classList.remove('status-error');
    status.classList.add('status-success');
    status.setAttribute('role','status');
  }

  // Setup Event Handlers
  function setupListeners() {
    el.projectSelect.onchange = (e) => loadProject(e.target.value);

    el.newProjectBtn.onclick = () => {
      el.newProjectModal.style.display = 'flex';
    };

    document.getElementById('cancel-new-proj-btn').onclick = () => {
      el.newProjectModal.style.display = 'none';
    };

    document.getElementById('submit-new-proj-btn').onclick = async () => {
      const projId = document.getElementById('new-proj-id').value.trim();
      const projName = document.getElementById('new-proj-name').value.trim();
      const actor = document.getElementById('new-proj-actor').value;
      const profile = document.getElementById('new-proj-profile').value;

      if (!projId || !projName) {
        alert('Project ID and Name are required.');
        return;
      }

      try {
        const created = await apiFetch('/api/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            project_id: projId,
            name: projName,
            actor: actor,
            profile: profile,
          }),
        });
        el.newProjectModal.style.display = 'none';
        await refreshProjectsList(created.project_id);
        showSuccess(`Project ${created.project_id} created.`);
      } catch (err) {
        showError('Could not create project: ' + err.message);
      }
    };

    el.defineTargetBtn.onclick = openTargetModal;
    document.getElementById('cancel-target-btn').onclick = closeTargetModal;
    document.getElementById('submit-target-btn').onclick = saveTargetModal;

    el.exportTextBtn.onclick = () => exportWorkOrder('text');
    el.exportJsonBtn.onclick = () => exportWorkOrder('json');

    // Filters
    el.filterBar.querySelectorAll('.filter-btn').forEach(btn => {
      btn.onclick = () => {
        el.filterBar.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.activeFilter = btn.dataset.filter;
        el.filterBar.querySelectorAll('.filter-btn').forEach(b => b.setAttribute('aria-pressed', String(b === btn)));
        renderTree();
      };
    });

    // Search
    el.searchInput.oninput = (e) => {
      state.searchQuery = e.target.value.trim();
      renderTree();
    };

    // Keyboard Shortcuts (RSF-38 ergonomics & accessibility)
    window.addEventListener('keydown', (e) => {
      const target = e.target;
      const isInput = target && (
        (target.tagName === 'INPUT' && !['checkbox', 'radio', 'button', 'submit', 'reset', 'range'].includes(target.type)) ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      );

      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (state.currentProject && state.manifest) {
          saveCurrent();
        }
        return;
      }

      // Review dialog shortcuts
      const reviewDialog = byId('review-dialog');
      if (reviewDialog && reviewDialog.open) {
        if (e.key === 'Escape') {
          e.preventDefault();
          byId('cancel-review')?.click();
          return;
        }
        if (!isInput) {
          if (e.key === 'a' || e.key === 'A') {
            e.preventDefault();
            byId('approve-review')?.click();
            return;
          }
          if (e.key === 'r' || e.key === 'R') {
            e.preventDefault();
            byId('reject-review')?.click();
            return;
          }
        }
      }

      if (isInput) return;

      // Timeline frame stepping & playback controls
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        byId('previous-frame')?.click();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        byId('next-frame')?.click();
      } else if (e.key === ' ') {
        e.preventDefault();
        if (interaction.playing) {
          byId('pause')?.click();
        } else {
          byId('play')?.click();
        }
      }
      // Integer zoom controls
      else if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        stepAnimZoom(1);
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        stepAnimZoom(-1);
      } else if (e.key === '0') {
        e.preventDefault();
        applyAnimZoom(1);
      }
      // Background style cycling
      else if (e.key === 'b' || e.key === 'B') {
        e.preventDefault();
        cyclePreviewBackground();
      }
    });
  }

  // Transport/presentation only: Python owns assignments, timeline and composition.
  let videoImport = null;
  const interaction = {workspace:null, selection:null, playing:false, timer:null, epoch:0, elapsed:0, started:0, busy:false, sourceEpoch:0};
  const byId = id => document.getElementById(id);
  const pretty = value => JSON.stringify(value,null,2);
  function endpoint(name) {
    if (!state.currentProject) throw new Error('Choose a project first.');
    return `/api/projects/${encodeURIComponent(state.currentProject)}/${name}`;
  }
  async function operation(name, data={}) {
    return apiFetch(endpoint(name), {method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...data,expected_revision:state.manifest.revision})});
  }
  function populate(id, records, blank) {
    const select = byId(id), old = select.value;
    select.replaceChildren();
    if (blank !== undefined) select.add(new Option(blank,''));
    records.forEach(([value,label]) => select.add(new Option(label,String(value))));
    if ([...select.options].some(o => o.value === old)) select.value = old;
  }

  // Integer nearest-neighbor zoom and transparency background (RSF-38)
  let currentZoom = 1;
  function applyAnimZoom(factor) {
    const img = byId('animation-preview');
    const select = byId('preview-zoom');
    if (factor !== undefined) currentZoom = Number(factor) || 1;
    if (select && Number(select.value) !== currentZoom) select.value = String(currentZoom);
    if (!img || img.hidden) return;
    if (img.naturalWidth && img.naturalHeight) {
      img.style.width = (img.naturalWidth * currentZoom) + 'px';
      img.style.height = (img.naturalHeight * currentZoom) + 'px';
      img.style.maxWidth = 'none';
      img.style.maxHeight = 'none';
    } else {
      img.style.transform = currentZoom === 1 ? 'none' : `scale(${currentZoom})`;
    }
  }

  function setPreviewBackground(bgMode) {
    const vp = byId('preview-viewport');
    const select = byId('preview-bg');
    if (!vp) return;
    vp.className = `preview-viewport bg-${bgMode}`;
    if (select && select.value !== bgMode) select.value = bgMode;
  }

  function cyclePreviewBackground() {
    const modes = ['checker-dark', 'checker-light', 'solid-dark', 'solid-white', 'transparent'];
    const select = byId('preview-bg');
    const current = select ? select.value : 'checker-dark';
    const nextIdx = (modes.indexOf(current) + 1) % modes.length;
    setPreviewBackground(modes[nextIdx]);
  }

  function stepAnimZoom(delta) {
    const levels = [1, 2, 3, 4, 8];
    let idx = levels.indexOf(currentZoom);
    if (idx === -1) idx = 0;
    const newIdx = Math.max(0, Math.min(levels.length - 1, idx + delta));
    applyAnimZoom(levels[newIdx]);
  }

  function picture(id, raw) {
    const img = byId(id);
    img.hidden = !raw;
    if (raw) {
      img.src = 'data:image/png;base64,'+raw;
      if (id === 'animation-preview') {
        applyAnimZoom();
      }
    } else {
      img.removeAttribute('src');
    }
  }
  async function loadInteractive() {
    const project = state.currentProject;
    const w = await apiFetch(endpoint('workspace'));
    if (project !== state.currentProject) return;
    pausePlayback();
    interaction.workspace = w;
    state.manifest = w.project;
    picture('source-thumbnail',null);
    byId('source-facts').textContent = 'Select a source to inspect its current evidence.';
    byId('resource-counts').textContent = pretty(w.resources);
    populate('art-source',w.sources.map(r => {
      const name = r.source.external_ref || r.image_identity || r.source.id;
      const dim = r.width && r.height ? ` ${r.width}x${r.height}` : '';
      const trans = r.transparency_kind ? ` ${r.transparency_kind}` : '';
      return [r.source.id, `${r.part || r.source.origin || r.source.kind}: ${name}${dim}${trans} · ${r.availability} · ${r.validation}`];
    }),'Select exact source');
    populate('transform-source',w.sources.filter(r => r.source.sha256).map(r => {
      const name = r.source.external_ref || r.image_identity || r.source.id;
      const dim = r.width && r.height ? ` ${r.width}x${r.height}` : '';
      return [r.source.sha256, `${name}${dim} · ${r.source.sha256.slice(0, 8)}`];
    }),'Select source image');
    populate('reuse-assignment',(w.ledger?.assignments || []).filter(a => a.kind !== 'UNASSIGNED').map(a => [a.id,`${a.id} r${a.revision} → ${a.requirement_id}`]),'Select source assignment');
    const parts = w.resources.map(r => [r.id,`${r.id} (${r.part})`]);
    populate('preview-resource',parts,'Select reference resource');
    populate('candidate-resource',parts,'No candidate selected');
    populate('preview-head',w.resources.filter(r => r.part === 'head').map(r => [r.id,r.id]),'No head');
    if (byId('compile-resource')) {
      populate('compile-resource',parts,'Select base resource');
      if (!byId('compile-resource').value && parts.length > 0) {
        const bodyRes = w.resources.find(r => r.part === 'body') || w.resources[0];
        byId('compile-resource').value = bodyRes.id;
      }
    }
    if (byId('compile-head-resource')) {
      populate('compile-head-resource',w.resources.filter(r => r.part === 'head').map(r => [r.id,r.id]),'No head resource');
    }
    updateActions();
    await inspectAssignment();
    showReviewState();
    await videoImport?.load(project);
  }
  async function saveCurrent() {
    try {
      pausePlayback();
      const saved = await apiFetch(`/api/projects/${encodeURIComponent(state.currentProject)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:state.manifest.revision,project:state.manifest})});
      state.manifest = saved; updateProjectHeader();
      await loadRequirementsAndCoverage();
      showSuccess(`Saved project revision ${saved.revision}.`);
    } catch(err) {showError(err.message);}
  }
  async function publishMappings(mappings) {
    if (!confirm('Confirm explicit mappings (no visual approval). Existing reuse dependents follow the revised assignment; affected reviews become STALE.\n'+pretty(mappings))) return;
    pausePlayback();
    const result = await operation('assign',{mappings});
    state.manifest = result.project;
    await loadRequirementsAndCoverage(); updateProjectHeader();
    byId('batch-mappings').value = '[]';
    showSuccess(`Mappings saved at project revision ${state.manifest.revision}. Visual approval unchanged.`);
  }
  function destination() {
    const layer = state.selectedNode?.layer;
    if (!layer) throw new Error('Select an exact layer requirement in the tree.');
    return layer.id;
  }
  function directMapping() {
    const record = interaction.workspace?.sources.find(s => s.source.id === byId('art-source').value);
    if (!record) throw new Error('Select an existing source.');
    return {requirement_id:destination(),kind:'DIRECT_SOURCE',source:record.source.id,source_revision:record.source.revision,recipe:[]};
  }
  async function inspectAssignment() {
    const epoch = ++interaction.sourceEpoch;
    picture('reuse-before',null); picture('reuse-after',null);
    const rid = state.selectedNode?.layer?.id;
    const report = interaction.workspace?.ledger?.assignments.find(a => a.requirement_id === rid);
    const declared = state.manifest?.ledger?.assignments.find(a => a.requirement_id === rid);
    const occurrence = state.coverage?.occurrences?.find(a => a.requirement_id === rid);
    showReviewState();
    byId('assignment-facts').textContent = pretty({requirement:state.selectedNode?.layer || null,target:interaction.workspace?.requirements?.target,profile:interaction.workspace?.requirements?.runtime_profile,
      assignment:declared || 'UNASSIGNED',validation:report || null,coverage:occurrence || null,
      warning:'Assignment, availability, preview and operator approval are separate. No automatic approval.'});
    if (report?.effective_source) {
      try {
        const result = await operation('source-preview',{assignment:report.id});
        if (epoch !== interaction.sourceEpoch) return;
        picture('reuse-before',result.before_base64);picture('reuse-after',result.png_base64);
        byId('assignment-facts').textContent += '\n'+pretty(result.execution);
      } catch(err) {if (epoch === interaction.sourceEpoch) showError(err.message);}
    }
  }
  let displayedReview = null;
  function showReviewState() {
    const reviews = interaction.workspace?.reviews;
    const rid = state.selectedNode?.layer?.id;
    byId('review-state').textContent = pretty({counts:reviews?.counts,selected:reviews?.occurrences.find(r=>r.requirement_id===rid),export_ready:false});
  }
  function reviewRequirements() {
    const selected = state.selectedNode?.layer;
    if (byId('review-scope').value==='batch') return JSON.parse(byId('review-batch').value);
    if (!selected) throw new Error('Select a layer to define the review scope.');
    return interaction.workspace.requirements.layers.filter(l=> {
      if (byId('review-scope').value==='layer') return l.id===selected.id;
      if (l.part!==selected.part || l.action!==selected.action) return false;
      if (byId('review-scope').value==='action') return true;
      if (l.view!==selected.view) return false;
      return byId('review-scope').value==='view' || l.frame===selected.frame;
    }).map(l=>l.id);
  }
  async function prepareReview() {
    pausePlayback();
    const project=state.currentProject;
    const result = await operation('review-proposal',{requirements:reviewRequirements()});
    if(project!==state.currentProject) throw new Error('Project changed while preparing review. Select the scope again.');
    displayedReview = {proposal:result.proposal,project};
    byId('review-proposal').textContent = pretty(result.proposal);
    byId('review-images').replaceChildren();
    for (const item of result.previews) {
      const figure=document.createElement('figure'), label=document.createElement('figcaption');
      label.textContent=item.requirement.id+' · '+item.preview.execution+' · '+item.preview.fidelity;
      figure.append(label);
      if(item.preview.png_base64) {const img=document.createElement('img');img.src='data:image/png;base64,'+item.preview.png_base64;img.alt=item.requirement.id+' exact executable source recipe';figure.append(img);}
      const details=document.createElement('pre');details.textContent=pretty({requirement:item.requirement,frame:item.frame,slot:item.slot,assignment:item.assignment,source:item.preview.source,lineage:item.preview.lineage,recipe:item.preview.transform_chain});figure.append(details);
      byId('review-images').append(figure);
    }
    byId('approve-review').disabled=!result.proposal.approvable;
    byId('exempt-review').disabled=!result.proposal.exemption_allowed;
    byId('review-exemption').checked=false;
    byId('review-dialog').showModal();
  }
  async function submitReview(decision) {
    if (!displayedReview || displayedReview.project!==state.currentProject) throw new Error('Reload the review scope.');
    const proposal=displayedReview.proposal;
    const result=await apiFetch(endpoint('review'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({expected_revision:proposal.project_revision,proposal,decision,
      policy:decision==='NOT_REQUIRED'?'UNCHANGED_REFERENCE_STRUCTURAL_ONLY':null,structural_only:byId('review-exemption').checked})});
    byId('review-dialog').close();displayedReview=null;
    state.manifest=result.project;
    await loadRequirementsAndCoverage();updateProjectHeader();
    showSuccess(`Recorded ${decision} for ${proposal.members.length} exact occurrences. Export readiness remains separate.`);
  }
  function selectedResource() {return interaction.workspace?.resources.find(r => r.id === byId('preview-resource').value);}
  function updateActions() {
    pausePlayback();
    const actions = selectedResource()?.actions || [];
    const groups = new Map();
    actions.forEach(a => groups.set(Math.floor(a.slot/8),a.action || `UNVERIFIED numeric group ${Math.floor(a.slot/8)}`));
    populate('play-action',[...groups.entries()].map(([g,label])=>[g,`${label} · group ${g}`]));
    updateViews();
  }
  function updateViews() {
    pausePlayback();
    const previousView = interaction.selection?.view;
    const group = Number(byId('play-action').value);
    populate('play-view',(selectedResource()?.actions || []).filter(a => Math.floor(a.slot/8) === group).map(a => [a.slot,`View ${a.view ?? 'UNVERIFIED'} · exact slot ${a.slot}`]));
    const matchingView = selectedResource()?.actions.find(a => Math.floor(a.slot/8) === group && a.view === previousView);
    if (matchingView) byId('play-view').value = matchingView.slot;
    byId('play-frame').value = 0;
    interaction.elapsed = 0;
    interaction.selection = null;
    picture('animation-preview',null); picture('comparison-preview',null);
    byId('current-frame').textContent = 'Frame not selected';
    byId('timing-facts').textContent = '';
  }
  function previewRequest() {
    const resource = selectedResource();
    if (!resource) throw new Error('Select an imported reference resource.');
    const action = resource.actions.find(a => a.slot === Number(byId('play-view').value));
    if (!action || action.view === null) throw new Error('Action/view mapping UNVERIFIED: no exact semantic selection.');
    const context = {};
    for (const [id,key] of [['movement-speed','movement_speed'],['duration-ms','duration_ms']]) {
      if (byId(id).value !== '') context[key] = Number(byId(id).value);
    }
    return {resource:resource.id,head:byId('preview-head').value || null,slot:action.slot,view:action.view,
      frame:Number(byId('play-frame').value),context,speed:Number(byId('play-speed').value)};
  }
  function showFrame(result) {
    const s = result.report.selection;
    interaction.selection = s;
    byId('play-frame').max = s.frame_count-1;
    byId('play-frame').value = s.frame;
    byId('current-frame').textContent = `Frame ${s.frame} / ${s.frame_count-1} · slot ${s.resolved_slot} · view ${s.view} · fallback ${s.fallback}`;
    byId('timing-facts').textContent = pretty(s);
    byId('frame-facts').textContent = pretty(result.report);
    picture('animation-preview',result.png_base64);
  }
  function pausePlayback() {
    if (interaction.playing) interaction.elapsed += performance.now()-interaction.started;
    interaction.playing = false;
    clearTimeout(interaction.timer); interaction.epoch++;
  }
  async function renderSelection(extra={}) {
    const epoch = ++interaction.epoch;
    const result = await operation('preview',{...previewRequest(),...extra});
    if (epoch === interaction.epoch) showFrame(result);
    return result;
  }
  async function playbackTick(epoch) {
    if (!interaction.playing || epoch !== interaction.epoch) return;
    try {
      const request = previewRequest();
      const result = await operation('preview',{...request,frame:0,resume_frame:interaction.startFrame,elapsed_ms:Math.floor(performance.now()-interaction.started)});
      if (!interaction.playing || epoch !== interaction.epoch) return;
      showFrame(result);
      const s = result.report.selection;
      if (!['SUPPORTED','DIAGNOSTIC'].includes(s.timing_status)) {
        pausePlayback(); showError('Timing unresolved: supply the required external runtime context. Manual stepping remains available.'); return;
      }
      if (s.terminal_hold) {pausePlayback(); return;}
      interaction.timer = setTimeout(()=>playbackTick(epoch),100);
    } catch(err) {if (epoch === interaction.epoch) {pausePlayback();showError(err.message);}}
  }
  function setupInteractive() {
    const handle = (id,fn) => byId(id).addEventListener('click',async()=>{try {await fn();}catch(err){showError(err.message);}});
    handle('prepare-review',prepareReview);
    handle('approve-review',()=>submitReview('APPROVED'));
    handle('reject-review',()=>submitReview('REJECTED'));
    handle('exempt-review',()=>submitReview('NOT_REQUIRED'));
    handle('cancel-review',()=>{byId('review-dialog').close();displayedReview=null;});
    handle('save-project-btn',saveCurrent);
    handle('import-pair',async()=>{
      const encode = async id => {const file=byId(id).files[0];if(!file || file.size>32*1024*1024) throw new Error('Select a file no larger than 32 MiB.'); const a=new Uint8Array(await file.arrayBuffer());let raw='';for(let i=0;i<a.length;i+=8192) raw+=String.fromCharCode(...a.subarray(i,i+8192));return btoa(raw);};
      const result=await operation('import-pair',{id:byId('resource-id').value,part:byId('resource-part').value,act_base64:await encode('resource-act'),spr_base64:await encode('resource-spr')});
      state.manifest=result.project;await loadRequirementsAndCoverage();updateProjectHeader();showSuccess('Exact resource bytes imported; no artwork assignments or approvals created.');
    });

    let currentSeqFiles = [];
    function renderSeqTable() {
      const container = byId('seq-frames-table');
      if (!container) return;
      if (currentSeqFiles.length === 0) {
        container.innerHTML = '<div style="color:var(--text-dim);padding:8px;">No PNG frames selected.</div>';
        byId('import-sequence-btn').style.display = 'none';
        return;
      }
      let html = '<table style="width:100%;font-size:12px;border-collapse:collapse;"><thead><tr style="border-bottom:1px solid var(--border-color);text-align:left;"><th style="width:40px;padding:4px;">#</th><th style="padding:4px;">Filename</th><th style="width:60px;padding:4px;">Size</th><th style="width:70px;padding:4px;">Order</th></tr></thead><tbody>';
      currentSeqFiles.forEach((f, idx) => {
        html += `<tr style="border-bottom:1px solid var(--border-color);"><td style="padding:4px;"><input type="number" class="seq-ord-input" data-index="${idx}" value="${f.ordinal}" min="0" max="999" style="width:36px;padding:2px;"></td><td style="padding:4px;word-break:break-all;">${f.file.name}</td><td style="padding:4px;color:var(--text-dim);">${(f.file.size/1024).toFixed(1)}k</td><td style="padding:4px;"><button type="button" class="btn seq-up-btn" data-index="${idx}" ${idx===0?'disabled':''}>↑</button><button type="button" class="btn seq-down-btn" data-index="${idx}" ${idx===currentSeqFiles.length-1?'disabled':''}>↓</button></td></tr>`;
      });
      html += '</tbody></table>';
      container.innerHTML = html;
      byId('import-sequence-btn').style.display = 'inline-block';

      container.querySelectorAll('.seq-ord-input').forEach(input => {
        input.onchange = (e) => {
          const i = parseInt(e.target.dataset.index, 10);
          const val = parseInt(e.target.value, 10);
          if (!isNaN(val) && val >= 0) {
            currentSeqFiles[i].ordinal = val;
          }
        };
      });
      container.querySelectorAll('.seq-up-btn').forEach(btn => {
        btn.onclick = () => {
          const i = parseInt(btn.dataset.index, 10);
          if (i > 0) {
            const tmp = currentSeqFiles[i - 1];
            currentSeqFiles[i - 1] = currentSeqFiles[i];
            currentSeqFiles[i] = tmp;
            currentSeqFiles.forEach((f, idx) => { f.ordinal = idx; });
            renderSeqTable();
          }
        };
      });
      container.querySelectorAll('.seq-down-btn').forEach(btn => {
        btn.onclick = () => {
          const i = parseInt(btn.dataset.index, 10);
          if (i < currentSeqFiles.length - 1) {
            const tmp = currentSeqFiles[i + 1];
            currentSeqFiles[i + 1] = currentSeqFiles[i];
            currentSeqFiles[i] = tmp;
            currentSeqFiles.forEach((f, idx) => { f.ordinal = idx; });
            renderSeqTable();
          }
        };
      });
    }

    if (byId('seq-files')) {
      byId('seq-files').onchange = (e) => {
        const files = Array.from(e.target.files || []).filter(f => f.name.toLowerCase().endsWith('.png'));
        if (files.length === 0) {
          currentSeqFiles = [];
          byId('seq-ordering-section').style.display = 'none';
          renderSeqTable();
          return;
        }
        files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' }));
        currentSeqFiles = files.map((file, idx) => ({ file, ordinal: idx }));
        byId('seq-ordering-section').style.display = 'block';
        if (!byId('seq-id').value && files.length > 0) {
          byId('seq-id').value = files[0].name.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9_-]/g, '-').slice(0, 32);
        }
        if (!byId('seq-name').value && files.length > 0) {
          byId('seq-name').value = byId('seq-id').value.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        }
        renderSeqTable();
      };
    }

    if (byId('seq-natural-sort')) {
      handle('seq-natural-sort', () => {
        currentSeqFiles.sort((a, b) => a.file.name.localeCompare(b.file.name, undefined, { numeric: true, sensitivity: 'base' }));
        currentSeqFiles.forEach((f, idx) => { f.ordinal = idx; });
        renderSeqTable();
      });
    }

    if (byId('import-sequence-btn')) {
      handle('import-sequence-btn', async () => {
        const seqId = byId('seq-id').value.trim();
        const seqName = byId('seq-name').value.trim() || seqId;
        if (!seqId) throw new Error('Sequence ID is required.');
        if (currentSeqFiles.length === 0) throw new Error('Select at least one PNG file.');
        byId('seq-status').textContent = 'Validating and staging frames...';
        const encode = async file => {
          if (!file || file.size > 32 * 1024 * 1024) throw new Error(`File ${file.name} exceeds 32 MiB.`);
          const a = new Uint8Array(await file.arrayBuffer());
          let raw = '';
          for (let i = 0; i < a.length; i += 8192) raw += String.fromCharCode(...a.subarray(i, i + 8192));
          return btoa(raw);
        };
        const frames = [];
        for (const item of currentSeqFiles) {
          frames.push({
            ordinal: item.ordinal,
            filename: item.file.name,
            data_base64: await encode(item.file),
          });
        }
        const result = await operation('stage-sequence', {
          sequence_id: seqId,
          name: seqName,
          frames: frames,
        });
        state.manifest = result.project;
        await loadRequirementsAndCoverage();
        updateProjectHeader();
        byId('seq-status').textContent = `Sequence '${seqId}' (${frames.length} frames) imported successfully. Original bytes immutable; unassigned.`;
        showSuccess(`Imported sequence '${seqId}' with ${frames.length} frames.`);
      });
    }

    if (byId('single-png-file')) {
      byId('single-png-file').onchange = (e) => {
        const file = e.target.files?.[0];
        byId('import-single-png-btn').style.display = file ? 'inline-block' : 'none';
      };
    }

    if (byId('import-single-png-btn')) {
      handle('import-single-png-btn', async () => {
        const file = byId('single-png-file').files?.[0];
        if (!file) throw new Error('Select a PNG file.');
        byId('single-png-status').textContent = 'Uploading and validating PNG...';
        const encode = async f => {
          if (f.size > 32 * 1024 * 1024) throw new Error('File exceeds 32 MiB.');
          const a = new Uint8Array(await f.arrayBuffer());
          let raw = '';
          for (let i = 0; i < a.length; i += 8192) raw += String.fromCharCode(...a.subarray(i, i + 8192));
          return btoa(raw);
        };
        const result = await operation('stage-png', {
          filename: file.name,
          data_base64: await encode(file),
        });
        state.manifest = result.project;
        await loadRequirementsAndCoverage();
        updateProjectHeader();
        byId('single-png-status').textContent = `Imported frame ${file.name}.`;
        showSuccess(`Imported frame ${file.name}.`);
      });
    }

    // Spritesheet Extraction
    let manualRectangles = [];
    const renderRectTable = () => {
      const container = byId('rectangles-table');
      if (!container) return;
      if (manualRectangles.length === 0) {
        container.innerHTML = '<p style="font-size:12px;color:var(--text-muted);margin:4px 0;">No rectangles defined. Click "Add rectangle" to create one.</p>';
        return;
      }
      container.innerHTML = '';
      manualRectangles.forEach((rect, idx) => {
        const row = document.createElement('div');
        row.style = 'display:grid;grid-template-columns:1fr 70px 70px 70px 70px 40px;gap:6px;align-items:center;margin-bottom:4px;';
        row.innerHTML = `
          <input type="text" placeholder="rect_id" value="${rect.id || ''}" style="font-size:12px;" data-field="id" data-idx="${idx}">
          <input type="number" min="0" placeholder="X" value="${rect.x ?? 0}" style="font-size:12px;" data-field="x" data-idx="${idx}">
          <input type="number" min="0" placeholder="Y" value="${rect.y ?? 0}" style="font-size:12px;" data-field="y" data-idx="${idx}">
          <input type="number" min="1" placeholder="W" value="${rect.width ?? 32}" style="font-size:12px;" data-field="width" data-idx="${idx}">
          <input type="number" min="1" placeholder="H" value="${rect.height ?? 32}" style="font-size:12px;" data-field="height" data-idx="${idx}">
          <button type="button" class="btn" style="padding:2px 6px;font-size:12px;" data-action="remove" data-idx="${idx}">✕</button>
        `;
        row.querySelectorAll('input').forEach(inp => {
          inp.oninput = (e) => {
            const f = e.target.dataset.field;
            const i = Number(e.target.dataset.idx);
            if (f === 'id') manualRectangles[i].id = e.target.value.trim();
            else manualRectangles[i][f] = Number(e.target.value);
          };
        });
        row.querySelector('[data-action="remove"]').onclick = () => {
          manualRectangles.splice(idx, 1);
          renderRectTable();
        };
        container.appendChild(row);
      });
    };

    if (byId('sheet-file')) {
      byId('sheet-file').onchange = (e) => {
        const file = e.target.files?.[0];
        if (!file) {
          byId('sheet-preview-container').style.display = 'none';
          byId('extraction-status').textContent = '';
          return;
        }
        const img = new Image();
        const url = URL.createObjectURL(file);
        img.onload = () => {
          URL.revokeObjectURL(url);
          byId('sheet-info').textContent = `Sheet: ${file.name} (${img.naturalWidth}×${img.naturalHeight} px, ${(file.size / 1024).toFixed(1)} KiB)`;
          byId('sheet-preview-container').style.display = 'block';
          if (!byId('extraction-id').value) {
            byId('extraction-id').value = file.name.replace(/\.[^/.]+$/, '').toLowerCase().replace(/[^a-z0-9_-]/g, '-').slice(0, 32);
          }
          if (manualRectangles.length === 0) {
            manualRectangles.push({ id: 'frame-0', x: 0, y: 0, width: Math.min(32, img.naturalWidth), height: Math.min(32, img.naturalHeight) });
            renderRectTable();
          }
        };
        img.onerror = () => {
          URL.revokeObjectURL(url);
          byId('sheet-preview-container').style.display = 'none';
          byId('extraction-status').textContent = 'Failed to load spritesheet image file.';
        };
        img.src = url;
      };
    }

    if (byId('mode-manual') && byId('mode-grid')) {
      byId('mode-manual').onchange = () => {
        byId('manual-rect-section').style.display = 'block';
        byId('grid-rect-section').style.display = 'none';
      };
      byId('mode-grid').onchange = () => {
        byId('manual-rect-section').style.display = 'none';
        byId('grid-rect-section').style.display = 'block';
      };
    }

    if (byId('add-rect-row-btn')) {
      byId('add-rect-row-btn').onclick = () => {
        const nextIdx = manualRectangles.length;
        manualRectangles.push({ id: `frame-${nextIdx}`, x: 0, y: 0, width: 32, height: 32 });
        renderRectTable();
      };
    }

    if (byId('clear-rect-rows-btn')) {
      byId('clear-rect-rows-btn').onclick = () => {
        manualRectangles = [];
        renderRectTable();
      };
    }

    if (byId('extract-spritesheet-btn')) {
      handle('extract-spritesheet-btn', async () => {
        const file = byId('sheet-file').files?.[0];
        if (!file) throw new Error('Select a spritesheet PNG file.');
        const isGrid = byId('mode-grid')?.checked;
        const extractionId = byId('extraction-id')?.value.trim();

        byId('extraction-status').textContent = 'Validating sheet and extracting rectangles...';
        const encode = async f => {
          if (f.size > 32 * 1024 * 1024) throw new Error('File exceeds 32 MiB.');
          const a = new Uint8Array(await f.arrayBuffer());
          let raw = '';
          for (let i = 0; i < a.length; i += 8192) raw += String.fromCharCode(...a.subarray(i, i + 8192));
          return btoa(raw);
        };

        const payload = {
          sheet_filename: file.name,
          sheet_data_base64: await encode(file),
        };
        if (extractionId) payload.extraction_id = extractionId;

        if (isGrid) {
          payload.grid = {
            cell_width: Number(byId('grid-cell-w').value),
            cell_height: Number(byId('grid-cell-h').value),
            cols: Number(byId('grid-cols').value),
            rows: Number(byId('grid-rows').value),
            offset_x: Number(byId('grid-offset-x').value || 0),
            offset_y: Number(byId('grid-offset-y').value || 0),
            spacing_x: Number(byId('grid-spacing-x').value || 0),
            spacing_y: Number(byId('grid-spacing-y').value || 0),
          };
          const prefix = byId('grid-prefix')?.value.trim();
          if (prefix) payload.grid.cell_id_prefix = prefix;
        } else {
          if (manualRectangles.length === 0) throw new Error('Specify at least one rectangle to extract.');
          payload.rectangles = manualRectangles.map((r, idx) => ({
            id: r.id || `rect-${idx}`,
            x: Number(r.x),
            y: Number(r.y),
            width: Number(r.width),
            height: Number(r.height),
            ordinal: idx,
          }));
        }

        const result = await operation('extract-spritesheet', payload);
        state.manifest = result.project;
        await loadRequirementsAndCoverage();
        updateProjectHeader();
        const msg = `Extracted ${result.extracted_count} frames from spritesheet. Original sheet and extracted frames immutable; unassigned.`;
        byId('extraction-status').textContent = msg;
        showSuccess(msg);
      });
    }

    // Transformation Recipes (RSF-21)
    let transformSteps = [];
    const renderTransformSteps = () => {
      const container = byId('transform-steps-list');
      if (!container) return;
      if (transformSteps.length === 0) {
        container.innerHTML = '<p style="font-size:12px;color:var(--text-muted);margin:4px 0;">No operations added. Click "Add operation step" to configure one.</p>';
        return;
      }
      container.innerHTML = '';
      transformSteps.forEach((step, idx) => {
        const row = document.createElement('div');
        row.style = 'border:1px solid var(--border-color);border-radius:4px;padding:6px;margin-bottom:6px;background:var(--bg-secondary);';

        let paramsHtml = '';
        if (step.op === 'crop') {
          paramsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:4px;margin-top:4px;">
              <div><label style="font-size:11px;">X</label><input type="number" min="0" value="${step.x ?? 0}" data-param="x" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Y</label><input type="number" min="0" value="${step.y ?? 0}" data-param="y" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Width</label><input type="number" min="1" value="${step.width ?? 32}" data-param="width" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Height</label><input type="number" min="1" value="${step.height ?? 32}" data-param="height" style="font-size:11px;"></div>
            </div>`;
        } else if (step.op === 'flip') {
          paramsHtml = `
            <div style="margin-top:4px;">
              <label style="font-size:11px;">Direction</label>
              <select data-param="direction" style="font-size:11px;">
                <option value="horizontal" ${step.direction === 'horizontal' ? 'selected' : ''}>Horizontal (FLIP_LEFT_RIGHT)</option>
                <option value="vertical" ${step.direction === 'vertical' ? 'selected' : ''}>Vertical (FLIP_TOP_BOTTOM)</option>
                <option value="both" ${step.direction === 'both' ? 'selected' : ''}>Both</option>
              </select>
            </div>`;
        } else if (step.op === 'scale') {
          paramsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:4px;">
              <div><label style="font-size:11px;">Width</label><input type="number" min="1" value="${step.width ?? 32}" data-param="width" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Height</label><input type="number" min="1" value="${step.height ?? 32}" data-param="height" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Filter</label>
                <select data-param="filter" style="font-size:11px;">
                  <option value="nearest" ${step.filter === 'nearest' ? 'selected' : ''}>Nearest (Pixel Art)</option>
                  <option value="bilinear" ${step.filter === 'bilinear' ? 'selected' : ''}>Bilinear</option>
                  <option value="bicubic" ${step.filter === 'bicubic' ? 'selected' : ''}>Bicubic</option>
                </select>
              </div>
            </div>`;
        } else if (step.op === 'offset') {
          paramsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr;gap:4px;margin-top:4px;">
              <div><label style="font-size:11px;">Offset X</label><input type="number" value="${step.offset_x ?? 0}" data-param="offset_x" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Offset Y</label><input type="number" value="${step.offset_y ?? 0}" data-param="offset_y" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Canvas W</label><input type="number" min="1" value="${step.canvas_width ?? ''}" placeholder="auto" data-param="canvas_width" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Canvas H</label><input type="number" min="1" value="${step.canvas_height ?? ''}" placeholder="auto" data-param="canvas_height" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Overflow</label>
                <select data-param="overflow" style="font-size:11px;">
                  <option value="clip" ${step.overflow === 'clip' ? 'selected' : ''}>Clip</option>
                  <option value="expand" ${step.overflow === 'expand' ? 'selected' : ''}>Expand</option>
                </select>
              </div>
            </div>`;
        } else if (step.op === 'matte_key') {
          const col = step.color || [255, 0, 255];
          paramsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;margin-top:4px;">
              <div><label style="font-size:11px;">Key Color (R,G,B)</label><input type="text" value="${col.join(',')}" data-param="color" placeholder="255,0,255" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Tolerance (0..255)</label><input type="number" min="0" max="255" value="${step.tolerance ?? 0}" data-param="tolerance" style="font-size:11px;"></div>
              <div><label style="font-size:11px;">Repl. Alpha (0..255)</label><input type="number" min="0" max="255" value="${step.replacement_alpha ?? 0}" data-param="replacement_alpha" style="font-size:11px;"></div>
            </div>`;
        } else if (step.op === 'color_mode') {
          paramsHtml = `
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:4px;">
              <div><label style="font-size:11px;">Target Mode</label>
                <select data-param="target_mode" style="font-size:11px;">
                  <option value="RGBA" ${step.target_mode === 'RGBA' ? 'selected' : ''}>RGBA</option>
                  <option value="RGB" ${step.target_mode === 'RGB' ? 'selected' : ''}>RGB (Discards Alpha)</option>
                  <option value="P" ${step.target_mode === 'P' ? 'selected' : ''}>P (Indexed 8-bit)</option>
                </select>
              </div>
              <div style="display:flex;align-items:center;margin-top:14px;">
                <label style="font-size:11px;"><input type="checkbox" data-param="dither" ${step.dither ? 'checked' : ''}> Dither</label>
              </div>
            </div>`;
        }

        row.innerHTML = `
          <div style="display:flex;align-items:center;justify-content:space-between;gap:6px;">
            <div style="display:flex;align-items:center;gap:6px;">
              <span style="font-weight:bold;font-size:11px;">#${idx + 1}</span>
              <select data-action="change-op" style="font-size:11px;">
                <option value="crop" ${step.op === 'crop' ? 'selected' : ''}>Crop</option>
                <option value="flip" ${step.op === 'flip' ? 'selected' : ''}>Flip</option>
                <option value="scale" ${step.op === 'scale' ? 'selected' : ''}>Scale</option>
                <option value="offset" ${step.op === 'offset' ? 'selected' : ''}>Offset / Canvas</option>
                <option value="matte_key" ${step.op === 'matte_key' ? 'selected' : ''}>Matte Key Color</option>
                <option value="color_mode" ${step.op === 'color_mode' ? 'selected' : ''}>Color Mode Conversion</option>
              </select>
            </div>
            <div style="display:flex;gap:4px;">
              <button type="button" class="btn" style="padding:2px 6px;font-size:11px;" data-action="up" ${idx === 0 ? 'disabled' : ''}>↑</button>
              <button type="button" class="btn" style="padding:2px 6px;font-size:11px;" data-action="down" ${idx === transformSteps.length - 1 ? 'disabled' : ''}>↓</button>
              <button type="button" class="btn" style="padding:2px 6px;font-size:11px;" data-action="remove">✕</button>
            </div>
          </div>
          ${paramsHtml}
        `;

        row.querySelector('[data-action="change-op"]').onchange = (e) => {
          const newOp = e.target.value;
          const defaults = {
            crop: { op: 'crop', x: 0, y: 0, width: 32, height: 32 },
            flip: { op: 'flip', direction: 'horizontal' },
            scale: { op: 'scale', width: 32, height: 32, filter: 'nearest' },
            offset: { op: 'offset', offset_x: 0, offset_y: 0, overflow: 'clip' },
            matte_key: { op: 'matte_key', color: [255, 0, 255], tolerance: 0, replacement_alpha: 0 },
            color_mode: { op: 'color_mode', target_mode: 'RGBA', dither: false },
          };
          transformSteps[idx] = defaults[newOp] || { op: newOp };
          renderTransformSteps();
        };

        const upBtn = row.querySelector('[data-action="up"]');
        if (upBtn) upBtn.onclick = () => {
          if (idx > 0) {
            const tmp = transformSteps[idx - 1];
            transformSteps[idx - 1] = transformSteps[idx];
            transformSteps[idx] = tmp;
            renderTransformSteps();
          }
        };

        const downBtn = row.querySelector('[data-action="down"]');
        if (downBtn) downBtn.onclick = () => {
          if (idx < transformSteps.length - 1) {
            const tmp = transformSteps[idx + 1];
            transformSteps[idx + 1] = transformSteps[idx];
            transformSteps[idx] = tmp;
            renderTransformSteps();
          }
        };

        row.querySelector('[data-action="remove"]').onclick = () => {
          transformSteps.splice(idx, 1);
          renderTransformSteps();
        };

        row.querySelectorAll('[data-param]').forEach(inp => {
          inp.onchange = (e) => {
            const param = e.target.dataset.param;
            if (param === 'color') {
              transformSteps[idx].color = e.target.value.split(',').map(s => Number(s.trim()));
            } else if (param === 'dither') {
              transformSteps[idx].dither = e.target.checked;
            } else if (e.target.type === 'number') {
              transformSteps[idx][param] = e.target.value === '' ? undefined : Number(e.target.value);
            } else {
              transformSteps[idx][param] = e.target.value;
            }
          };
          inp.oninput = inp.onchange;
        });

        container.appendChild(row);
      });
    };

    if (byId('add-transform-step-btn')) {
      byId('add-transform-step-btn').onclick = () => {
        transformSteps.push({ op: 'crop', x: 0, y: 0, width: 32, height: 32 });
        renderTransformSteps();
      };
    }

    if (byId('clear-transform-steps-btn')) {
      byId('clear-transform-steps-btn').onclick = () => {
        transformSteps = [];
        renderTransformSteps();
      };
    }

    const buildRecipePayload = () => {
      const srcSha = byId('transform-source')?.value;
      if (!srcSha) throw new Error('Select an input source image.');
      const rid = byId('transform-recipe-id')?.value.trim() || `recipe-${Date.now()}`;
      const rname = byId('transform-recipe-name')?.value.trim() || rid;
      if (transformSteps.length === 0) throw new Error('Add at least one transformation operation step.');
      return {
        id: rid,
        name: rname,
        source_sha256: srcSha,
        operations: transformSteps,
      };
    };

    if (byId('preview-transform-btn')) {
      handle('preview-transform-btn', async () => {
        const recipe = buildRecipePayload();
        byId('transform-status').textContent = 'Executing preview transformation...';
        const result = await operation('transform-preview', { recipe });
        byId('transform-preview-container').style.display = 'block';
        picture('transform-before-img', result.before_base64);
        picture('transform-after-img', result.after_base64);
        byId('transform-facts').textContent = pretty({
          recipe_id: result.recipe_id,
          source_sha256: result.source_sha256,
          derived_sha256: result.derived_sha256,
          input_dimensions: result.input_dimensions,
          output_dimensions: result.output_dimensions,
          input_mode: result.input_mode,
          output_mode: result.output_mode,
          transparency_kind: result.transparency_kind,
          loss_report: result.loss_report,
          recipe_sha256: result.recipe_sha256,
        });
        byId('transform-status').textContent = `Preview executed: ${result.output_dimensions[0]}×${result.output_dimensions[1]} px, mode ${result.output_mode}.`;
      });
    }

    if (byId('apply-transform-btn')) {
      handle('apply-transform-btn', async () => {
        const recipe = buildRecipePayload();
        byId('transform-status').textContent = 'Applying transformation and staging derived candidate...';
        const result = await operation('apply-transform', { recipe });
        state.manifest = result.project;
        await loadRequirementsAndCoverage();
        updateProjectHeader();
        const msg = `Staged derived candidate '${result.recipe.id}' (hash: ${result.derived_sha256.slice(0, 16)}...). Loss report: ${JSON.stringify(result.loss_report)}.`;
        byId('transform-status').textContent = msg;
        showSuccess(msg);
      });
    }
    byId('art-source').onchange=async()=>{
      const epoch=++interaction.sourceEpoch;
      const record=interaction.workspace?.sources.find(r=>r.source.id===byId('art-source').value);
      byId('source-facts').textContent=pretty(record || 'No source selected');picture('source-thumbnail',null);
      if(record) try {const r=await operation('source-preview',{source:record.source.id});if(epoch===interaction.sourceEpoch) picture('source-thumbnail',r.png_base64);}catch(err){if(epoch===interaction.sourceEpoch) showError(err.message);}
    };
    handle('assign-selected',()=>publishMappings([directMapping()]));
    handle('add-batch',()=>{const mappings=JSON.parse(byId('batch-mappings').value);mappings.push(directMapping());byId('batch-mappings').value=pretty(mappings);showSuccess('Explicit mapping added. Review and confirm the complete batch before publication.');});
    handle('assign-batch',()=>publishMappings(JSON.parse(byId('batch-mappings').value)));
    handle('assign-reuse',()=>{
      const source=interaction.workspace?.ledger?.assignments.find(a=>a.id===byId('reuse-assignment').value);
      if(!source) throw new Error('Select an existing source assignment.');
      return publishMappings([{requirement_id:destination(),kind:'EXPLICIT_REUSE',dependency:{id:source.id,revision:source.revision},recipe:byId('reuse-mirror').checked?[{id:'mirror',op:'mirror_x',version:1,parameters:{}}]:[]}]);
    });
    byId('preview-resource').onchange=updateActions;
    byId('preview-head').onchange=()=>{pausePlayback();renderSelection().catch(e=>showError(e.message));};
    byId('play-action').onchange=()=>{updateViews();renderSelection().catch(e=>showError(e.message));};
    byId('play-view').onchange=()=>{pausePlayback();interaction.elapsed=0;byId('play-frame').value=0;renderSelection().catch(e=>showError(e.message));};
    for(const id of ['play-speed','movement-speed','duration-ms']) byId(id).onchange=()=>{pausePlayback();interaction.elapsed=0;};
    byId('play-frame').oninput=()=>{pausePlayback();interaction.elapsed=0;renderSelection().catch(e=>showError(e.message));};
    handle('previous-frame',()=>{pausePlayback();interaction.elapsed=0;return renderSelection({step:-1});});
    handle('next-frame',()=>{pausePlayback();interaction.elapsed=0;return renderSelection({step:1});});
    handle('stop',()=>{pausePlayback();interaction.elapsed=0;return renderSelection({frame:0});});
    handle('pause',()=>pausePlayback());
    handle('play',()=>{if(interaction.playing)return;previewRequest();interaction.startFrame=Number(byId('play-frame').value);interaction.playing=true;interaction.started=performance.now();const epoch=++interaction.epoch;return playbackTick(epoch);});
    handle('compare-selected',async()=>{pausePlayback();picture('comparison-preview',null);byId('comparison-facts').textContent='';const r=await operation('compare',{...previewRequest(),candidate:byId('candidate-resource').value,mode:byId('compare-mode').value});picture('comparison-preview',r.png_base64);byId('comparison-facts').textContent=pretty(r.report);});

    // Deterministic ACT/SPR Compiler (RSF-23)
    const buildCompilePayload = () => {
      const resId = byId('compile-resource')?.value;
      if (!resId) throw new Error('Select a base ACT/SPR resource.');
      const resObj = interaction.workspace?.resources.find(r => r.id === resId);
      const payload = {
        resource_id: resId,
        part: resObj?.part || 'body',
        compilation_mode: byId('compile-mode')?.value || 'bounded_replacement',
        replacement_policy: byId('compile-policy')?.value || 'preserve_pool',
        isolation_strategy: byId('compile-isolation')?.value || 'auto',
      };
      const headId = byId('compile-head-resource')?.value;
      if (headId) payload.head_resource_id = headId;
      return payload;
    };

    if (byId('plan-compile-btn')) {
      handle('plan-compile-btn', async () => {
        const payload = buildCompilePayload();
        byId('compile-status').textContent = 'Building pre-compilation plan...';
        const plan = await operation('compile-plan', payload);
        byId('compile-facts').textContent = pretty(plan);
        const msg = plan.ready_to_compile
          ? `Plan READY (${plan.selected_replacements.length} replacement(s), mode=${plan.compilation_mode}, export_ready=${plan.export_ready}).`
          : `Plan BLOCKED (${plan.blockers.length} blocker(s): ${plan.blockers.join('; ')}).`;
        byId('compile-status').textContent = msg;
      });
    }

    if (byId('run-compile-btn')) {
      handle('run-compile-btn', async () => {
        const payload = buildCompilePayload();
        const compId = byId('compile-id')?.value.trim() || `compile-${Date.now()}`;
        payload.compilation_id = compId;
        const regId = byId('compile-register-resource')?.value.trim();
        if (regId) payload.register_resource_id = regId;
        byId('compile-status').textContent = 'Compiling modified ACT/SPR resources and running post-write verification...';
        const result = await operation('compile', payload);
        state.manifest = result.project;
        await loadRequirementsAndCoverage();
        updateProjectHeader();
        const cm = result.compilation;
        byId('compile-facts').textContent = pretty(cm);
        const msg = `Compiled '${cm.id}': ${cm.replacements.length} replacement(s), decode_after_write=${cm.verification.decode_after_write}, native_korangar=${cm.verification.native_korangar}, export_ready=${cm.status.export_ready}.`;
        byId('compile-status').textContent = msg;
        showSuccess(msg);
      });
    }

    // RSF-38: Setup preview zoom and background handlers
    const pZoom = byId('preview-zoom');
    if (pZoom) {
      pZoom.onchange = (e) => applyAnimZoom(Number(e.target.value));
    }
    const pBg = byId('preview-bg');
    if (pBg) {
      pBg.onchange = (e) => setPreviewBackground(e.target.value);
    }
    const aImg = byId('animation-preview');
    if (aImg) {
      aImg.addEventListener('load', () => applyAnimZoom());
    }
  }

  // App Initialization
  async function init() {
    initElements();
    setupListeners();
    setupInteractive();
    videoImport = window.createVideoImport({apiFetch, operation, endpoint,
      current: () => state.currentProject, refresh: () => loadProject(state.currentProject)});
    await loadCsrfToken();
    await refreshProjectsList();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
