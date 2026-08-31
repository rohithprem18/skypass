import type { Settings, Station } from '../types';
import { useEffect, useRef } from 'react';
import { usePlanningStatus } from '../lib/loading';
import { PROPAGATION, SCHEDULER, WEATHER } from '../lib/research';

/* The front door.
 *
 * Nothing is planned until someone asks for it. Propagating a catalogue takes
 * real seconds and real network, so the console opens on a question rather
 * than on the results of a run nobody requested -- which also means a reload
 * never silently replans against yesterday's settings.
 */

interface Props {
  settings: Settings;
  stations: Station[];
  busy: boolean;
  error: string | null;
  onChange: (patch: Partial<Settings>) => void;
  onPlan: () => void;
  onResearch?: () => void;
}

export function Landing({ settings: s, stations, busy, error,
                          onChange, onPlan, onResearch }: Props) {
  const usingCoords = s.lat.trim() !== '' && s.lon.trim() !== '';
  const status = usePlanningStatus(busy);
  /* The clip is 1.4 seconds. At normal speed the loop restarts often enough to
     read as a stutter behind the text; slowing it stretches each cycle to
     roughly three seconds. */
  const video = useRef<HTMLVideoElement>(null);
  useEffect(() => { if (video.current) video.current.playbackRate = 0.45; }, []);

  return (
    <div className="landing">
      {/* The subject of the product, behind the page that sells it. Muted and
          looping so it never asks for attention, and covered by a scrim that
          keeps the headline and the form at full contrast: the video is
          atmosphere, not something anyone has to read through. */}
      <div className="lp-bg" aria-hidden="true">
        <video ref={video} className="lp-bg-video" autoPlay muted loop
          playsInline preload="auto" disablePictureInPicture
          src="/landing-bg.mp4" />
        <div className="lp-bg-scrim" />
      </div>

      {/* ------------------------------------------------------------ top -- */}
      <header className="band band-dark">
        <div className="wrap lp-top" style={{ justifyContent: 'space-between' }}>
          <span className="nav-mark">SkyPass</span>
          {onResearch && (
            <button type="button" className="btn btn-quiet btn-sm" onClick={onResearch}>
              Research & Experiments →
            </button>
          )}
        </div>
      </header>

      {/* ----------------------------------------------------------- hero -- */}
      <section className="band band-dark">
        <div className="wrap pad-lg lp-hero">
          <div className="lp-hero-text">
            <p className="hero-eyebrow">
              <span className="sq sq-sm" aria-hidden="true" />
              Ground-station observation planning
            </p>

            <h1 className="lp-title">
              Choose the night,<br />not just the pass.
            </h1>

            <p className="t-body lp-lede">
              SkyPass propagates the catalogue, works out what is actually
              visible from your site, checks the cloud forecast against it, and
              resolves overlapping passes into a schedule you can export. One
              pipeline, validated end to end.
            </p>

            <dl className="lp-proof">
              <div className="metric">
                <dt className="metric-k">Clear-sky yield</dt>
                <dd className="lp-proof-v num">+{WEATHER.budgetGain}%</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Propagator cost</dt>
                <dd className="lp-proof-v num">{PROPAGATION.reduction}× lower</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Conflict resolution</dt>
                <dd className="lp-proof-v num">
                  {SCHEDULER.exactDp.toFixed(0)}% optimal
                </dd>
              </div>
            </dl>
          </div>

          {/* The plan form is the hero's product image: the whole interface
              exists to answer the question this panel asks. */}
          <form className="lp-form" onSubmit={(e) => { e.preventDefault(); onPlan(); }}>
            <p className="t-label lp-form-k">Plan an observing window</p>

            <label className="field">
              <span className="field-k">Ground station</span>
              <select className="select"
                value={usingCoords ? '' : s.station}
                onChange={(e) => onChange({ station: e.target.value, lat: '', lon: '' })}>
                {usingCoords && <option value="">My location</option>}
                {stations.map((st) => (
                  <option key={st.key} value={st.key}>{st.name}</option>
                ))}
              </select>
            </label>

            <div className="lp-form-row">
              <label className="field">
                <span className="field-k">Horizon</span>
                <select className="select" value={s.days}
                  onChange={(e) => onChange({ days: e.target.value })}>
                  <option value="1">24 hours</option>
                  <option value="2">2 days</option>
                  <option value="3">3 days</option>
                  <option value="5">5 days</option>
                  <option value="7">7 days</option>
                </select>
              </label>

              <label className="field">
                <span className="field-k">Mode</span>
                <select className="select" value={s.mode}
                  onChange={(e) => onChange({ mode: e.target.value as Settings['mode'] })}>
                  <option value="optical">Optical</option>
                  <option value="radio">Radio</option>
                </select>
              </label>
            </div>

            <div className="lp-form-row">
              <label className="field">
                <span className="field-k">Horizon mask</span>
                <select className="select" value={s.mask}
                  onChange={(e) => onChange({ mask: e.target.value })}>
                  <option value="5">5°</option>
                  <option value="10">10°</option>
                  <option value="20">20°</option>
                  <option value="30">30°</option>
                </select>
              </label>

              <label className="field">
                <span className="field-k">Passes per night</span>
                <select className="select" value={s.capacity}
                  onChange={(e) => onChange({ capacity: e.target.value })}>
                  <option value="0">No limit</option>
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="5">5</option>
                </select>
              </label>
            </div>

            <label className="check lp-form-check">
              <input type="checkbox" checked={s.weather}
                onChange={(e) => onChange({ weather: e.target.checked })} />
              <span>Use cloud forecast</span>
            </label>

            <button type="submit" aria-busy={busy} disabled={busy}
              className={'btn btn-primary lp-go' + (busy ? ' is-busy' : '')}>
              {busy ? (
                <>
                  <span className="spinner" />
                  <span className="lp-go-phrase">{status.phrase}…</span>
                  <span className="lp-go-clock num">{status.seconds}s</span>
                </>
              ) : 'Plan observations'}
            </button>

            {error && (
              <p className="lp-error">
                <span className="sq sq-sm sq-err" aria-hidden="true" />{error}
              </p>
            )}

            {onResearch && (
              <button
                type="button"
                className="btn btn-outline lp-research-btn"
                onClick={onResearch}
                style={{ marginBlockStart: 'var(--s-3)', inlineSize: '100%' }}
              >
                View Research Analysis & Experiments →
              </button>
            )}
          </form>
        </div>
      </section>

      <footer className="band band-dark">
        <div className="wrap pad-sm app-foot-in">
          <p className="t-meta">
            SkyPass · every figure comes from the same package the paper
            validates.
          </p>
          <p className="t-meta num">
            {PROPAGATION.catalogue} objects · {PROPAGATION.passes.toLocaleString()} passes
          </p>
        </div>
      </footer>
    </div>
  );
}


