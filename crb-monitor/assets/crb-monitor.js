/* CRB Damage Monitor — S-Paudel.github.io
 * Browses public palm photos (iNaturalist, Mapillary, Flickr, GBIF) live from their APIs,
 * shows the pipeline's analysis results (crb-monitor/data/results.json), and sends photos
 * for analysis by opening a pre-filled GitHub issue. Images are hot-linked, never stored.
 * Damage-detection method: Aubrey Moore, https://github.com/aubreymoore/CRB-2026-05-13
 */
(() => {
  'use strict';

  const REPO = 'S-Paudel/crb-monitor-private';   // private project repository: issues for links and reviews
  const DATA = 'crb-monitor/data/';
  const API = {
    inat: 'https://api.inaturalist.org/v1',
    gbif: 'https://api.gbif.org/v1',
    mly: 'https://graph.mapillary.com',
    flickr: 'https://api.flickr.com/services/rest/',
  };
  const INAT_CC = 'cc0,cc-by,cc-by-nc,cc-by-sa,cc-by-nd,cc-by-nc-sa,cc-by-nc-nd';
  const FLICKR_CC = '1,2,3,4,5,6,7,9,10';
  const FLICKR_LIC = { 0: 'all rights reserved', 1: 'CC BY-NC-SA 2.0', 2: 'CC BY-NC 2.0', 3: 'CC BY-NC-ND 2.0',
    4: 'CC BY 2.0', 5: 'CC BY-SA 2.0', 6: 'CC BY-ND 2.0', 7: 'no known copyright restrictions',
    8: 'US Government work', 9: 'CC0 1.0', 10: 'Public Domain Mark 1.0' };
  const GBIF_INAT_DATASET = '50c9509d-22c7-4a22-a47d-8c48425ef4a7';
  const MAX_ISSUE_LINKS = 30;
  const PAGE_SIZE = 60;

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const today = () => new Date().toISOString().slice(0, 10);
  const yearsAgo = n => { const d = new Date(); d.setFullYear(d.getFullYear() - n); return d.toISOString().slice(0, 10); };
  const ls = {
    get(k) { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
    set(k, v) { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* storage unavailable */ } },
  };

  const state = {
    regions: {}, items: [], byUid: new Map(), bySrc: new Map(), rejected: {}, log: [],
    selected: new Map(), maps: {}, layers: {}, entries: {}, sourceState: {},
  };

  // ------------------------------------------------------------------ data
  async function getJSON(url, opts) {
    const r = await fetch(url, opts);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  async function loadData() {
    const nc = { cache: 'no-cache' };
    const [regions, results, log, rejected] = await Promise.all([
      getJSON(DATA + 'regions.json', nc),
      getJSON(DATA + 'results.json', nc).catch(() => ({ items: [] })),
      getJSON(DATA + 'scan_log.json', nc).catch(() => []),
      getJSON(DATA + 'rejected.json', nc).catch(() => ({})),
    ]);
    state.regions = regions;   // { groups: {key: {name, members}}, areas: {ISO: {name, inat_place, bbox, …}} }
    state.items = results.items || [];
    state.log = log; state.rejected = rejected;
    for (const it of state.items) {
      state.byUid.set(it.uid, it);
      const k = `${it.source}:${it.source_id}`;
      if (!state.bySrc.has(k)) state.bySrc.set(k, []);
      state.bySrc.get(k).push(it);
    }
  }

  function statusOf(it) {
    if (!it) return 'none';
    if (it.status === 'analyzed') {
      return { candidate_damage: 'damage', no_damage_detected: 'clear', no_palm_found: 'nopalm' }[it.analysis?.verdict] || 'clear';
    }
    return { queued: 'queued', beetle_record: 'beetle', error: 'error' }[it.status] || 'none';
  }

  function badgeHTML(it, rejectedScore) {
    const st = statusOf(it);
    let label = {
      damage: `${it?.analysis?.n_cuts} cut${it?.analysis?.n_cuts === 1 ? '' : 's'} · possible damage`,
      clear: 'No cuts found', nopalm: 'No palm found', queued: 'Waiting for analysis',
      beetle: 'Beetle sighting', error: 'Analysis failed', none: 'Not screened',
    }[st];
    if (st === 'none' && rejectedScore !== undefined) label = 'Screened · no palm';
    let html = `<span class="badge ${st === 'none' && rejectedScore !== undefined ? 'nopalm' : st}">${esc(label)}</span>`;
    if (it?.review) html += ` <span class="badge review">${esc(it.review.decision)}</span>`;
    return html;
  }

  /** Best stored result for a browsed entry (by source id, or the iNaturalist id behind a GBIF record). */
  function resultFor(entry) {
    const lists = [state.bySrc.get(`${entry.source}:${entry.sourceId}`), entry.inatId && state.bySrc.get(`inaturalist:${entry.inatId}`)]
      .filter(Boolean).flat();
    const rank = { damage: 0, clear: 1, nopalm: 2, queued: 3, beetle: 4, error: 5, none: 6 };
    return lists.sort((a, b) => rank[statusOf(a)] - rank[statusOf(b)])[0];
  }

  /** Palm-check score if the pipeline already looked at this photo and found no palm. */
  function rejectedFor(entry) {
    if (!state.rejBySrc) {
      state.rejBySrc = new Map();
      for (const [uid, v] of Object.entries(state.rejected)) state.rejBySrc.set(uid.split(':').slice(0, 2).join(':'), v[1]);
    }
    const k = `${entry.source}:${entry.sourceId}`;
    return state.rejBySrc.has(k) ? state.rejBySrc.get(k) : undefined;
  }

  // ------------------------------------------------------------------ stats + regions
  function renderStats() {
    const analysed = state.items.filter(i => i.status === 'analyzed');
    const dmg = analysed.filter(i => i.analysis?.verdict === 'candidate_damage');
    const conf = state.items.filter(i => i.review?.decision === 'confirmed');
    const screened = state.items.length + Object.keys(state.rejected).length;
    const lastScan = [...state.log].reverse().find(e => e.command === 'scan');
    $('#crbStats').innerHTML = [
      `<span><b>${screened.toLocaleString()}</b>photos screened</span>`,
      `<span><b>${analysed.length.toLocaleString()}</b>analysed</span>`,
      `<span class="dmg"><b>${dmg.length.toLocaleString()}</b>possible damage</span>`,
      `<span><b>${conf.length.toLocaleString()}</b>confirmed</span>`,
      `<span><b>${state.items.filter(i => i.status === 'queued').length}</b>waiting</span>`,
      `<span>last scan <b>${lastScan ? esc(lastScan.finished.slice(0, 10)) : '—'}</b></span>`,
    ].join('');
  }

  /** Region select: watch groups first, then single countries grouped under them. */
  function fillRegionSelect(sel, groups) {
    const { groups: G, areas: A } = state.regions;
    const keys = groups || Object.keys(G);
    const opts = sel.dataset.regions === 'all' ? ['<option value="">All regions</option>'] : [];
    opts.push('<optgroup label="Regions">' + keys.map(k => `<option value="${esc(k)}">${esc(G[k].name)}</option>`).join('') + '</optgroup>');
    for (const k of keys) {
      if (G[k].members.length < 2) continue;
      const members = [...G[k].members].sort((a, b) => A[a].name.localeCompare(A[b].name));
      opts.push(`<optgroup label="${esc(G[k].name)}">` + members.map(m => `<option value="${esc(m)}">${esc(A[m].name)}</option>`).join('') + '</optgroup>');
    }
    sel.innerHTML = opts.join('');
  }
  /** The countries (areas) behind a group or area key. */
  function areasOf(key) {
    const { groups: G, areas: A } = state.regions;
    if (G[key]) return G[key].members.map(m => ({ key: m, ...A[m] }));
    return A[key] ? [{ key, ...A[key] }] : [];
  }
  function regionBBox(key) {
    const bb = areasOf(key).map(a => a.bbox);
    return bb.length ? [Math.min(...bb.map(b => b[0])), Math.min(...bb.map(b => b[1])), Math.max(...bb.map(b => b[2])), Math.max(...bb.map(b => b[3]))] : null;
  }
  function inatPlaceParams(key) {
    const areas = areasOf(key);
    const out = { place_id: areas.map(a => a.inat_place).join(',') };
    const excl = [...new Set(areas.flatMap(a => a.inat_not_in_place || []))];
    if (excl.length) out.not_in_place = excl.join(',');
    return out;
  }
  window.CRB = Object.assign(window.CRB || {}, { areasOf, regionBBox, inatPlaceParams, getRegions: () => state.regions });

  // ------------------------------------------------------------------ maps
  const COLORS = { damage: '#FF8A3D', clear: '#D6F24C', queued: '#7FC8F8', nopalm: '#7C8274', beetle: '#E7A6F0', error: '#F06C6C', none: '#F5F2E9' };

  function getMap(name, el) {
    if (state.maps[name]) return state.maps[name];
    if (typeof L === 'undefined') { el.innerHTML = '<p class="crb-empty">Map unavailable.</p>'; return null; }
    const map = L.map(el, { worldCopyJump: true, scrollWheelZoom: false }).setView([10, -75], 3);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, className: 'crb-tiles',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' }).addTo(map);
    state.layers[name] = L.layerGroup().addTo(map);
    state.maps[name] = map;
    return map;
  }

  function plot(name, entries, fit) {
    const map = state.maps[name];
    if (!map) return;
    const layer = state.layers[name];
    layer.clearLayers();
    const pts = [];
    for (const e of entries) {
      if (e.lat == null || e.lon == null) continue;
      const st = e.result ? statusOf(e.result) : 'none';
      const m = L.circleMarker([e.lat, e.lon], { radius: st === 'damage' ? 7 : 5, color: COLORS[st], weight: 1.5, fillOpacity: 0.65 });
      m.bindPopup(`<strong>${esc(e.title)}</strong><br>${esc(e.date || '')}<br><a href="#" data-open="${esc(e.key)}">Open photo</a>`);
      m.on('popupopen', ev => { const a = ev.popup.getElement().querySelector('[data-open]'); if (a) a.onclick = x => { x.preventDefault(); openViewer(e); }; });
      layer.addLayer(m); pts.push([e.lat, e.lon]);
    }
    if (fit && pts.length) map.fitBounds(L.latLngBounds(pts).pad(0.15), { maxZoom: 14 });
  }

  function fitRegion(name, key) {
    const map = state.maps[name], bb = regionBBox(key);
    if (map && bb) { const [w, s, e, n] = bb; map.fitBounds([[s, w], [n, e]]); }
  }

  function bboxFor(name, regionKey) {
    if (regionKey && regionKey !== '__map' && regionBBox(regionKey)) return regionBBox(regionKey);
    const b = state.maps[name]?.getBounds();
    if (!b) return regionBBox('caribbean');
    const w = Math.max(-180, b.getWest()), e = Math.min(180, b.getEast());
    return [w, Math.max(-90, b.getSouth()), e, Math.min(90, b.getNorth())].map(v => +v.toFixed(5));
  }

  // ------------------------------------------------------------------ cards
  function entryFromItem(it) {
    return {
      key: it.uid, source: it.source, sourceId: it.source_id, title: it.label || it.source, date: it.observed_on,
      lat: it.lat, lon: it.lon, thumb: it.thumb_url, image: it.image_url, page: it.page_url,
      license: it.license, attribution: it.attribution, result: it, fromResults: true,
    };
  }

  function cardHTML(e) {
    const it = e.result;
    const sel = state.selected.has(e.key);
    const meta = [e.date, e.place || (e.lat != null ? `${(+e.lat).toFixed(3)}, ${(+e.lon).toFixed(3)}` : ''), sourceName(e.source)]
      .filter(Boolean).join(' · ');
    const seen = it?.first_seen ? `<p class="crb-card-meta">first seen ${esc(it.first_seen)}</p>` : '';
    const canSend = !it || ['none', 'error'].includes(statusOf(it));
    return `<article class="crb-card${sel ? ' selected' : ''}" data-key="${esc(e.key)}">
      <button class="crb-thumb" type="button" data-view aria-label="Open ${esc(e.title)}">
        ${thumbImg(e)}
        ${badgeHTML(it, it ? undefined : e.rejected)}
      </button>
      <div class="crb-card-body">
        <p class="crb-card-title" title="${esc(e.title)}">${esc(e.title)}</p>
        <p class="crb-card-meta">${esc(meta)}</p>${seen}
        <div class="crb-card-foot">
          <a href="${esc(e.page)}" target="_blank" rel="noopener">Source ↗</a>
          ${canSend ? `<label class="crb-pick"><input type="checkbox" data-pick ${sel ? 'checked' : ''}> analyse</label>` : ''}
        </div>
      </div>
    </article>`;
  }

  function thumbImg(e) {
    if (e.source === 'mapillary' && e.fromResults) {
      return `<img alt="" loading="lazy" data-mly="${esc(e.sourceId)}" hidden><span class="ph">Mapillary image ${esc(e.sourceId)}<br>${ls.get('crb.mapillaryToken') ? 'loading…' : 'add a Mapillary token to preview'}</span>`;
    }
    if (!e.thumb) return '<span class="ph">no preview</span>';
    const fb = e.image && e.image !== e.thumb ? ` data-fallback="${esc(e.image)}"` : '';
    return `<img src="${esc(e.thumb)}" alt="" loading="lazy" referrerpolicy="no-referrer"${fb}>`;
  }

  function wireImages(root) {
    $$('img[data-fallback]', root).forEach(img => img.addEventListener('error', () => {
      if (img.dataset.fallback && img.src !== img.dataset.fallback) { img.src = img.dataset.fallback; img.dataset.fallback = ''; }
    }, { once: false }));
    const token = ls.get('crb.mapillaryToken');
    if (token) $$('img[data-mly]', root).forEach(async img => {
      try {
        const d = await getJSON(`${API.mly}/${img.dataset.mly}?fields=thumb_256_url,thumb_2048_url&access_token=${encodeURIComponent(token)}`);
        img.src = d.thumb_256_url; img.hidden = false; img.nextElementSibling?.remove();
        const e = findEntry(img.closest('[data-key]')?.dataset.key);
        if (e) e.image = d.thumb_2048_url;
      } catch { /* leave placeholder */ }
    });
  }

  function sourceName(s) { return { inaturalist: 'iNaturalist', mapillary: 'Mapillary', flickr: 'Flickr', gbif: 'GBIF', link: 'Link' }[s] || s; }

  function renderGrid(grid, entries, append = false) {
    const html = entries.map(cardHTML).join('');
    if (append) grid.insertAdjacentHTML('beforeend', html); else grid.innerHTML = html || '<p class="crb-empty">Nothing matches these filters yet.</p>';
    wireImages(grid);
  }

  function findEntry(key) {
    for (const list of Object.values(state.entries)) { const e = list.find(x => x.key === key); if (e) return e; }
    const it = state.byUid.get(key);
    return it ? entryFromItem(it) : null;
  }

  document.addEventListener('click', ev => {
    const card = ev.target.closest('.crb-card');
    if (!card) return;
    if (ev.target.closest('[data-view]')) { const e = findEntry(card.dataset.key); if (e) openViewer(e); }
  });
  document.addEventListener('change', ev => {
    if (!ev.target.matches('[data-pick]')) return;
    const card = ev.target.closest('.crb-card'), e = findEntry(card.dataset.key);
    if (!e) return;
    if (ev.target.checked) state.selected.set(e.key, { url: e.page || e.image, title: e.title });
    else state.selected.delete(e.key);
    card.classList.toggle('selected', ev.target.checked);
    renderTray();
  });

  // ------------------------------------------------------------------ GitHub issues
  function issueURL(title, body) {
    return `https://github.com/${REPO}/issues/new?title=${encodeURIComponent(title)}&body=${encodeURIComponent(body)}`;
  }
  function sendLinks(urls) {
    const list = [...new Set(urls.filter(Boolean))];
    if (!list.length) return;
    if (list.length > MAX_ISSUE_LINKS) {
      alert(`Please send at most ${MAX_ISSUE_LINKS} links at a time (you selected ${list.length}).`);
      return;
    }
    const body = `<!-- crb-monitor:link -->\nPlease analyse these photos for CRB damage:\n\n${list.join('\n')}\n\n_Sent from ${location.origin}${location.pathname}_`;
    window.open(issueURL(`[CRB link] ${list.length} photo${list.length > 1 ? 's' : ''} for analysis`, body), '_blank', 'noopener');
  }
  function sendReview(it, decision) {
    const body = `<!-- crb-monitor:review -->\nuid: ${it.uid}\ndecision: ${decision}\nnote: \n\nPhoto: ${it.page_url}\n\n_(Add a note on the "note:" line if you like, then submit.)_`;
    window.open(issueURL(`[CRB review] ${decision}: ${it.uid}`, body), '_blank', 'noopener');
  }

  function renderTray() {
    const n = state.selected.size;
    $('#tray').hidden = n === 0;
    $('#trayCount').textContent = `${n} photo${n === 1 ? '' : 's'} selected`;
  }
  $('#trayClear').onclick = () => { state.selected.clear(); $$('[data-pick]').forEach(c => { c.checked = false; c.closest('.crb-card')?.classList.remove('selected'); }); renderTray(); };
  $('#traySend').onclick = () => sendLinks([...state.selected.values()].map(v => v.url));

  // ------------------------------------------------------------------ viewer
  async function openViewer(e) {
    const dlg = $('#viewer'), it = e.result;
    let img = e.image || e.thumb;
    if (e.source === 'mapillary' && (!img || e.fromResults)) {
      const token = ls.get('crb.mapillaryToken');
      if (token) {
        try { img = (await getJSON(`${API.mly}/${e.sourceId}?fields=thumb_2048_url&access_token=${encodeURIComponent(token)}`)).thumb_2048_url; } catch { /* keep */ }
      } else img = '';
    }
    const a = it?.analysis;
    let overlay = '';
    if (a) {
      const pts = p => p.map(([x, y]) => `${x},${y}`).join(' ');
      overlay = `<svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">${a.palms.map(pm =>
        `<polygon class="palm${pm.touches_edge ? ' edge' : ''}" points="${pts(pm.poly)}"/>` +
        pm.cuts.map(c => `<polygon class="cut${c.counted ? '' : ' ignored'}" points="${pts(c.poly)}"/>`).join('')).join('')}</svg>`;
    }
    $('#viewerFigure').innerHTML = img
      ? `<div class="crb-overlay-wrap"><img src="${esc(img)}" alt="${esc(e.title)}" referrerpolicy="no-referrer">${overlay}</div>`
      : `<p class="crb-empty" style="padding:40px">Preview needs a Mapillary token (see the Mapillary tab).<br><a href="${esc(e.page)}" target="_blank" rel="noopener">Open on Mapillary ↗</a></p>`;

    const rows = [
      ['Source', `<a href="${esc(e.page)}" target="_blank" rel="noopener">${esc(sourceName(e.source))} ↗</a>`],
      ['Taken', esc(e.date || '—')],
      it?.first_seen && ['First seen', esc(it.first_seen)],
      e.lat != null && ['Location', `${(+e.lat).toFixed(5)}, ${(+e.lon).toFixed(5)}`],
      ['Licence', esc(e.license || '—')],
      ['Credit', esc(e.attribution || '—')],
      it?.palm_score != null && ['Palm check', `${Math.round(it.palm_score * 100)}% palm (CLIP)`],
      a && ['Palms found', esc(a.n_palms)],
      a && ['V-cuts counted', esc(a.n_cuts)],
      a && ['Detector', `${esc(a.detector)}${a.cut_filter === 'none' ? ' — <em>no cut classifier; counts include frond gaps</em>' : ''}`],
      a && ['Analysed', `${esc((a.analysed_at || '').slice(0, 10))}${a.seconds ? ` · ${esc(a.seconds)} s` : ''}`],
      it?.review && ['Review', `${esc(it.review.decision)} by ${esc(it.review.by || '—')} on ${esc(it.review.on)}`],
      it?.error && ['Error', esc(it.error)],
    ].filter(Boolean);
    const st = statusOf(it);
    const actions = it && it.status === 'analyzed'
      ? `<div class="crb-review">
           <button class="crb-btn-ghost confirm" data-rev="confirmed">Confirm damage</button>
           <button class="crb-btn-ghost" data-rev="rejected">Not CRB damage</button>
           <button class="crb-btn-ghost" data-rev="unsure">Unsure</button>
         </div><p class="crb-note">Project members only: opens a short issue in the private project repository that records your decision.</p>`
      : (['none', 'error'].includes(st) ? `<button class="btn btn-primary" data-send>Send for analysis</button>` : '');
    $('#viewerMeta').innerHTML = `
      <div>${badgeHTML(it, it ? undefined : e.rejected)}</div>
      <h3>${esc(e.title)}</h3>
      ${a ? `<div class="crb-legend"><span><i style="border:2px solid #D6F24C"></i>palm outline</span><span><i style="background:#FF8A3D"></i>counted V-cut</span><span><i style="border:1px dashed #999"></i>not counted</span></div>` : ''}
      <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      ${actions}
      <p class="crb-note">Automated screening only. V-cuts can also come from wind, other pests or
        pruning, so please confirm by eye.</p>`;
    $$('[data-rev]', dlg).forEach(b => b.onclick = () => sendReview(it, b.dataset.rev));
    const send = $('[data-send]', dlg); if (send) send.onclick = () => sendLinks([e.page || e.image]);
    if (!dlg.open) dlg.showModal();
    if (it) history.replaceState(null, '', `#item=${encodeURIComponent(it.uid)}`);
  }
  $('#viewerClose').onclick = () => $('#viewer').close();
  $('#viewer').addEventListener('click', ev => { if (ev.target.id === 'viewer') ev.target.close(); });
  $('#viewer').addEventListener('close', () => { if (location.hash.startsWith('#item=')) history.replaceState(null, '', location.pathname + `#tab=${currentTab}`); });

  // ------------------------------------------------------------------ results tab
  let resShown = 0, resFiltered = [];
  function filterResults() {
    const f = Object.fromEntries(new FormData($('#resFilters')));
    resFiltered = state.items.filter(it => {
      const st = statusOf(it);
      const okStatus = {
        damage: st === 'damage', all_analyzed: it.status === 'analyzed', clear: st === 'clear', no_palm: st === 'nopalm',
        queued: st === 'queued', beetle: st === 'beetle', everything: true,
      }[f.status];
      if (!okStatus) return false;
      if (f.source && it.source !== f.source) return false;
      if (f.region && it.region !== f.region && !areasOf(f.region).some(a => a.key === it.area)) return false;
      if (f.since && (it.first_seen || '') < f.since) return false;
      if (f.review === 'none' && it.review) return false;
      if (f.review && f.review !== 'none' && it.review?.decision !== f.review) return false;
      return true;
    }).map(entryFromItem);
    state.entries.results = resFiltered;
    const total = state.items.length;
    $('#resCount').textContent = total
      ? `${resFiltered.length.toLocaleString()} of ${total.toLocaleString()} records`
      : 'No results yet. They appear here after the first scheduled scan, or after you send photos for analysis.';
    resShown = 0;
    $('#grid-results').innerHTML = '';
    showMoreResults();
    getMap('results', $('#map-results'));
    plot('results', resFiltered, true);
  }
  function showMoreResults() {
    const next = resFiltered.slice(resShown, resShown + 120);
    renderGrid($('#grid-results'), next, resShown > 0);
    if (!resFiltered.length && state.items.length) $('#grid-results').innerHTML = '<p class="crb-empty">Nothing matches these filters.</p>';
    resShown += next.length;
    let more = $('#resMore');
    if (resShown < resFiltered.length) {
      if (!more) { more = document.createElement('button'); more.id = 'resMore'; more.className = 'crb-btn-ghost crb-more'; more.textContent = 'Show more'; more.onclick = showMoreResults; $('#grid-results').after(more); }
    } else more?.remove();
  }
  $('#resFilters').addEventListener('change', filterResults);
  $('#csvBtn').onclick = () => {
    const cols = ['uid', 'source', 'page_url', 'image_url', 'lat', 'lon', 'observed_on', 'first_seen', 'region', 'status',
      'verdict', 'n_palms', 'n_cuts', 'palm_score', 'review', 'license', 'attribution'];
    const rows = resFiltered.map(e => { const it = e.result, a = it.analysis || {};
      return [it.uid, it.source, it.page_url, it.image_url, it.lat, it.lon, it.observed_on, it.first_seen, it.region, it.status,
        a.verdict, a.n_palms, a.n_cuts, it.palm_score, it.review?.decision, it.license, it.attribution]; });
    const csv = [cols, ...rows].map(r => r.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `crb-monitor-${today()}.csv` });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  // ------------------------------------------------------------------ source adapters
  const taxonCache = {};
  async function inatTaxon(name) {
    if (!taxonCache['i' + name]) {
      const d = await getJSON(`${API.inat}/taxa?q=${encodeURIComponent(name)}&per_page=30`);
      const t = d.results.find(x => x.name.toLowerCase() === name.toLowerCase());
      if (!t) throw new Error(`iNaturalist taxon not found: ${name}`);
      taxonCache['i' + name] = t.id;
    }
    return taxonCache['i' + name];
  }
  async function gbifTaxon(name) {
    if (!taxonCache['g' + name]) {
      const d = await getJSON(`${API.gbif}/species/match?name=${encodeURIComponent(name)}`);
      if (!d.usageKey) throw new Error(`GBIF taxon not found: ${name}`);
      taxonCache['g' + name] = d.usageKey;
    }
    return taxonCache['g' + name];
  }
  const inatSize = (u, size) => u.replace(/\/(square|small|medium|large|original|thumb)\./, `/${size}.`);
  /** MD5 (for GBIF's image-cache URLs, which are keyed by the MD5 of the original image URL). */
  function md5(str) {
    const bytes = new TextEncoder().encode(str);
    const n = ((bytes.length + 8) >>> 6) + 1, words = new Uint32Array(n * 16);
    bytes.forEach((b, i) => { words[i >> 2] |= b << ((i % 4) * 8); });
    words[bytes.length >> 2] |= 0x80 << ((bytes.length % 4) * 8);
    words[n * 16 - 2] = bytes.length * 8;
    const S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21];
    const K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0);
    let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476;
    for (let o = 0; o < words.length; o += 16) {
      let a = a0, b = b0, c = c0, d = d0;
      for (let i = 0; i < 64; i++) {
        const r = i >> 4;
        let f, g;
        if (r === 0) { f = (b & c) | (~b & d); g = i; }
        else if (r === 1) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16; }
        else if (r === 2) { f = b ^ c ^ d; g = (3 * i + 5) % 16; }
        else { f = c ^ (b | ~d); g = (7 * i) % 16; }
        const tmp = d; d = c; c = b;
        const x = (a + f + K[i] + words[o + g]) >>> 0, s = S[r * 4 + (i % 4)];
        b = (b + ((x << s) | (x >>> (32 - s)))) >>> 0; a = tmp;
      }
      a0 = (a0 + a) >>> 0; b0 = (b0 + b) >>> 0; c0 = (c0 + c) >>> 0; d0 = (d0 + d) >>> 0;
    }
    return [a0, b0, c0, d0].map(v => [0, 8, 16, 24].map(sh => ((v >>> sh) & 255).toString(16).padStart(2, '0')).join('')).join('');
  }
  const gbifThumb = (occKey, u) => `${API.gbif}/image/cache/500x/occurrence/${occKey}/media/${md5(u)}`;

  function jsonp(url) {
    return new Promise((resolve, reject) => {
      const cb = `crbcb${Date.now()}${Math.floor(Math.random() * 1e6)}`;
      const s = document.createElement('script');
      const done = () => { delete window[cb]; s.remove(); };
      window[cb] = d => { done(); resolve(d); };
      s.onerror = () => { done(); reject(new Error('Flickr request failed')); };
      s.src = `${url}&jsoncallback=${cb}`;
      document.head.append(s);
      setTimeout(() => { if (window[cb]) { done(); reject(new Error('Flickr request timed out')); } }, 20000);
    });
  }
  async function flickrCall(params) {
    const qs = new URLSearchParams({ ...params, format: 'json' });
    try { return await getJSON(`${API.flickr}?${qs}&nojsoncallback=1`); } catch { return jsonp(`${API.flickr}?${qs}`); }
  }

  function thinEntries(list, metres = 150) {
    const seen = new Set();
    return list.filter(e => {
      const dLat = metres / 111320, dLon = metres / (111320 * Math.max(0.1, Math.cos(e.lat * Math.PI / 180)));
      const k = `${e.date}:${Math.floor(e.lat / dLat)}:${Math.floor(e.lon / dLon)}`;
      if (seen.has(k)) return false; seen.add(k); return true;
    });
  }

  const SOURCES = {
    inaturalist: {
      intro: 'Live search of iNaturalist photos in the surveillance regions. <strong>Pre-select</strong> limits results to records identified as coconut palm or all palms. <strong>Added since</strong> shows only records uploaded after a date, so you can check what is new. Tick photos to send them for damage analysis.',
      fields: { taxon: true, text: false, added: true, cc: true },
      async search(f, page) {
        const q = new URLSearchParams({ taxon_id: await inatTaxon(f.taxon), ...inatPlaceParams(f.region),
          photos: 'true', per_page: PAGE_SIZE, page, order_by: 'created_at', order: 'desc' });
        if (f.d1) q.set('d1', f.d1); if (f.d2) q.set('d2', f.d2);
        if (f.added) q.set('created_d1', f.added);
        if (f.cc) q.set('photo_license', INAT_CC);
        const d = await getJSON(`${API.inat}/observations?${q}`);
        const entries = d.results.filter(o => o.photos?.length).map(o => {
          const p = o.photos[0], c = o.geojson?.coordinates || [];
          return { key: `inaturalist:${o.id}`, source: 'inaturalist', sourceId: String(o.id),
            title: o.taxon?.preferred_common_name ? `${o.taxon.preferred_common_name} (${o.taxon.name})` : (o.taxon?.name || 'Unidentified'),
            date: o.observed_on, place: o.place_guess, lat: c[1], lon: c[0],
            thumb: inatSize(p.url, 'medium'), image: inatSize(p.url, 'large'), page: o.uri || `https://www.inaturalist.org/observations/${o.id}`,
            license: p.license_code || 'all rights reserved', attribution: p.attribution };
        });
        return { entries, total: d.total_results, more: page * PAGE_SIZE < d.total_results };
      },
    },
    gbif: {
      intro: 'Live search of GBIF occurrence records that have photos, from herbaria, museums, survey datasets and citizen science. Records that GBIF re-publishes from iNaturalist are marked.',
      fields: { taxon: true, text: false, added: false, cc: false },
      async search(f, page) {
        const [w, s, e, n] = f.bbox;
        const q = new URLSearchParams({ taxonKey: await gbifTaxon(f.taxon), mediaType: 'StillImage', hasCoordinate: 'true',
          decimalLatitude: `${s},${n}`, decimalLongitude: `${w},${e}`, limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE });
        if (f.d1 || f.d2) q.set('eventDate', `${f.d1 || '1900-01-01'},${f.d2 || today()}`);
        const d = await getJSON(`${API.gbif}/occurrence/search?${q}`);
        const entries = d.results.map(o => {
          const m = (o.media || []).find(x => x.type === 'StillImage' && x.identifier);
          const fromInat = o.datasetKey === GBIF_INAT_DATASET;
          const inatId = fromInat ? (String(o.references || '').match(/observations\/(\d+)/) || [])[1] : undefined;
          return m && { key: `gbif:${o.key}`, source: 'gbif', sourceId: String(o.key), inatId,
            title: (o.vernacularName ? `${o.vernacularName} (${o.scientificName})` : o.scientificName) + (fromInat ? ' · via iNaturalist' : ''),
            date: (o.eventDate || '').slice(0, 10), place: [o.locality, o.country].filter(Boolean).join(', '),
            lat: o.decimalLatitude, lon: o.decimalLongitude, thumb: gbifThumb(o.key, m.identifier), image: m.identifier,
            page: `https://www.gbif.org/occurrence/${o.key}`, license: m.license || o.license,
            attribution: m.rightsHolder || m.creator || o.recordedBy || o.datasetName };
        }).filter(Boolean);
        return { entries, total: d.count, more: !d.endOfRecords };
      },
    },
    mapillary: {
      intro: 'Street-level photos from Mapillary, the closest public match to Aubrey Moore\'s roadside surveys. Mapillary only allows small search boxes, so zoom the map in to a few kilometres, choose <strong>Current map view</strong>, and search. Images are thinned to one per ~150 m per day. Mapillary has no plant filter, so the palm check happens later, in the analysis pipeline.',
      key: { store: 'crb.mapillaryToken', label: 'Mapillary client token', hint: 'Free: sign in at mapillary.com → Dashboard → Developers → Register application, then copy the <em>client token</em>. It is saved only in this browser.' },
      fields: { taxon: false, text: false, added: false, cc: false },
      async search(f) {
        const token = ls.get('crb.mapillaryToken');
        if (!token) throw new Error('Add a Mapillary client token above to browse Mapillary.');
        const [w, s, e, n] = f.bbox, step = 0.1;
        const tiles = [];
        for (let x = w; x < e; x += step) for (let y = s; y < n; y += step) tiles.push([x, y, Math.min(e, x + step), Math.min(n, y + step)]);
        if (tiles.length > 25) throw new Error(`That area needs ${tiles.length} separate Mapillary searches. Zoom the map in, choose "Current map view" and search again. (The scheduled scan covers whole regions.)`);
        const out = [];
        for (const t of tiles) {
          const q = new URLSearchParams({ access_token: token, bbox: t.map(v => v.toFixed(5)).join(','), is_pano: 'false', limit: 500,
            fields: 'id,captured_at,computed_geometry,geometry,thumb_256_url,thumb_1024_url,creator' });
          if (f.d1) q.set('start_captured_at', `${f.d1}T00:00:00Z`);
          if (f.d2) q.set('end_captured_at', `${f.d2}T23:59:59Z`);
          const d = await getJSON(`${API.mly}/images?${q}`);
          for (const im of d.data || []) {
            const g = (im.computed_geometry || im.geometry)?.coordinates; if (!g) continue;
            out.push({ key: `mapillary:${im.id}`, source: 'mapillary', sourceId: String(im.id), title: `Street view ${im.id}`,
              date: im.captured_at ? new Date(im.captured_at).toISOString().slice(0, 10) : '', lat: g[1], lon: g[0],
              thumb: im.thumb_256_url, image: im.thumb_1024_url, page: `https://www.mapillary.com/app/?pKey=${im.id}`,
              license: 'CC BY-SA 4.0', attribution: `© ${im.creator?.username || 'Mapillary contributor'}, Mapillary` });
          }
        }
        const thinned = thinEntries(out).slice(0, 400);
        return { entries: thinned, total: thinned.length, more: false, note: `${out.length} images found, ${thinned.length} after thinning` };
      },
    },
    flickr: {
      intro: 'Geotagged Flickr photos matching your search words. Only openly licensed photos are shown unless you untick that box. Flickr has no plant filter, so the palm check happens later, in the analysis pipeline.',
      key: { store: 'crb.flickrKey', label: 'Flickr API key', hint: 'Free for non-commercial use: flickr.com/services/apps/create. It is saved only in this browser.' },
      fields: { taxon: false, text: true, added: true, cc: true },
      async search(f, page) {
        const key = ls.get('crb.flickrKey');
        if (!key) throw new Error('Add a Flickr API key above to browse Flickr.');
        const p = { method: 'flickr.photos.search', api_key: key, text: f.text || 'coconut palm', bbox: f.bbox.join(','),
          has_geo: 1, content_types: 0, sort: 'date-posted-desc', per_page: PAGE_SIZE, page,
          extras: 'geo,date_taken,owner_name,license,url_m,url_z,url_l' };
        if (f.d1) p.min_taken_date = `${f.d1} 00:00:00`;
        if (f.d2) p.max_taken_date = `${f.d2} 23:59:59`;
        if (f.added) p.min_upload_date = f.added;
        if (f.cc) p.license = FLICKR_CC;
        const d = await flickrCall(p);
        if (d.stat !== 'ok') throw new Error(d.message || 'Flickr error');
        const entries = d.photos.photo.map(ph => ({ key: `flickr:${ph.id}`, source: 'flickr', sourceId: String(ph.id),
          title: ph.title || 'Untitled', date: (ph.datetaken || '').slice(0, 10), lat: +ph.latitude || null, lon: +ph.longitude || null,
          thumb: ph.url_m || ph.url_z, image: ph.url_l || ph.url_z || ph.url_m, page: `https://www.flickr.com/photos/${ph.owner}/${ph.id}`,
          license: FLICKR_LIC[ph.license] || ph.license, attribution: ph.ownername }));
        return { entries, total: +d.photos.total, more: page < d.photos.pages };
      },
    },
  };

  function buildSourcePanel(name) {
    const panel = $(`[data-panel="${name}"]`), cfg = SOURCES[name];
    panel.append($('#sourceTpl').content.cloneNode(true));
    $('.crb-intro', panel).innerHTML = cfg.intro;
    const form = $('form', panel), mapEl = $('.crb-map', panel), grid = $('.crb-grid', panel), count = $('.crb-count', panel), more = $('.crb-more', panel);
    for (const [fld, on] of Object.entries(cfg.fields)) $$(`.f-${fld}`, form).forEach(el => { el.hidden = !on; });
    $('[name="taxon"] option[value="Oryctes rhinoceros"]', form)?.remove();   // beetle records live on the Surveillance tab
    if (cfg.key) {
      const box = $('.crb-keys', panel), input = $('input', box);
      box.hidden = false; $('.key-label', box).textContent = cfg.key.label; $('.crb-hint', box).innerHTML = cfg.key.hint;
      input.value = ls.get(cfg.key.store); if (!input.value) box.open = true;
      $('.save-key', box).onclick = () => { ls.set(cfg.key.store, input.value.trim()); box.open = false; };
    }
    form.d1.value = name === 'mapillary' ? yearsAgo(2) : yearsAgo(3);
    form.d2.value = today();
    fillRegionSelect(form.region, ['south_america', 'caribbean', 'us_contiguous']);
    form.region.value = 'caribbean';
    if (name === 'mapillary') { form.region.insertAdjacentHTML('afterbegin', '<option value="__map">Current map view</option>'); form.region.value = '__map'; }
    const st = state.sourceState[name] = { page: 1, entries: [] };

    const map = getMap(name, mapEl);
    if (name === 'mapillary') map?.setView([13.474, 144.75], 13); else fitRegion(name, form.region.value);
    form.region.addEventListener('change', () => fitRegion(name, form.region.value));

    async function run(append) {
      const f = Object.fromEntries(new FormData(form));
      f.cc = form.cc.checked; f.hideKnown = form.hideKnown.checked; f.bbox = bboxFor(name, f.region);
      if (!append) { st.page = 1; st.entries = []; grid.innerHTML = ''; }
      count.textContent = 'Searching…'; more.hidden = true;
      try {
        const res = await cfg.search(f, st.page);
        for (const e of res.entries) { e.result = resultFor(e); if (!e.result) e.rejected = rejectedFor(e); }
        const shown = f.hideKnown ? res.entries.filter(e => !e.result && e.rejected === undefined) : res.entries;
        st.entries.push(...shown);
        state.entries[name] = st.entries;
        renderGrid(grid, shown, append);
        if (!st.entries.length) grid.innerHTML = '<p class="crb-empty">No photos found. Try a larger area or a wider date range.</p>';
        const screened = st.entries.filter(e => e.result || e.rejected !== undefined).length;
        count.textContent = `${st.entries.length.toLocaleString()} shown${res.total != null ? ` of ${(+res.total).toLocaleString()}` : ''}` +
          `${res.note ? ` · ${res.note}` : ''} · ${screened} already screened by the monitor`;
        plot(name, st.entries, f.region === '__map' ? false : true);
        more.hidden = !res.more;
      } catch (err) {
        count.textContent = '';
        const msg = err.message === 'Failed to fetch' || err.name === 'TypeError'
          ? `Could not reach ${sourceName(name)} just now. Check your connection and try again.` : err.message;
        grid.innerHTML = `<p class="crb-error">${esc(msg)}</p>`;
      }
    }
    form.addEventListener('submit', ev => { ev.preventDefault(); run(false); });
    more.onclick = () => { st.page += 1; run(true); };
    panel.dataset.built = '1';
    if (!cfg.key || ls.get(cfg.key.store)) run(false);
  }

  // ------------------------------------------------------------------ link tab
  async function sha1hex(s) {
    const buf = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(s));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  }
  async function previewLink(url) {
    let m;
    if ((m = url.match(/inaturalist\.org\/observations\/(\d+)/))) {
      const o = (await getJSON(`${API.inat}/observations/${m[1]}`)).results[0]; const p = o.photos?.[0]; const c = o.geojson?.coordinates || [];
      return { key: `inaturalist:${o.id}`, source: 'inaturalist', sourceId: String(o.id), title: o.taxon?.name || 'iNaturalist observation',
        date: o.observed_on, lat: c[1], lon: c[0], thumb: p && inatSize(p.url, 'medium'), image: p && inatSize(p.url, 'large'), page: url,
        license: p?.license_code, attribution: p?.attribution };
    }
    if ((m = url.match(/gbif\.org\/occurrence\/(\d+)/))) {
      const o = await getJSON(`${API.gbif}/occurrence/${m[1]}`); const md = (o.media || []).find(x => x.identifier);
      return { key: `gbif:${o.key}`, source: 'gbif', sourceId: String(o.key), title: o.scientificName, date: (o.eventDate || '').slice(0, 10),
        lat: o.decimalLatitude, lon: o.decimalLongitude, thumb: md && gbifThumb(o.key, md.identifier), image: md?.identifier, page: url,
        license: md?.license, attribution: md?.rightsHolder || o.recordedBy };
    }
    if ((m = url.match(/mapillary\.com\/.*[?&]pKey=(\d+)/))) {
      const token = ls.get('crb.mapillaryToken'); let thumb = '';
      if (token) try { thumb = (await getJSON(`${API.mly}/${m[1]}?fields=thumb_1024_url&access_token=${encodeURIComponent(token)}`)).thumb_1024_url; } catch { /* no preview */ }
      return { key: `mapillary:${m[1]}`, source: 'mapillary', sourceId: m[1], title: `Street view ${m[1]}`, thumb, image: thumb, page: url, license: 'CC BY-SA 4.0' };
    }
    if ((m = url.match(/flickr\.com\/photos\/[^/]+\/(\d+)/))) {
      const key = ls.get('crb.flickrKey'); let thumb = '';
      if (key) try { const d = await flickrCall({ method: 'flickr.photos.getSizes', api_key: key, photo_id: m[1] }); thumb = (d.sizes.size.find(s => s.label === 'Medium') || d.sizes.size.at(-1)).source; } catch { /* no preview */ }
      return { key: `flickr:${m[1]}`, source: 'flickr', sourceId: m[1], title: `Flickr photo ${m[1]}`, thumb, image: thumb, page: url };
    }
    const looksImage = /\.(jpe?g|png|webp|gif|avif)(\?|$)/i.test(url);
    const h = (await sha1hex(url)).slice(0, 16);
    return { key: `link:${h}`, source: 'link', sourceId: url, title: url.replace(/^https?:\/\//, '').slice(0, 80),
      thumb: looksImage ? url : '', image: looksImage ? url : '', page: url,
      note: looksImage ? '' : 'Web page: the analysis will use its preview (og:image) photo' };
  }
  const linkLines = () => $('#linkInput').value.split(/\s+/).map(s => s.trim()).filter(s => /^https?:\/\//.test(s));
  $('#linkPreview').onclick = async () => {
    const grid = $('#grid-link'), urls = linkLines();
    if (!urls.length) { grid.innerHTML = '<p class="crb-error">Paste at least one link starting with http.</p>'; return; }
    grid.innerHTML = '<p class="crb-empty">Looking up…</p>';
    const entries = [];
    for (const u of urls.slice(0, MAX_ISSUE_LINKS)) {
      try {
        const e = await previewLink(u);
        e.result = e.source === 'link' ? state.items.find(it => it.uid.startsWith(e.key)) : resultFor(e);
        if (!e.thumb && e.note) e.title += ' — ' + e.note;
        entries.push(e);
      } catch (err) { entries.push({ key: 'err:' + u, source: 'link', title: `Could not preview: ${err.message}`, page: u }); }
    }
    state.entries.link = entries;
    renderGrid(grid, entries);
  };
  $('#linkSend').onclick = () => {
    const urls = linkLines();
    if (!urls.length) { $('#grid-link').innerHTML = '<p class="crb-error">Paste at least one link starting with http.</p>'; return; }
    sendLinks(urls);
  };

  // ------------------------------------------------------------------ tabs + routing
  let currentTab = 'results';
  function showTab(name) {
    if (!$(`[data-panel="${name}"]`)) name = 'results';
    currentTab = name;
    $$('#crbTabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === name)));
    $$('.crb-panel').forEach(p => { p.hidden = p.dataset.panel !== name; });
    if (SOURCES[name] && !$(`[data-panel="${name}"]`).dataset.built) buildSourcePanel(name);
    setTimeout(() => state.maps[name]?.invalidateSize(), 50);
    if (!location.hash.startsWith('#item=')) history.replaceState(null, '', `#tab=${name}`);
  }
  $$('#crbTabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
  window.addEventListener('hashchange', () => {
    const uid = new URLSearchParams(location.hash.slice(1)).get('item');
    if (uid && state.byUid.has(uid)) { showTab('results'); openViewer(entryFromItem(state.byUid.get(uid))); }
    else if (uid && /^(inat|gbif):/.test(uid)) location.href = `crb-surveillance.html#item=${encodeURIComponent(uid)}`;
  });
  $('#crbTabs').addEventListener('keydown', ev => {
    if (!['ArrowRight', 'ArrowLeft'].includes(ev.key)) return;
    const tabs = $$('#crbTabs button'), i = tabs.findIndex(t => t.dataset.tab === currentTab);
    const next = tabs[(i + (ev.key === 'ArrowRight' ? 1 : tabs.length - 1)) % tabs.length];
    showTab(next.dataset.tab); next.focus();
  });

  async function init() {
    try { await loadData(); } catch (err) {
      $('#crbStats').textContent = `Could not load monitor data (${err.message}).`;
      return;
    }
    renderStats();
    $$('select[data-regions="all"]').forEach(sel => fillRegionSelect(sel, ['south_america', 'caribbean', 'us_contiguous']));
    const hash = new URLSearchParams(location.hash.slice(1));
    const uid = hash.get('item');
    if (uid && /^(inat|gbif):/.test(uid)) { location.replace(`crb-surveillance.html#item=${encodeURIComponent(uid)}`); return; }
    showTab(hash.get('tab') || 'results');
    filterResults();
    if (uid && state.byUid.has(uid)) {
      $('#resFilters').status.value = 'everything'; filterResults();
      openViewer(entryFromItem(state.byUid.get(uid)));
    } else if (!state.items.some(i => statusOf(i) === 'damage') && state.items.length) {
      $('#resFilters').status.value = 'all_analyzed'; filterResults();
    }
  }
  init();
})();
