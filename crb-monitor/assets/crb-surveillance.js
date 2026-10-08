/* CRB pre-border surveillance dashboard — S-Paudel.github.io
 * New GBIF + iNaturalist records of watch-list species in the watch regions.
 * Reads crb-monitor/data/surveillance.json (written daily by `python -m crbmon surveil`)
 * and can also check the two APIs live from the browser ("Check live now").
 * Grew out of Sulav Paudel's "Automated Pre-border surveillance.R" (B3 2026 ideas).
 */
(() => {
  'use strict';

  const REPO = 'S-Paudel/S-Paudel.github.io';
  const DATA = 'crb-monitor/data/surveillance.json';
  const INAT = 'https://api.inaturalist.org/v1';
  const GBIF = 'https://api.gbif.org/v1';
  const GBIF_INAT_DATASET = '50c9509d-22c7-4a22-a47d-8c48425ef4a7';
  const DEFAULT_SPECIES = ['Oryctes rhinoceros'];
  const WATCH_GROUPS = ['south_america', 'caribbean', 'us_contiguous', 'mexico_central_america'];
  // Evidence → colour (validated 3-slot palette for the dark surface) and label
  const EV = {
    confirmed:   { label: 'Confirmed',        color: '#d95926', hint: 'iNaturalist research grade (wild), or confirmed by a reviewer' },
    check:       { label: 'Needs checking',   color: '#3987e5', hint: 'iNaturalist "needs ID" / casual, or a museum, survey or lab record in GBIF' },
    captive:     { label: 'Captive / lab',    color: '#199e70', hint: 'iNaturalist captive or cultivated (pets, labs, interceptions)' },
    rejected:    { label: 'Not this species', color: '#6b6f66', hint: 'Marked as a mis-identification by a reviewer' },
  };
  const evGroup = ev => (ev === 'specimen' || ev === 'unconfirmed') ? 'check' : ev;
  // Country status (fixed status palette, always shown with icon + label)
  const STATUS = {
    active:  { icon: '●', label: 'Confirmed in last 12 months', color: '#d03b3b' },
    past:    { icon: '◐', label: 'Confirmed earlier',            color: '#ec835a' },
    check:   { icon: '?', label: 'Unconfirmed records only',     color: '#fab219' },
    none:    { icon: '○', label: 'No records',                   color: '#7C8274' },
  };

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const iso = d => d.toISOString().slice(0, 10);
  const daysAgo = n => iso(new Date(Date.now() - n * 864e5));
  const ls = {
    get(k) { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch { /* storage unavailable */ } },
  };
  const getJSON = async (url, opts) => { const r = await fetch(url, opts); if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); return r.json(); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const S = {
    built: false, data: null, records: [], live: false, liveNew: new Set(),
    groups: new Set(WATCH_GROUPS), evShown: new Set(['confirmed', 'check', 'captive']),
    since: '', species: '', focus: '', map: null, layer: null, page: 0,
  };
  // ---------------------------------------------------------------- regions (crb-monitor/data/regions.json)
  let REGIONS = null;
  const R = () => REGIONS;
  const CRB = {
    areasOf(key) {
      const { groups: G, areas: A } = REGIONS;
      if (G[key]) return G[key].members.map(m => ({ key: m, ...A[m] }));
      return A[key] ? [{ key, ...A[key] }] : [];
    },
    regionBBox(key) {
      const bb = CRB.areasOf(key).map(a => a.bbox);
      return bb.length ? [Math.min(...bb.map(b => b[0])), Math.min(...bb.map(b => b[1])), Math.max(...bb.map(b => b[2])), Math.max(...bb.map(b => b[3]))] : null;
    },
    inatPlaceParams(key) {
      const areas = CRB.areasOf(key);
      const out = { place_id: areas.map(a => a.inat_place).join(',') };
      const excl = [...new Set(areas.flatMap(a => a.inat_not_in_place || []))];
      if (excl.length) out.not_in_place = excl.join(',');
      return out;
    },
  };
  const areaName = k => R().areas[k]?.name || k || 'Unknown';
  const groupOfArea = k => Object.keys(R().groups).find(g => R().groups[g].members.includes(k));

  function evidence(r) {
    const rv = r.review?.decision;
    if (rv === 'rejected') return 'rejected';
    if (rv === 'confirmed') return 'confirmed';
    if (r.src === 'gbif') return 'specimen';
    if (r.captive) return 'captive';
    return r.grade === 'research' ? 'confirmed' : 'unconfirmed';
  }

  // ---------------------------------------------------------------- live fetch (mirrors crbmon/surveillance.py)
  const taxa = {};
  async function inatTaxon(name) {
    if (!taxa['i' + name]) {
      const d = await getJSON(`${INAT}/taxa?q=${encodeURIComponent(name)}&per_page=30`);
      taxa['i' + name] = d.results.find(t => t.name.toLowerCase() === name.toLowerCase())?.id;
    }
    return taxa['i' + name];
  }
  async function gbifKey(name) {
    if (!taxa['g' + name]) taxa['g' + name] = (await getJSON(`${GBIF}/species/match?name=${encodeURIComponent(name)}`)).usageKey;
    return taxa['g' + name];
  }
  function areaFromPlaces(group, placeIds) {
    return R().groups[group].members.find(k => {
      const a = R().areas[k];
      return placeIds.includes(a.inat_place) && !(a.inat_not_in_place || []).some(p => placeIds.includes(p));
    });
  }
  async function fetchLive(species, groups, onProgress) {
    const out = [];
    for (const sp of species) {
      const tid = await inatTaxon(sp), gk = await gbifKey(sp);
      for (const g of groups) {
        onProgress?.(`${sp} · ${R().groups[g].name}`);
        const places = CRB.inatPlaceParams(g);
        let idAbove = 0;
        const inatInGbif = new Set();
        for (let i = 0; i < 50; i++) {
          const q = new URLSearchParams({ taxon_id: tid, ...places, per_page: 200, order_by: 'id', order: 'asc', id_above: idAbove });
          const d = await getJSON(`${INAT}/observations?${q}`);
          for (const o of d.results) {
            const c = o.geojson?.coordinates || [];
            const ph = o.photos?.[0]?.url;
            out.push({ uid: `inat:${o.id}`, sp, src: 'inaturalist', id: o.id, url: o.uri || `https://www.inaturalist.org/observations/${o.id}`,
              area: areaFromPlaces(g, o.place_ids || []), lat: c[1] ?? null, lon: c[0] ?? null, date: o.observed_on,
              added: (o.created_at || '').slice(0, 10), grade: o.quality_grade, captive: !!o.captive, place: o.place_guess,
              by: o.user?.login, taxon: o.taxon?.name, photo: ph ? ph.replace('/square.', '/small.') : null });
          }
          if (d.results.length < 200) break;
          idAbove = d.results.at(-1).id;
          await sleep(500);
        }
        const areas = CRB.areasOf(g);
        const queries = [];
        const whole = areas.filter(a => !a.gbif_bbox_filter).map(a => a.country);
        if (whole.length) { const q = new URLSearchParams({ taxonKey: gk, occurrenceStatus: 'PRESENT', limit: 300 }); whole.forEach(c => q.append('country', c)); queries.push(q); }
        for (const a of areas.filter(a => a.gbif_bbox_filter)) {
          const [w, s, e, n] = a.bbox;
          queries.push(new URLSearchParams({ taxonKey: gk, occurrenceStatus: 'PRESENT', limit: 300, country: a.country, decimalLatitude: `${s},${n}`, decimalLongitude: `${w},${e}` }));
        }
        for (const q of queries) {
          for (let off = 0; off < 3000; off += 300) {
            q.set('offset', off);
            const d = await getJSON(`${GBIF}/occurrence/search?${q}`);
            for (const o of d.results) {
              if (o.datasetKey === GBIF_INAT_DATASET) { const m = String(o.references || '').match(/observations\/(\d+)/); if (m) inatInGbif.add(+m[1]); continue; }
              out.push({ uid: `gbif:${o.key}`, sp, src: 'gbif', id: o.key, url: `https://www.gbif.org/occurrence/${o.key}`,
                area: areas.find(a => a.country === o.countryCode)?.key, lat: o.decimalLatitude ?? null, lon: o.decimalLongitude ?? null,
                date: (o.eventDate || '').slice(0, 10) || null, grade: o.basisOfRecord, captive: false,
                place: [o.locality, o.stateProvince].filter(Boolean).join(', ') || null, by: o.recordedBy || o.institutionCode,
                dataset: o.datasetName || o.datasetKey, taxon: o.scientificName, photo: (o.media || []).find(m => m.identifier)?.identifier || null });
            }
            if (d.endOfRecords) break;
          }
        }
        out.forEach(r => { if (r.src === 'inaturalist' && inatInGbif.has(r.id)) r.in_gbif = true; });
      }
    }
    out.forEach(r => { r.ev = evidence(r); });
    return out;
  }

  // ---------------------------------------------------------------- derived data
  function visible() {
    return S.records.filter(r =>
      (!S.species || r.sp === S.species) &&
      S.groups.has(groupOfArea(r.area)) &&
      S.evShown.has(evGroup(r.ev)) &&
      (!S.focus || r.area === S.focus));
  }
  /** When the record entered the system: the day the daily job first saw it; for records already there
   *  when monitoring started, the day it was uploaded to iNaturalist (GBIF-only records: unknown). */
  const seenDate = r => (r.first_seen && r.first_seen !== 'baseline' && r.first_seen !== 'live') ? r.first_seen
    : (r.first_seen === 'live' ? iso(new Date()) : (r.added || ''));
  const isNew = r => S.liveNew.has(r.uid) || (seenDate(r) && seenDate(r) >= S.since);
  function areaStatus(recs) {
    const yearAgo = daysAgo(365);
    const conf = recs.filter(r => r.ev === 'confirmed');
    if (conf.some(r => (r.date || r.added || '') >= yearAgo)) return 'active';
    if (conf.length) return 'past';
    if (recs.some(r => r.ev !== 'rejected')) return 'check';
    return 'none';
  }
  function monthsBack(n) {
    const out = [], d = new Date(); d.setUTCDate(1);
    for (let i = n - 1; i >= 0; i--) { const x = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - i, 1)); out.push(x.toISOString().slice(0, 7)); }
    return out;
  }

  // ---------------------------------------------------------------- render
  function render() {
    const recs = visible();
    renderKPIs(recs);
    renderAlerts();
    renderBoard();
    renderChart(recs);
    renderMap(recs);
    S.page = 0; renderTable(recs);
  }

  function renderKPIs(recs) {
    const fresh = recs.filter(isNew);
    const freshConf = fresh.filter(r => r.ev === 'confirmed').length;
    const activeAreas = Object.entries(groupBy(recs.filter(r => r.ev !== 'rejected'), r => r.area))
      .filter(([, rs]) => areaStatus(rs) === 'active').map(([k]) => areaName(k));
    const dated = recs.filter(r => r.date).sort((a, b) => b.date.localeCompare(a.date));
    const latest = dated[0];
    // Spread tracker (from the R script's spread analysis): northernmost confirmed record in the watch area
    const conf = recs.filter(r => r.ev === 'confirmed' && r.lat != null);
    const north = conf.sort((a, b) => b.lat - a.lat)[0];
    $('#svKpis').innerHTML = [
      tile(fresh.length, `new since ${S.since}`, freshConf ? `${freshConf} confirmed` : 'none confirmed', fresh.length ? 'hot' : ''),
      tile(activeAreas.length, 'countries with confirmed records in the last 12 months', activeAreas.join(', ') || '—', activeAreas.length ? 'hot' : ''),
      tile(latest ? latest.date : '—', 'latest observation', latest ? `${areaName(latest.area)} · ${latest.place || ''}` : 'no records'),
      tile(north ? `${north.lat.toFixed(2)}°` : '—', 'northernmost confirmed record', north ? `${north.place || areaName(north.area)} (${north.date || 'undated'})` : 'none'),
    ].join('');
  }
  const tile = (v, label, sub, cls = '') => `<div class="sv-tile ${cls}"><b>${esc(v)}</b><span>${esc(label)}</span><small>${esc(sub)}</small></div>`;
  const groupBy = (arr, f) => arr.reduce((m, x) => ((m[f(x)] ||= []).push(x), m), {});

  function renderAlerts() {
    const box = $('#svAlerts');
    let alerts = (S.data?.alerts || []).filter(a => a.date >= S.since && (!S.species || a.sp === S.species)
      && (!a.area || S.groups.has(groupOfArea(a.area))));
    // New records not already covered by a saved alert (live finds, and uploads since the date for older records)
    const covered = new Set(alerts.flatMap(a => a.uids || []));
    const fresh = visible().filter(r => isNew(r) && !covered.has(r.uid));
    const byArea = groupBy(fresh, r => r.area);
    const derived = Object.entries(byArea).map(([k, rs]) => {
      const conf = rs.filter(r => r.ev === 'confirmed').length;
      const live = rs.some(r => S.liveNew.has(r.uid));
      return { level: conf ? 'high' : 'low', type: live ? 'live check' : 'new uploads',
        text: `${rs.length} new record${rs.length > 1 ? 's' : ''} in ${areaName(k)}${conf ? ` (${conf} confirmed)` : ' (needs checking)'}` +
              `${live ? ', not yet in the saved record' : ''}`,
        uids: rs.map(r => r.uid), date: rs.map(seenDate).sort().at(-1) || '' };
    });
    alerts = derived.concat(alerts);
    if (!alerts.length) {
      box.innerHTML = `<p class="sv-quiet">No alerts since ${esc(S.since)}.${S.data?.baseline ? ` Watching since ${esc(S.data.baseline)}.` : ''}</p>`;
      return;
    }
    const icon = { high: '▲', medium: '◆', low: '•' };
    box.innerHTML = alerts.slice(0, 40).map(a => `<div class="sv-alert ${esc(a.level)}">
        <span class="sv-alert-icon" aria-hidden="true">${icon[a.level] || '•'}</span>
        <div><p>${esc(a.text)}</p><small class="mono">${esc(a.date)} · ${esc(a.type.replace('_', ' '))}
          ${(a.uids || []).slice(0, 3).map(u => ` · <a href="#" data-rec="${esc(u)}">view</a>`).join('')}</small></div></div>`).join('');
  }

  function renderBoard() {
    const recs = S.records.filter(r => (!S.species || r.sp === S.species) && r.ev !== 'rejected');
    const byArea = groupBy(recs, r => r.area);
    const months = monthsBack(60);
    const html = [];
    for (const g of WATCH_GROUPS) {
      if (!S.groups.has(g)) continue;
      const members = R().groups[g].members;
      const withRecs = members.filter(k => byArea[k]?.length)
        .sort((a, b) => ['active', 'past', 'check'].indexOf(areaStatus(byArea[a])) - ['active', 'past', 'check'].indexOf(areaStatus(byArea[b])));
      const without = members.filter(k => !byArea[k]?.length).map(areaName).sort();
      html.push(`<section class="sv-group"><h4>${esc(R().groups[g].name)}</h4><div class="sv-cards">`);
      for (const k of withRecs) {
        const rs = byArea[k], st = STATUS[areaStatus(rs)];
        const counts = groupBy(rs, r => evGroup(r.ev));
        const last = rs.map(r => r.date).filter(Boolean).sort().at(-1);
        const fresh = rs.filter(isNew).length;
        html.push(`<button class="sv-card${S.focus === k ? ' on' : ''}" data-area="${esc(k)}" aria-pressed="${S.focus === k}">
          <span class="sv-status" style="--c:${st.color}"><i aria-hidden="true">${st.icon}</i>${esc(st.label)}</span>
          <strong>${esc(areaName(k))}</strong>
          <span class="sv-counts mono">${['confirmed', 'check', 'captive'].map(e => counts[e] ? `<span><i style="background:${EV[e].color}"></i>${counts[e].length} ${EV[e].label.toLowerCase()}</span>` : '').join('')}</span>
          ${sparkline(rs, months)}
          <small class="mono">last seen ${esc(last || 'undated')}${fresh ? ` · <em>${fresh} new</em>` : ''}</small>
        </button>`);
      }
      html.push('</div>');
      if (without.length) html.push(`<p class="sv-none"><span class="sv-status" style="--c:${STATUS.none.color}"><i aria-hidden="true">○</i>No records</span> ${esc(without.join(' · '))}</p>`);
      html.push('</section>');
    }
    $('#svBoard').innerHTML = html.join('');
  }

  function sparkline(recs, months) {
    const counts = months.map(m => recs.filter(r => (r.date || '').startsWith(m) && r.ev !== 'captive').length);
    const max = Math.max(1, ...counts), w = 120, h = 24, bw = w / months.length;
    return `<svg class="sv-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Monthly records, last 5 years">${
      counts.map((c, i) => c ? `<rect x="${(i * bw).toFixed(2)}" y="${(h - (c / max) * h).toFixed(2)}" width="${Math.max(1, bw - 0.6).toFixed(2)}" height="${((c / max) * h).toFixed(2)}" rx="0.6"/>` : '').join('')
    }<line x1="0" x2="${w}" y1="${h - 0.5}" y2="${h - 0.5}"/></svg>`;
  }

  // Monthly stacked bars: confirmed vs needs checking, last 5 years (captive / rejected excluded)
  function renderChart(recs) {
    const months = monthsBack(60);
    const rows = months.map(m => ({ m,
      confirmed: recs.filter(r => r.ev === 'confirmed' && (r.date || '').startsWith(m)).length,
      check: recs.filter(r => evGroup(r.ev) === 'check' && (r.date || '').startsWith(m)).length }));
    const max = Math.max(1, ...rows.map(r => r.confirmed + r.check));
    const W = 760, H = 200, L = 30, B = 22, T = 8, bw = (W - L) / months.length;
    const y = v => T + (H - T - B) * (1 - v / max);
    const ticks = [...new Set([0, Math.ceil(max / 2), max])];
    const svg = [`<svg viewBox="0 0 ${W} ${H}" class="sv-chart-svg" role="img" aria-label="Records per month for the last five years">`];
    ticks.forEach(t => svg.push(`<line class="grid" x1="${L}" x2="${W}" y1="${y(t)}" y2="${y(t)}"/><text class="tick" x="${L - 6}" y="${y(t) + 4}" text-anchor="end">${t}</text>`));
    rows.forEach((r, i) => {
      const x = L + i * bw + 1, w = Math.max(1, bw - 2);
      let base = H - B;
      for (const k of ['confirmed', 'check']) {
        if (!r[k]) continue;
        const hgt = (H - T - B) * r[k] / max;
        svg.push(`<rect x="${x.toFixed(1)}" y="${(base - hgt).toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(0, hgt - 1).toFixed(1)}" rx="1.5" fill="${EV[k].color}"/>`);
        base -= hgt;
      }
      svg.push(`<rect class="hit" x="${(L + i * bw).toFixed(1)}" y="${T}" width="${bw.toFixed(1)}" height="${H - T - B}" data-i="${i}"/>`);
      if (r.m.endsWith('-01')) svg.push(`<text class="tick" x="${(L + i * bw).toFixed(1)}" y="${H - 6}">${r.m.slice(0, 4)}</text>`);
    });
    svg.push('</svg>');
    const scope = S.focus ? areaName(S.focus) : [...S.groups].map(g => R().groups[g].name).join(', ');
    $('#svChart').innerHTML = `<div class="sv-chart-head"><h4>Records per month · ${esc(scope)}</h4>
      <span class="sv-legend">${['confirmed', 'check'].map(k => `<span><i style="background:${EV[k].color}"></i>${EV[k].label}</span>`).join('')}</span></div>
      <div class="sv-chart-wrap">${svg.join('')}<div class="sv-tip" hidden></div></div>`;
    const tip = $('#svChart .sv-tip'), wrap = $('#svChart .sv-chart-wrap');
    $$('#svChart .hit').forEach(el => {
      el.addEventListener('mouseenter', () => {
        const r = rows[+el.dataset.i];
        tip.hidden = false;
        tip.innerHTML = `<b>${esc(r.m)}</b><br>${r.confirmed} confirmed · ${r.check} needs checking`;
        const box = el.getBoundingClientRect(), wb = wrap.getBoundingClientRect();
        tip.style.left = `${Math.min(wb.width - 170, Math.max(0, box.left - wb.left - 60))}px`;
      });
      el.addEventListener('mouseleave', () => { tip.hidden = true; });
    });
  }

  function renderMap(recs) {
    if (!S.map) {
      if (typeof L === 'undefined') { $('#svMap').innerHTML = '<p class="crb-empty">Map unavailable.</p>'; return; }
      S.map = L.map('svMap', { scrollWheelZoom: false, worldCopyJump: true }).setView([8, -78], 3);
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 18, subdomains: 'abcd',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>' }).addTo(S.map);
      S.layer = L.layerGroup().addTo(S.map);
    }
    S.layer.clearLayers();
    const pts = [];
    const order = { captive: 0, rejected: 0, check: 1, confirmed: 2 };
    [...recs].sort((a, b) => order[evGroup(a.ev)] - order[evGroup(b.ev)]).forEach(r => {
      if (r.lat == null || r.lon == null) return;
      const e = EV[evGroup(r.ev)], fresh = isNew(r);
      const m = L.circleMarker([r.lat, r.lon], { radius: fresh ? 8 : 5.5, color: fresh ? '#F5F2E9' : '#0A0B09', weight: fresh ? 2.5 : 1.5, fillColor: e.color, fillOpacity: 0.9 });
      m.bindTooltip(`${esc(areaName(r.area))} · ${esc(r.date || 'undated')}<br>${esc(e.label)}${fresh ? ' · NEW' : ''}`);
      m.on('click', () => openRecord(r.uid));
      S.layer.addLayer(m); pts.push([r.lat, r.lon]);
    });
    if (S.focus) { const bb = CRB.regionBBox(S.focus); if (bb) S.map.fitBounds([[bb[1], bb[0]], [bb[3], bb[2]]], { maxZoom: 9 }); }
    else if (pts.length) S.map.fitBounds(L.latLngBounds(pts).pad(0.3), { maxZoom: 6 });
    setTimeout(() => S.map.invalidateSize(), 60);
  }

  function renderTable(recs) {
    const sorted = [...recs].sort((a, b) => (isNew(b) - isNew(a)) || (b.date || b.added || '').localeCompare(a.date || a.added || ''));
    const page = sorted.slice(0, (S.page + 1) * 40);
    $('#svCount').textContent = `${recs.length} record${recs.length === 1 ? '' : 's'}${S.focus ? ` in ${areaName(S.focus)}` : ''} · ${recs.filter(isNew).length} new since ${S.since}`;
    $('#svTable tbody').innerHTML = page.map(r => {
      const e = EV[evGroup(r.ev)];
      return `<tr class="${isNew(r) ? 'new' : ''}">
        <td>${r.photo ? `<img src="${esc(r.photo)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : '<span class="sv-nophoto">—</span>'}</td>
        <td class="mono">${esc(r.date || 'undated')}${isNew(r) ? ' <em class="sv-new">new</em>' : ''}</td>
        <td>${esc(areaName(r.area))}<br><small>${esc(r.place || '')}</small></td>
        <td><span class="sv-ev" style="--c:${e.color}"><i></i>${esc(e.label)}</span><br><small class="mono">${esc(r.src === 'gbif' ? (r.grade || '').replace('_', ' ').toLowerCase() : r.grade)}${r.review ? ` · reviewed: ${esc(r.review.decision)}` : ''}</small></td>
        <td><a href="${esc(r.url)}" target="_blank" rel="noopener">${r.src === 'gbif' ? 'GBIF' : 'iNaturalist'} ↗</a><br><small class="mono">${r.first_seen === 'baseline' ? (r.added ? `uploaded ${esc(r.added)}` : 'in GBIF before monitoring') : `first seen ${esc(r.first_seen || 'live')}`}</small></td>
        <td><button class="crb-btn-ghost sv-open" data-rec="${esc(r.uid)}">Open</button></td></tr>`;
    }).join('') || '<tr><td colspan="6" class="crb-empty">No records match these filters.</td></tr>';
    $('#svMore').hidden = page.length >= sorted.length;
  }

  // ---------------------------------------------------------------- record viewer (reuses the page's dialog)
  function openRecord(uid) {
    const r = S.records.find(x => x.uid === uid);
    const dlg = document.getElementById('viewer');
    if (!r || !dlg) return;
    const e = EV[evGroup(r.ev)];
    const big = r.photo ? r.photo.replace('/small.', '/medium.') : '';
    $('#viewerFigure').innerHTML = big ? `<div class="crb-overlay-wrap"><img src="${esc(big)}" alt="${esc(r.taxon || r.sp)}" referrerpolicy="no-referrer"></div>`
      : '<p class="crb-empty" style="padding:40px">No photo with this record.</p>';
    const rows = [
      ['Species', `<em>${esc(r.taxon || r.sp)}</em>`], ['Country', esc(areaName(r.area))], ['Place', esc(r.place || '—')],
      ['Observed', esc(r.date || 'undated')], ['Uploaded', esc(r.added || '—')],
      ['First seen here', esc(r.first_seen === 'baseline' ? `already published when monitoring started (${S.data?.baseline})` : r.first_seen || 'live check')],
      ['Evidence', `${esc(e.label)} — <small>${esc(e.hint)}</small>`],
      ['Source detail', esc(r.src === 'gbif' ? `${r.grade || ''} · ${r.dataset || ''}` : `quality grade: ${r.grade}${r.captive ? ' · captive/cultivated' : ''}${r.in_gbif ? ' · also in GBIF' : ''}`)],
      ['Recorded by', esc(r.by || '—')],
      r.lat != null && ['Location', `${(+r.lat).toFixed(4)}, ${(+r.lon).toFixed(4)}`],
      r.review && ['Review', `${esc(r.review.decision)} by ${esc(r.review.by || '—')} on ${esc(r.review.on)}${r.review.note ? ` — ${esc(r.review.note)}` : ''}`],
    ].filter(Boolean);
    $('#viewerMeta').innerHTML = `
      <div><span class="sv-ev" style="--c:${e.color}"><i></i>${esc(e.label)}</span>${isNew(r) ? ' <em class="sv-new">new</em>' : ''}</div>
      <h3>${esc(areaName(r.area))}: <em>${esc(r.sp)}</em></h3>
      <dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>
      <p><a class="btn btn-primary" href="${esc(r.url)}" target="_blank" rel="noopener">Open on ${r.src === 'gbif' ? 'GBIF' : 'iNaturalist'} ↗</a></p>
      <div class="crb-review">
        <button class="crb-btn-ghost confirm" data-sv-rev="confirmed">Confirmed CRB</button>
        <button class="crb-btn-ghost" data-sv-rev="rejected">Not CRB</button>
        <button class="crb-btn-ghost" data-sv-rev="unsure">Unsure</button>
      </div>
      <p class="crb-note">Your decision is recorded through a short GitHub issue. "Not CRB" removes the record from counts and alerts.</p>`;
    $$('[data-sv-rev]', dlg).forEach(b => b.onclick = () => {
      const body = `<!-- crb-monitor:review -->\nuid: ${r.uid}\ndecision: ${b.dataset.svRev}\nnote: \n\nRecord: ${r.url}\n\n_(Add a note on the "note:" line if you like, then submit.)_`;
      window.open(`https://github.com/${REPO}/issues/new?title=${encodeURIComponent(`[CRB review] ${b.dataset.svRev}: ${r.uid}`)}&body=${encodeURIComponent(body)}`, '_blank', 'noopener');
    });
    if (!dlg.open) dlg.showModal();
    history.replaceState(null, '', `#item=${encodeURIComponent(uid)}`);
  }

  function downloadCSV() {
    const cols = ['uid', 'species', 'country', 'place', 'lat', 'lon', 'observed', 'uploaded', 'first_seen', 'evidence', 'source', 'grade', 'captive', 'url', 'review'];
    const rows = visible().map(r => [r.uid, r.sp, areaName(r.area), r.place, r.lat, r.lon, r.date, r.added, r.first_seen, r.ev, r.src, r.grade, r.captive, r.url, r.review?.decision]);
    const csv = [cols, ...rows].map(row => row.map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: `crb-surveillance-${iso(new Date())}.csv` });
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---------------------------------------------------------------- live check
  async function checkLive(auto) {
    const btn = $('#svLive'), status = $('#svStatus');
    btn.disabled = true;
    try {
      const species = S.data?.species?.map(s => s.name) || DEFAULT_SPECIES;
      const live = await fetchLive(species, WATCH_GROUPS, msg => { status.textContent = `Checking GBIF and iNaturalist live… ${msg}`; });
      const saved = new Map(S.records.map(r => [r.uid, r]));
      S.liveNew = new Set();
      for (const r of live) {
        const old = saved.get(r.uid);
        if (old) { Object.assign(old, { grade: r.grade, captive: r.captive }); if (!old.review) old.ev = r.ev; continue; }
        r.first_seen = S.data?.records?.length ? 'live' : 'baseline';
        if (S.data?.records?.length) S.liveNew.add(r.uid);
        S.records.push(r);
      }
      S.live = true;
      status.innerHTML = `Live check ${new Date().toLocaleString()}: ${live.length} records found, <b>${S.liveNew.size}</b> not yet in the saved record.` +
        (S.data?.updated ? ` Saved record last updated ${esc(new Date(S.data.updated).toLocaleString())}.` : ' The daily job has not saved a record yet, so everything shown is live.');
      render();
      if (S.pendingOpen) { openRecord(S.pendingOpen); S.pendingOpen = null; }
    } catch (err) {
      status.textContent = `Live check failed (${err.message}).${auto ? '' : ' Try again in a minute.'}`;
    } finally { btn.disabled = false; }
  }

  // ---------------------------------------------------------------- init
  async function build() {
    S.built = true;
    try { REGIONS = await getJSON('crb-monitor/data/regions.json', { cache: 'no-cache' }); }
    catch (err) { $('#svStatus').textContent = `Could not load the region list (${err.message}).`; return; }
    const last = ls.get('crb.sv.lastVisit');
    S.since = last && last < iso(new Date()) ? last : daysAgo(30);
    ls.set('crb.sv.lastVisit', iso(new Date()));
    $('#svSince').value = S.since;
    $('#svSinceHint').textContent = last ? `your last visit was ${last}` : '';
    // filters
    $('#svGroups').innerHTML = WATCH_GROUPS.map(g => `<label class="sv-chip"><input type="checkbox" value="${g}" checked> ${esc(R().groups[g].name)}</label>`).join('');
    $('#svEv').innerHTML = Object.entries(EV).map(([k, e]) => `<label class="sv-chip" title="${esc(e.hint)}"><input type="checkbox" value="${k}" ${S.evShown.has(k) ? 'checked' : ''}><i style="background:${e.color}"></i>${esc(e.label)}</label>`).join('');
    $('#svGroups').addEventListener('change', ev => { ev.target.checked ? S.groups.add(ev.target.value) : S.groups.delete(ev.target.value); S.focus = ''; render(); });
    $('#svEv').addEventListener('change', ev => { ev.target.checked ? S.evShown.add(ev.target.value) : S.evShown.delete(ev.target.value); render(); });
    $('#svSince').addEventListener('change', ev => { S.since = ev.target.value || daysAgo(30); render(); });
    $$('[data-since]').forEach(b => b.onclick = () => { S.since = daysAgo(+b.dataset.since); $('#svSince').value = S.since; render(); });
    $('#svBoard').addEventListener('click', ev => { const c = ev.target.closest('[data-area]'); if (!c) return; S.focus = S.focus === c.dataset.area ? '' : c.dataset.area; render(); $('#svChart').scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
    document.getElementById('surveillance-panel').addEventListener('click', ev => { const a = ev.target.closest('[data-rec]'); if (a) { ev.preventDefault(); openRecord(a.dataset.rec); } });
    $('#svMore').onclick = () => { S.page += 1; renderTable(visible()); };
    $('#svMapLegend').innerHTML = ['confirmed', 'check', 'captive'].map(k => `<span><i style="background:${EV[k].color}"></i>${EV[k].label}</span>`).join('') +
      '<span><i class="ring"></i>new since your date</span>';
    $('#svCsv').onclick = downloadCSV;
    $('#svLive').onclick = () => checkLive(false);

    try { S.data = await getJSON(DATA, { cache: 'no-cache' }); } catch { S.data = null; }
    S.records = (S.data?.records || []).filter(r => !r.gone);
    const sp = S.data?.species?.map(s => s.name) || DEFAULT_SPECIES;
    $('#svSpecies').innerHTML = sp.map(n => `<option>${esc(n)}</option>`).join('');
    $('#svSpecies').closest('label').hidden = sp.length < 2;
    $('#svSpecies').onchange = ev => { S.species = ev.target.value; render(); };
    S.species = sp[0];
    const scans = S.data?.scans || [];
    $('#svStatus').innerHTML = S.data?.updated
      ? `Saved record updated <b>${esc(new Date(S.data.updated).toLocaleString())}</b> · ${S.records.length} records · watching since ${esc(S.data.baseline)} · ${scans.length} daily checks so far.`
      : 'No saved record yet. Checking GBIF and iNaturalist live…';
    render();
    if (!S.records.length) checkLive(true);
    if (S.pendingOpen && S.records.length) { openRecord(S.pendingOpen); S.pendingOpen = null; }
  }

  // viewer dialog
  const dlg = document.getElementById('viewer');
  $('#viewerClose').onclick = () => dlg.close();
  dlg.addEventListener('click', ev => { if (ev.target === dlg) dlg.close(); });
  dlg.addEventListener('close', () => { if (location.hash.startsWith('#item=')) history.replaceState(null, '', location.pathname); });
  const hashItem = () => new URLSearchParams(location.hash.slice(1)).get('item');
  window.addEventListener('hashchange', () => { const uid = hashItem(); if (uid) openRecord(uid); });
  S.pendingOpen = hashItem();
  build();
})();
