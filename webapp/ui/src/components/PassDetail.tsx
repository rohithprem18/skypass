import type { Pass, TrackPoint } from '../types';
import { duration, hhmmss, mag, pct, utc } from '../lib/time';

/* The single-pass inspector.
 *
 * The elevation curve is the shape of the pass: how long it stays usable, not
 * just how high it gets. Two passes with the same culmination can differ by
 * minutes of workable time, and the curve is the only place that shows it.
 */

interface Props {
  pass: Pass;
  track: TrackPoint[];
  onClose: () => void;
  onExplain: (p: Pass) => void;
  icsHref: string;
}

function ElevationCurve({ pass, track }: { pass: Pass; track: TrackPoint[] }) {
  const W = 460;
  const H = 150;
  const PAD = { l: 30, r: 12, t: 10, b: 22 };

  if (track.length < 2) {
    return (
      <div className="curve-empty t-meta">
        Elevation profile unavailable for this pass.
      </div>
    );
  }

  const t0 = utc(track[0]!.t).getTime();
  const t1 = utc(track[track.length - 1]!.t).getTime();
  const span = Math.max(1, t1 - t0);
  const x = (t: string) =>
    PAD.l + ((utc(t).getTime() - t0) / span) * (W - PAD.l - PAD.r);
  const y = (el: number) =>
    H - PAD.b - (Math.max(0, el) / 90) * (H - PAD.t - PAD.b);

  const d = track
    .map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} ${y(p.el).toFixed(1)}`)
    .join(' ');
  const area = `${d} L${x(track[track.length - 1]!.t).toFixed(1)} ${H - PAD.b}`
    + ` L${x(track[0]!.t).toFixed(1)} ${H - PAD.b} Z`;

  const peak = track.reduce((a, b) => (b.el > a.el ? b : a), track[0]!);

  return (
    <svg className="chart curve" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Elevation profile peaking at ${pass.el_max} degrees`}>
      {[0, 30, 60, 90].map((el) => (
        <g key={el}>
          <line className="c-grid" x1={PAD.l} y1={y(el)} x2={W - PAD.r} y2={y(el)} />
          <text className="c-label" x={PAD.l - 6} y={y(el) + 3} textAnchor="end">
            {el}°
          </text>
        </g>
      ))}
      <path className="c-area" d={area} />
      <path className="c-series" d={d} />
      <circle className="c-dot" cx={x(peak.t)} cy={y(peak.el)} r="3.5" />
      <line className="c-grid" x1={x(peak.t)} y1={y(peak.el)} x2={x(peak.t)}
        y2={H - PAD.b} />

      <line className="c-axis" x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r}
        y2={H - PAD.b} />
      <text className="c-label" x={PAD.l} y={H - 6}>AOS</text>
      <text className="c-label" x={x(peak.t)} y={H - 6} textAnchor="middle">MAX</text>
      <text className="c-label" x={W - PAD.r} y={H - 6} textAnchor="end">LOS</text>
    </svg>
  );
}

export function PassDetail({ pass, track, onClose, onExplain, icsHref }: Props) {
  const specs: [string, string][] = [
    ['AOS', `${hhmmss(pass.aos)} UTC`],
    ['Culmination', `${hhmmss(pass.tca)} UTC`],
    ['LOS', `${hhmmss(pass.los)} UTC`],
    ['Max elevation', `${pass.el_max.toFixed(1)}°`],
    ['Azimuth', `${Math.round(pass.az_aos)}° → ${Math.round(pass.az_los)}°`],
    ['Duration', duration(pass.duration_s)],
    ['Range at max', `${pass.range_km.toLocaleString()} km`],
    ['Sunlit', pct(pass.sunlit)],
    ['Cloud', pct(pass.cloud)],
    ['Magnitude', mag(pass.magnitude)],
    ['Score', pass.score.toFixed(2)],
  ];

  return (
    <aside className="inspector" aria-label={`${pass.name} detail`}>
      <header className="band-dark inspector-head">
        <div className="inspector-title">
          <h2 className="t-panel">{pass.name}</h2>
          <p className="t-meta num">NORAD {pass.norad_id}</p>
        </div>
        <p className="inspector-status">
          {pass.selected
            ? <><span className="sq sq-sm" aria-hidden="true" /> Scheduled</>
            : pass.conflicts.length
              ? <><span className="sq sq-sm sq-muted" aria-hidden="true" /> Conflict</>
              : <span className="muted">Candidate</span>}
        </p>
        <button type="button" className="icon-btn" onClick={onClose}
          aria-label="Close detail">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none"
            stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
            <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
          </svg>
        </button>
      </header>

      <div className="inspector-body">
        <ElevationCurve pass={pass} track={track} />

        <dl className="inspector-specs">
          {specs.map(([k, v]) => (
            <div key={k} className="metric">
              <dt className="metric-k">{k}</dt>
              <dd className="inspector-v num">{v}</dd>
            </div>
          ))}
        </dl>

        {pass.conflicts.length > 0 && (
          <p className="inspector-conflict t-meta">
            Overlaps {pass.conflicts.map((c) => c.name).join(', ')}.
          </p>
        )}
      </div>

      <footer className="inspector-foot">
        <button type="button" className="btn btn-quiet btn-sm"
          onClick={() => onExplain(pass)}>
          Why this decision
        </button>
        <a className="btn btn-primary btn-sm" href={icsHref}>Add to schedule</a>
      </footer>
    </aside>
  );
}

