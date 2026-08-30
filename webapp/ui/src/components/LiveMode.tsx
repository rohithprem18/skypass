import { useMemo } from 'react';
import type { Pass } from '../types';
import { clock, hhmmss, pct, utc } from '../lib/time';

/* The screen that gets used outdoors, in the dark, next to a telescope.
 *
 * Everything else in the console is a planning surface; this one is an
 * instrument. Very large type, very few values, no navigation to get lost in,
 * and no interaction required while the observer's hands are on the mount.
 * The trajectory shows where the object is now against where it is going.
 */

interface Props {
  passes: Pass[];
  now: number;
  onExit: () => void;
}

export function LiveMode({ passes, now, onExit }: Props) {
  const state = useMemo(() => {
    const upcoming = passes
      .filter((p) => p.selected && utc(p.los).getTime() > now)
      .sort((a, b) => a.aos.localeCompare(b.aos));
    const current = upcoming[0] ?? null;
    const next = upcoming[1] ?? null;
    if (!current) return { current: null, next: null, live: false, ms: 0, at: null };

    const aos = utc(current.aos).getTime();
    const live = now >= aos;
    // Where the object is right now, from the sampled track.
    let at: { az: number; el: number } | null = null;
    if (live && current.track.length) {
      let closest = current.track[0]!;
      let best = Infinity;
      for (const t of current.track) {
        const d = Math.abs(utc(t.t).getTime() - now);
        if (d < best) { best = d; closest = t; }
      }
      at = { az: closest.az, el: closest.el };
    }
    return { current, next, live, ms: live ? utc(current.los).getTime() - now : aos - now, at };
  }, [passes, now]);

  const { current, next, live, ms, at } = state;

  return (
    <div className="live band-dark">
      <header className="live-top">
        <div className="live-brand">
          <span className="nav-mark">SkyPass</span>
          <span className="live-tag">
            <span className="sq sq-sm" aria-hidden="true" />
            Live observation
          </span>
        </div>
        <button type="button" className="btn btn-outline btn-sm" onClick={onExit}>
          Exit
        </button>
      </header>

      {current ? (
        <main className="live-main">
          <p className="live-name">{current.name}</p>

          <p className="t-label live-event">{live ? 'Loss of signal in' : 'AOS in'}</p>
          <p className="live-clock num">{clock(ms)}</p>

          <Trajectory pass={current} at={at} />

          <dl className="live-grid">
            <div className="metric">
              <dt className="metric-k">Azimuth</dt>
              <dd className="live-v num">
                {at ? `${Math.round(at.az)}°` : `${Math.round(current.az_aos)}°`}{' '}
                {at ? '' : current.dir_aos}
              </dd>
            </div>
            <div className="metric">
              <dt className="metric-k">Elevation</dt>
              <dd className="live-v num">
                {at ? `${at.el.toFixed(1)}°` : '—'}
              </dd>
            </div>
            <div className="metric">
              <dt className="metric-k">Max</dt>
              <dd className="live-v num">{current.el_max.toFixed(1)}°</dd>
            </div>
          </dl>
        </main>
      ) : (
        <main className="live-main">
          <p className="t-page">No scheduled passes remaining.</p>
          <p className="t-body muted">
            Nothing further tonight. Exit to plan another night.
          </p>
        </main>
      )}

      <footer className="live-foot">
        <div className="metric">
          <span className="metric-k">Next</span>
          <span className="live-foot-v num">
            {next ? `${next.name} · ${hhmmss(next.aos)}` : '—'}
          </span>
        </div>
        <div className="live-foot-right">
          <div className="metric">
            <span className="metric-k">Cloud</span>
            <span className="live-foot-v num">
              {current ? pct(current.cloud) : '—'}
            </span>
          </div>
          <div className="metric">
            <span className="metric-k">Forecast</span>
            <span className="live-foot-v">
              {current?.cloud == null ? '—'
                : current.cloud <= 0.4 ? 'Clear'
                  : current.cloud <= 0.7 ? 'Broken' : 'Overcast'}
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function Trajectory({ pass, at }: {
  pass: Pass; at: { az: number; el: number } | null;
}) {
  const W = 640;
  const H = 120;
  const PAD = 24;

  if (pass.track.length < 2) return <div className="live-traj-empty" />;

  const t0 = utc(pass.track[0]!.t).getTime();
  const t1 = utc(pass.track[pass.track.length - 1]!.t).getTime();
  const x = (t: string) =>
    PAD + ((utc(t).getTime() - t0) / Math.max(1, t1 - t0)) * (W - 2 * PAD);
  const y = (el: number) => H - 14 - (Math.max(0, el) / 90) * (H - 32);

  const d = pass.track
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} ${y(p.el).toFixed(1)}`)
    .join(' ');

  // Current position, matched by elevation along the sampled arc.
  const cur = at
    ? pass.track.reduce((a, b) =>
        Math.abs(b.el - at.el) < Math.abs(a.el - at.el) ? b : a, pass.track[0]!)
    : null;

  return (
    <svg className="live-traj" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Trajectory peaking at ${pass.el_max} degrees`}>
      <line className="live-horizon" x1={PAD} y1={y(0)} x2={W - PAD} y2={y(0)} />
      <path className="live-path" d={d} />
      {cur && <circle className="live-now" cx={x(cur.t)} cy={y(cur.el)} r="6" />}
      <text className="c-label" x={PAD} y={H - 2}>{pass.dir_aos}</text>
      <text className="c-label" x={W - PAD} y={H - 2} textAnchor="end">
        {pass.dir_los}
      </text>
    </svg>
  );
}
