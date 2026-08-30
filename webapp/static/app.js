/* SkyPass web -- client logic.
 *
 * All astronomy happens on the server, in the same package the paper validates.
 * This file gathers inputs, renders results, draws the sky chart, and keeps a
 * live countdown to the next pass.
 */
'use strict';

const $ = (id) => document.getElementById(id);
const STORE = 'skypass.settings';
const state = { station: 'chennai', plan: null, busy: false, sort: 'time',
                timer: null };

/* ------------------------------------------------------------- helpers -- */

/* The server speaks UTC; the observer lives in local time and has to be
 * outside at the right moment, so everything shown is converted. */
const utc = (iso) => new Date(iso + 'Z');

const fmtTime = (iso) => utc(iso).toLocaleTimeString([],
  { hour: '2-digit', minute: '2-digit' });

function fmtDay(iso) {
  const d = utc(iso), now = new Date();
  const same = (a, b) => a.toDateString() === b.toDateString();
  if (same(d, now)) return 'Tonight';
  if (same(d, new Date(now.getTime() + 86400000))) return 'Tomorrow';
  return d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
}

function fmtDur(s) {
  const m = Math.floor(s / 60);
  return m >= 1 ? `${m} min ${s % 60}s` : `${s}s`;
}

function countdown(ms) {
  if (ms <= 0) return 'now';
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m ${s % 60}s`;
}

function brightnessWord(mag) {
  if (mag === null || mag === undefined) return null;
  if (mag <= 0) return 'brilliant';
  if (mag <= 2) return 'bright';
  if (mag <= 4) return 'easy';
  if (mag <= 5.5) return 'faint';
  return 'very faint';
}

function setStatus(html, busy) {
  state.busy = !!busy;
  $('status').innerHTML = busy
    ? `<span class="spinner"></span><span>${html}</span>`
    : `<span>${html}</span>`;
  $('runBtn').disabled = !!busy;
}

/* ---------------------------------------------------------- sky chart -- */

/* Polar plot: zenith at the centre, horizon at the rim, north at the top.
 * This is the one element carrying the system's single drop-shadow -- it is
 * the "product" here, the thing the interface exists to show. */
function skyChart(track, elMax) {
  if (!track || track.length < 2) return '';
  const S = 300, C = S / 2, R = C - 30;
  const css = getComputedStyle(document.documentElement);
  const bg = css.getPropertyValue('--chart-bg').trim() || '#fff';
  const ring = css.getPropertyValue('--chart-ring').trim() || '#e0e0e0';
  const lab = css.getPropertyValue('--chart-label').trim() || '#7a7a7a';
  const accent = css.getPropertyValue('--primary').trim() || '#0066cc';

  const pt = (az, el) => {
    const r = R * (1 - Math.max(0, Math.min(el, 90)) / 90);
    const a = (az - 90) * Math.PI / 180;
    return [C + r * Math.cos(a), C + r * Math.sin(a)];
  };

  let rings = '';
  [[0, "0°"], [30, "30°"], [60, "60°"]].forEach(([el, txt]) => {
    const r = R * (1 - el / 90);
    rings += `<circle cx="${C}" cy="${C}" r="${r}" fill="none"
      stroke="${ring}" stroke-width="1"/>`;
    if (el) rings += `<text x="${C + 3}" y="${C - r + 11}" font-size="9"
      fill="${lab}" font-family="system-ui,sans-serif">${txt}</text>`;
  });

  let spokes = '';
  ['N', 'E', 'S', 'W'].forEach((d, i) => {
    const [x, y] = pt(i * 90, -6);
    spokes += `<text x="${x}" y="${y}" font-size="12" fill="${lab}"
      text-anchor="middle" dominant-baseline="middle"
      font-family="system-ui,sans-serif">${d}</text>`;
  });

  const pts = track.map((p) => pt(p.az, p.el));
  const path = pts.map((p, i) =>
    `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
  const [sx, sy] = pts[0];
  const [ex, ey] = pts[pts.length - 1];
  let pk = 0;
  track.forEach((p, i) => { if (p.el > track[pk].el) pk = i; });
  const [px, py] = pts[pk];

  // Arrowhead on the second-to-last segment shows direction of travel, so the
  // observer knows which way to sweep rather than guessing from the endpoints.
  const [ax, ay] = pts[Math.max(0, pts.length - 2)];
  const ang = Math.atan2(ey - ay, ex - ax) * 180 / Math.PI;

  return `<svg class="skychart" viewBox="0 0 ${S} ${S}" role="img"
    aria-label="Sky track rising ${Math.round(track[0].az)} degrees,
      peaking ${elMax} degrees, setting ${Math.round(track[track.length-1].az)} degrees">
    <rect width="${S}" height="${S}" rx="8" fill="${bg}"/>
    ${rings}${spokes}
    <path d="${path}" fill="none" stroke="${accent}" stroke-width="2.5"
      stroke-linecap="round" stroke-linejoin="round"/>
    <g transform="translate(${ex},${ey}) rotate(${ang})">
      <path d="M0,0 L-9,-4.5 L-9,4.5 Z" fill="${accent}"/>
    </g>
    <circle cx="${sx}" cy="${sy}" r="4.5" fill="${bg}" stroke="${accent}" stroke-width="2"/>
    <circle cx="${px}" cy="${py}" r="6" fill="${accent}"/>
    <text x="${px}" y="${py - 12}" font-size="10" fill="${lab}"
      text-anchor="middle" font-family="system-ui,sans-serif">${elMax}°</text>
  </svg>`;
}

/* ----------------------------------------------------------- rendering -- */

function passCard(p, isNext) {
  const cloud = p.cloud === null || p.cloud === undefined
    ? null : Math.round(p.cloud * 100);
  const bright = brightnessWord(p.magnitude);

  const specs = [
    ['Peak', `${p.el_max}° ${p.dir_tca}`],
    ['Lasts', fmtDur(p.duration_s)],
    ['Range', `${p.range_km} km`],
  ];
  if (bright) specs.push(['Brightness', `mag ${p.magnitude.toFixed(1)}`]);
  if (cloud !== null) specs.push(['Cloud', `${cloud}%`]);
  specs.push(['Track', `${p.dir_aos} → ${p.dir_los}`]);

  return `<article class="pass-card reveal${isNext ? ' is-next' : ''}">
    ${isNext ? '<span class="badge">Next up</span>' : ''}
    <div class="pass-head">
      <span class="pass-name">${p.name}</span>
      <span class="pass-when">${fmtTime(p.aos)}–${fmtTime(p.los)}</span>
    </div>
    <div class="chart-frame">${skyChart(p.track, p.el_max)}</div>
    <div class="spec-row">
      ${specs.map((s) => `<div><span class="k">${s[0]}</span>
        <span class="v">${s[1]}</span></div>`).join('')}
    </div>
    ${bright ? `<p class="caption muted tight">
      Look ${p.dir_tca} at ${fmtTime(p.tca)} — ${bright}${
        cloud !== null ? `, ${cloud}% cloud forecast` : ''}.</p>` : ''}
  </article>`;
}

const SORTS = {
  time:   (a, b) => a.aos.localeCompare(b.aos),
  bright: (a, b) => (a.magnitude ?? 99) - (b.magnitude ?? 99),
  high:   (a, b) => b.el_max - a.el_max,
  clear:  (a, b) => (a.cloud ?? 1) - (b.cloud ?? 1),
};

function renderList(passes, nextId) {
  if (state.sort === 'time') {
    // Grouped by observing night, so an evening and the small hours that
    // follow read as one session rather than two dates.
    const nights = {};
    passes.forEach((p) => { (nights[p.night] ||= []).push(p); });
    return Object.keys(nights).sort().map((k) => `
      <h3 class="night-head">${fmtDay(nights[k][0].aos)}
        <span class="caption muted night-count">
          · ${nights[k].length} pass${nights[k].length > 1 ? 'es' : ''}</span></h3>
      <div class="card-grid">${nights[k]
        .map((p) => passCard(p, p.__id === nextId)).join('')}</div>`).join('');
  }
  const sorted = [...passes].sort(SORTS[state.sort]);
  return `<div class="card-grid">${sorted
    .map((p) => passCard(p, p.__id === nextId)).join('')}</div>`;
}

function render(plan) {
  state.plan = plan;
  plan.passes.forEach((p, i) => { p.__id = i; });
  $('siteLabel').textContent = plan.site.name;

  const now = Date.now();
  const upcoming = plan.passes.filter((p) => utc(p.aos).getTime() > now);
  const next = upcoming.length ? upcoming[0] : null;

  if (!plan.passes.length) {
    // Distinguish "clouded out" from "nothing up there" -- they call for
    // completely different responses from the observer.
    const pct = plan.mean_cloud == null ? null : Math.round(plan.mean_cloud * 100);
    if (plan.if_clear && plan.if_clear.length) {
      plan.if_clear.forEach((p, i) => { p.__id = -1 - i; });
      const nights = {};
      plan.if_clear.forEach((p) => { (nights[p.night] ||= []).push(p); });
      $('results').innerHTML = `
        <div class="empty empty-tight">
          <p class="tagline">Clouded out.</p>
          <p class="caption">There ${plan.blocked_by_weather === 1 ? 'is' : 'are'}
            ${plan.blocked_by_weather} observable
            pass${plan.blocked_by_weather === 1 ? '' : 'es'} up there, but the
            forecast puts ${pct !== null ? pct + '%' : 'heavy'} cloud over them.
            Below is what you would see if it cleared.</p>
        </div>
        ${Object.keys(nights).sort().map((k) => `
          <h3 class="night-head">${fmtDay(nights[k][0].aos)}
            <span class="caption muted night-count">
              · if it clears</span></h3>
          <div class="card-grid">${nights[k].map((p) => passCard(p, false)).join('')}</div>`).join('')}`;
    } else {
      $('results').innerHTML = `<div class="empty">
        <p class="tagline">Nothing worth going outside for.</p>
        <p class="caption">Every pass in this window failed at least one test —
        daylight, eclipse, or too faint. Try a longer horizon, a lower horizon
        mask, or radio mode.</p></div>`;
    }
    $('sortBar').hidden = true;
  } else {
    $('sortBar').hidden = false;
    $('results').innerHTML = renderList(plan.passes, next ? next.__id : null);
  }

  const n = plan.passes.length;
  $('timetableSub').innerHTML = n
    ? `${n} pass${n > 1 ? 'es' : ''} worth your time, from ${plan.funnel.geometric}
       that cross the sky. ${plan.weather_used
        ? 'Ranked with the cloud forecast.'
        : '<strong>Weather not applied.</strong>'}`
    : (plan.if_clear && plan.if_clear.length
        ? `${plan.blocked_by_weather} observable, none worth it under this sky.`
        : 'No observable passes in this window.');

  // Funnel as a gapless bento: the lead statistic gets a 2x2 cell, the middle
  // stages take singles, and the payoff spans the full width. Verified to
  // leave zero empty cells at 4, 2 and 1 columns.
  const f = plan.funnel;
  const stages = plan.mode === 'optical'
    ? [['Cross the sky', f.geometric, 'lead'], ['Sunlit', f.sunlit],
       ['Sky is dark', f.dark], ['Bright enough', f.bright],
       ['Forecast usable', f.clear], ['Scheduled', f.scheduled, 'wide']]
    : [['Cross the sky', f.geometric, 'lead'], ['Above floor', f.candidates],
       ['Scheduled', f.scheduled, 'wide']];
  const top = stages[0][1] || 1;
  $('funnelGrid').innerHTML = stages.map(([label, v, kind]) => {
    const pct = top ? (100 * v / top) : 0;
    return `<div class="cell${kind ? ' cell-' + kind : ''}">
      <div class="n">${v.toLocaleString()}</div>
      <div class="l">${label}</div>
      <div class="pct">${pct >= 99.5 ? '' : pct.toFixed(1) + '% of the sky'}</div>
    </div>`;
  }).join('');
  $('funnelNote').textContent =
    `${f.catalogue} objects propagated in ${plan.runtime_s}s `
    + `(${plan.propagations.toLocaleString()} SGP4 evaluations)`
    + (plan.capacity ? `, limited to ${plan.capacity} per night.` : '.');

  observeReveals();

  startCountdown(next);
}

/* ---------------------------------------------------------- reveals --- */

/* One observer, re-registered after each render. Elements fade up on entry and
   dim on exit so the card the reader is on holds focus -- the "image scale and
   fade" idea, done with the platform instead of a motion library. */
let _io = null;
function observeReveals() {
  if (!('IntersectionObserver' in window)) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (_io) _io.disconnect();
  _io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('is-in');
        e.target.classList.remove('is-out');
      } else if (e.target.classList.contains('is-in')) {
        e.target.classList.toggle('is-out', e.boundingClientRect.top < 0);
      }
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
  document.querySelectorAll('.reveal').forEach((el) => _io.observe(el));
}

/* --------------------------------------------------------- countdown --- */

function startCountdown(next) {
  clearInterval(state.timer);
  const bar = $('stickyBar');
  if (!next) {
    $('nextUp').hidden = true;
    bar.dataset.show = '0';
    return;
  }
  $('nextUp').hidden = false;
  $('nextName').textContent = next.name;
  $('nextDetail').textContent =
    `${fmtTime(next.aos)} · peaks ${next.el_max}° ${next.dir_tca}`
    + (next.cloud != null ? ` · ${Math.round(next.cloud * 100)}% cloud` : '');
  $('barTitle').textContent = next.name;

  const tick = () => {
    const ms = utc(next.aos).getTime() - Date.now();
    const txt = countdown(ms);
    $('nextCount').textContent = txt;
    $('barSub').textContent = `in ${txt} · peaks ${next.el_max}° ${next.dir_tca}`;
    if (ms < -next.duration_s * 1000) { clearInterval(state.timer); }
  };
  tick();
  state.timer = setInterval(tick, 1000);
  bar.dataset.show = '1';
}

/* ------------------------------------------------------------ requests -- */

function query() {
  const q = new URLSearchParams();
  const lat = $('lat').value.trim(), lon = $('lon').value.trim();
  if (lat && lon) { q.set('lat', lat); q.set('lon', lon); }
  else q.set('station', state.station);
  q.set('days', $('days').value);
  q.set('mode', $('mode').value);
  q.set('mask', $('mask').value);
  q.set('capacity', $('capacity').value);
  q.set('weather', $('weather').checked ? '1' : '0');
  return q;
}

function saveSettings() {
  try {
    localStorage.setItem(STORE, JSON.stringify({
      station: state.station, sort: state.sort,
      lat: $('lat').value, lon: $('lon').value,
      days: $('days').value, mode: $('mode').value,
      mask: $('mask').value, capacity: $('capacity').value,
      weather: $('weather').checked,
    }));
  } catch (e) { /* private browsing -- not worth interrupting the user */ }
}

function loadSettings() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || '{}');
    if (s.station) state.station = s.station;
    if (s.sort && SORTS[s.sort]) state.sort = s.sort;
    ['lat', 'lon', 'days', 'mode', 'mask', 'capacity'].forEach((k) => {
      if (s[k] !== undefined && s[k] !== null) $(k).value = s[k];
    });
    if (s.weather !== undefined) $('weather').checked = !!s.weather;
  } catch (e) { /* ignore */ }
}

async function runPlan() {
  if (state.busy) return;
  saveSettings();
  setStatus('Propagating orbits and checking the sky…', true);
  $('results').innerHTML = `<div class="card-grid group">
    ${'<div class="skeleton"></div>'.repeat(3)}</div>`;
  try {
    const res = await fetch('/api/plan?' + query().toString());
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || data.error || 'request failed');
    render(data);
    setStatus(`Done in ${data.runtime_s}s.`, false);
    $('timetable').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    $('results').innerHTML = '';
    setStatus(`Could not plan: ${err.message}`, false);
  }
}

/* --------------------------------------------------------------- setup -- */

async function init() {
  loadSettings();

  try {
    const res = await fetch('/api/stations');
    const d = await res.json();
    $('stationChips').innerHTML = d.stations.map((s) => `
      <button class="chip" type="button" aria-pressed="${s.key === state.station}"
        data-key="${s.key}">${s.name.split(',')[0]}</button>`).join('');
    $('stationChips').addEventListener('click', (e) => {
      const b = e.target.closest('.chip');
      if (!b) return;
      state.station = b.dataset.key;
      $('lat').value = ''; $('lon').value = '';
      [...$('stationChips').children].forEach((c) =>
        c.setAttribute('aria-pressed', String(c === b)));
      $('siteLabel').textContent = b.textContent.trim();
      saveSettings();
    });
    const cur = d.stations.find((s) => s.key === state.station);
    if (cur) $('siteLabel').textContent = cur.name;
  } catch {
    setStatus('Could not reach the planner. Is the server running?', false);
  }

  $('sortBar').addEventListener('click', (e) => {
    const b = e.target.closest('.chip');
    if (!b) return;
    state.sort = b.dataset.sort;
    [...$('sortBar').querySelectorAll('.chip')].forEach((c) =>
      c.setAttribute('aria-pressed', String(c === b)));
    saveSettings();
    if (state.plan) render(state.plan);
  });


  $('runBtn').addEventListener('click', runPlan);
  $('heroPlan').addEventListener('click', runPlan);
  $('planBtn').addEventListener('click', () =>
    $('plan').scrollIntoView({ behavior: 'smooth' }));

  ['days', 'mode', 'mask', 'capacity', 'weather'].forEach((k) =>
    $(k).addEventListener('change', saveSettings));

  $('geoBtn').addEventListener('click', () => {
    if (!navigator.geolocation) {
      setStatus('This browser will not share a location.', false);
      return;
    }
    setStatus('Asking your device where you are…', true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        $('lat').value = pos.coords.latitude.toFixed(4);
        $('lon').value = pos.coords.longitude.toFixed(4);
        [...$('stationChips').children].forEach((c) =>
          c.setAttribute('aria-pressed', 'false'));
        setStatus('Using your location.', false);
        runPlan();
      },
      (err) => setStatus(`Location unavailable (${err.message}).`, false),
      { timeout: 10000 });
  });

  const ics = (e) => {
    e.preventDefault();
    window.location = '/api/ics?' + query().toString();
  };
  $('icsBtn').addEventListener('click', ics);
  $('barIcs').addEventListener('click', ics);

  if (navigator.share) {
    $('shareBtn').hidden = false;
    $('shareBtn').addEventListener('click', async () => {
      const p = state.plan && state.plan.passes[0];
      try {
        await navigator.share({
          title: 'SkyPass',
          text: p ? `${p.name} at ${fmtTime(p.aos)}, peaks ${p.el_max}° ${p.dir_tca}`
                  : 'Satellite passes worth watching',
          url: location.href,
        });
      } catch (e) { /* user dismissed */ }
    });
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
}

document.addEventListener('DOMContentLoaded', init);
