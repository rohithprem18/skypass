import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Nav } from './components/Nav';
import { Landing } from './components/Landing';
import { SettingsPanel } from './components/SettingsPanel';
import { Overview } from './components/Overview';
import { Planner } from './components/Planner';
import { PassExplorer } from './components/PassExplorer';
import { PassDetail } from './components/PassDetail';
import { DecisionPanel } from './components/DecisionPanel';
import { Weather } from './components/Weather';
import { Schedule } from './components/Schedule';
import { Analysis } from './components/Analysis';
import { Experiments } from './components/Experiments';
import { LiveMode } from './components/LiveMode';
import { verdictFor } from './lib/verdict';
import { fetchPlan, fetchStations, fetchTrack, icsUrl } from './lib/api';
import { utc } from './lib/time';
import type { Pass, Plan, Settings, Station, TrackPoint, View } from './types';

const STORE = 'skypass.settings';

const DEFAULTS: Settings = {
  station: 'chennai', lat: '', lon: '', days: '3',
  mode: 'optical', mask: '10', capacity: '3', weather: true,
};

function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(STORE);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch { return DEFAULTS; }
}

/** One clock for the whole console rather than one per countdown. */
function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

export default function App() {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [stations, setStations] = useState<Station[]>([]);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [view, setView] = useState<View>('overview');
  const [night, setNight] = useState<string | null>(null);
  const [selected, setSelected] = useState<Pass | null>(null);
  const [explain, setExplain] = useState<Pass | null>(null);
  const [tracks, setTracks] = useState<Record<string, TrackPoint[]>>({});
  const [live, setLive] = useState(false);
  /* The console is only entered once a plan has been asked for. */
  const [entered, setEntered] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const now = useNow(plan !== null);

  useEffect(() => {
    try { localStorage.setItem(STORE, JSON.stringify(settings)); } catch { /* ignore */ }
  }, [settings]);

  useEffect(() => {
    fetchStations().then(setStations)
      .catch(() => setError('Could not reach the planner. Is the server running?'));
  }, []);

  const run = useCallback(async (): Promise<boolean> => {
    abort.current?.abort();
    const ac = new AbortController();
    abort.current = ac;
    setBusy(true);
    setError(null);
    setSettingsOpen(false);
    try {
      const data = await fetchPlan(settings, ac.signal);
      data.candidates.forEach((p, i) => { p.__id = i; });
      // The scheduled list repeats passes that are already in `candidates`.
      // Swapping in the candidate objects keeps one identity per pass, so a
      // selection made on the timeline is the same object the table highlights
      // -- but only the scheduled copies carry a sampled sky track, so that has
      // to be carried across or live mode loses its trajectory.
      const byKey = new Map(data.candidates.map((p) => [p.norad_id + p.aos, p]));
      for (const s of data.passes) {
        const c = byKey.get(s.norad_id + s.aos);
        if (c && s.track.length) c.track = s.track;
      }
      data.passes = data.passes.map((p) => byKey.get(p.norad_id + p.aos) ?? p);
      setPlan(data);
      setTracks({});
      const firstNight = data.nights.find((n) => n.selected > 0)?.night
        ?? data.nights[0]?.night ?? null;
      setNight(firstNight);
      setSelected(null);
      setExplain(null);
      return true;
    } catch (e) {
      if ((e as Error).name !== 'AbortError') setError((e as Error).message);
      return false;
    } finally {
      if (abort.current === ac) setBusy(false);
    }
  }, [settings]);

  /* Deliberately no plan on mount. Propagating a catalogue costs seconds and
     network, and a reload silently replanning against whatever settings were
     last stored is a surprise, not a convenience. */
  const planAndEnter = useCallback(async () => {
    if (await run()) setEntered(true);
  }, [run]);

  // Sky tracks are fetched per pass: sampling an arc for every candidate would
  // cost tens of thousands of propagator calls for rows nothing ever draws.
  useEffect(() => {
    if (!selected) return;
    const key = selected.norad_id + selected.aos;
    if (tracks[key] || selected.track.length) return;
    let alive = true;
    fetchTrack(settings, selected.norad_id, selected.aos, selected.los)
      .then((t) => { if (alive) setTracks((m) => ({ ...m, [key]: t })); })
      .catch(() => { /* the inspector degrades to numbers only */ });
    return () => { alive = false; };
  }, [selected, settings, tracks]);

  /* Escape closes the topmost panel, one layer at a time. Owned here rather
     than in each panel: two independent listeners fired in mount order, which
     closed the inspector underneath the decision panel and left the top one
     standing. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (explain) setExplain(null);
      else if (selected) setSelected(null);
      else if (settingsOpen) setSettingsOpen(false);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [explain, selected, settingsOpen]);

  const locate = useCallback(() => {
    if (!navigator.geolocation) {
      setError('This browser will not share a location.'); return;
    }
    setError(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => setSettings((s) => ({
        ...s,
        lat: pos.coords.latitude.toFixed(4),
        lon: pos.coords.longitude.toFixed(4),
      })),
      (err) => setError(`Location unavailable (${err.message}).`),
      { timeout: 10_000 },
    );
  }, []);

  const patch = useCallback((p: Partial<Settings>) =>
    setSettings((s) => ({ ...s, ...p })), []);

  /* Every view is a separate page as far as the reader is concerned, so each
     one starts at its own top. Without this, leaving a long page like Analysis
     dropped you into the middle of the next one -- and returning to the
     landing showed it already scrolled past its own headline. */
  useEffect(() => { window.scrollTo(0, 0); }, [view, entered, live]);

  const verdict = useMemo(() => verdictFor(plan, now), [plan, now]);

  const nightPasses = useMemo(
    () => (plan && night ? plan.candidates.filter((p) => p.night === night) : []),
    [plan, night]);

  const elementAge = useMemo(() => {
    if (!plan) return '—';
    const mins = Math.round((now - utc(plan.generated).getTime()) / 60_000);
    return mins < 60 ? `${Math.max(0, mins)}m` : `${Math.floor(mins / 60)}h`;
  }, [plan, now]);

  const rival = useMemo(() => {
    if (!explain || !plan) return null;
    if (explain.selected) {
      // Whichever unscheduled pass named this one as the slot it wanted.
      return plan.candidates.find((c) => !c.selected
        && c.conflicts.some((k) => k.norad_id === explain.norad_id
          && k.aos === explain.aos)) ?? null;
    }
    const first = explain.conflicts[0];
    return first
      ? plan.candidates.find((c) => c.norad_id === first.norad_id
          && c.aos === first.aos) ?? null
      : null;
  }, [explain, plan]);

  const pick = useCallback((p: Pass) => { setSelected(p); setExplain(null); }, []);

  const trackFor = (p: Pass): TrackPoint[] =>
    p.track.length ? p.track : (tracks[p.norad_id + p.aos] ?? []);

  if (live && plan) {
    return <LiveMode passes={plan.passes} now={now} onExit={() => setLive(false)} />;
  }

  if (!entered || !plan) {
    return (
      <Landing settings={settings} stations={stations} busy={busy}
        error={error} onChange={patch} onPlan={planAndEnter} />
    );
  }

  return (
    <div className="app">
      <Nav view={view} plan={plan} elementAge={elementAge} busy={busy}
        settingsOpen={settingsOpen} onView={setView}
        onSettings={() => setSettingsOpen((o) => !o)}
        onLive={() => setLive(true)} onHome={() => setEntered(false)} />

      {settingsOpen && (
        <SettingsPanel settings={settings} stations={stations} busy={busy}
          onChange={patch} onRun={run} onLocate={locate}
          onClose={() => setSettingsOpen(false)} />
      )}

      {error && (
        <div className="band"><div className="wrap">
          <p className="banner banner-error">
            <span className="sq sq-sm sq-err" aria-hidden="true" />{error}
          </p>
        </div></div>
      )}

      {plan && !night && !busy && (
        <div className="band"><div className="wrap pad-lg boot">
          <p className="t-page">Nothing above the horizon.</p>
          <p className="t-body muted">
            No pass in this window cleared the visibility floor. Try a longer
            planning horizon, a lower elevation mask, or radio mode.
          </p>
        </div></div>
      )}

      {plan && night && (
        <main>
          {view === 'overview' && (
            <Overview plan={plan} verdict={verdict} elementAge={elementAge}
              onView={setView} />
          )}

          {view === 'planner' && (
            <Planner plan={plan} night={night} passes={nightPasses}
              selectedId={selected?.__id ?? null} onNight={setNight}
              onSelect={pick} />
          )}

          {view === 'passes' && (
            <section className="band">
              <div className="wrap pad-md">
                <header className="sec-head">
                  <h1 className="t-page">Satellite passes</h1>
                  <p className="t-body muted sec-lede">
                    Every pass that cleared the visibility floor across the whole
                    window, scheduled or not.
                  </p>
                </header>
                <PassExplorer passes={plan.candidates}
                  selectedId={selected?.__id ?? null} onSelect={pick} />
              </div>
            </section>
          )}

          {view === 'weather' && (
            <Weather plan={plan} night={night} passes={nightPasses} />
          )}

          {view === 'schedule' && (
            <Schedule night={night} siteName={plan.site.name} passes={nightPasses}
              icsHref={icsUrl(settings)} onSelect={pick} onRecalculate={run} />
          )}

          {view === 'analysis' && <Analysis />}
          {view === 'experiments' && <Experiments />}
        </main>
      )}

      {selected && (
        <PassDetail pass={selected} track={trackFor(selected)}
          onClose={() => setSelected(null)} onExplain={setExplain}
          icsHref={icsUrl(settings)} />
      )}

      {explain && (
        <DecisionPanel pass={explain} rival={rival}
          onClose={() => setExplain(null)} onOpen={pick} />
      )}

      {plan && (
        <footer className="band band-dark app-foot">
          <div className="wrap pad-sm app-foot-in">
            <p className="t-meta">
              SkyPass · weather-aware satellite transit planning. Every figure
              comes from the same package the paper validates.
            </p>
            <p className="t-meta num">
              {plan.funnel.catalogue.toLocaleString()} objects ·{' '}
              {plan.propagations.toLocaleString()} SGP4 calls ·{' '}
              {plan.runtime_s}s
            </p>
          </div>
        </footer>
      )}
    </div>
  );
}
