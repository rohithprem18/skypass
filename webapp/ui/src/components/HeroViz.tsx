import { useMemo } from 'react';
import type { Pass } from '../types';
import { hhmmss } from '../lib/time';

/* The observing geometry, drawn to scale from the pass itself.
 *
 * Topocentric range and culmination elevation fix the satellite's geocentric
 * radius exactly, by the law of cosines on the observer-centre-satellite
 * triangle:
 *
 *     r^2 = Re^2 + rho^2 + 2 Re rho sin(E)
 *
 * so the orbit drawn here sits at the altitude this pass actually reaches
 * rather than at a height chosen to look right. Everything else -- the limb,
 * the mask cone, the terminator -- follows from the same construction.
 */

const RE_KM = 6371;

interface Props { pass: Pass | null; maskDeg: number }

/** Deterministic star field: a fixed seed keeps it still across re-renders. */
function stars(n: number): { x: number; y: number; r: number; o: number }[] {
  let seed = 0x5ee1;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  return Array.from({ length: n }, () => {
    const t = rnd();
    return {
      x: rnd() * 720,
      y: rnd() * 380,
      r: t < 0.82 ? 0.6 : t < 0.96 ? 0.9 : 1.3,
      o: 0.18 + rnd() * 0.42,
    };
  });
}

export function HeroViz({ pass, maskDeg }: Props) {
  const field = useMemo(() => stars(150), []);

  const geom = useMemo(() => {
    // Fallback geometry keeps the diagram truthful when nothing is selected:
    // a typical low-Earth orbit rather than an invented one.
    const elMax = pass ? pass.el_max : 55;
    const rho = pass && pass.range_km > 0 ? pass.range_km : 780;
    const E = (elMax * Math.PI) / 180;
    const r = Math.sqrt(RE_KM * RE_KM + rho * rho + 2 * RE_KM * rho * Math.sin(E));
    const altKm = Math.max(120, r - RE_KM);

    // Projection: Earth centre far below the frame, limb through the observer.
    const cx = 360;
    const cy = 1180;
    const R = 900;                       // Earth radius in user units
    const perKm = R / RE_KM;
    const orbitR = R + altKm * perKm;

    // Half-angle of the drawn arc, from the geocentric angle the pass spans.
    const central = Math.acos(Math.min(1, (RE_KM * Math.cos(E)) / r));
    const half = Math.max(0.26, Math.min(0.85, central * 1.9));

    const pt = (radius: number, a: number) => ({
      x: cx + radius * Math.sin(a),
      y: cy - radius * Math.cos(a),
    });

    const obs = pt(R, 0);
    const arc = Array.from({ length: 81 }, (_, i) => {
      const a = -half + (2 * half * i) / 80;
      return pt(orbitR, a);
    });
    const sat = pt(orbitR, 0);

    // Mask cone: the lowest lines of sight the site actually accepts.
    const coneLen = orbitR - R + 240;
    const cone = [maskDeg, 180 - maskDeg].map((deg) => {
      const a = (deg * Math.PI) / 180;
      return { x: obs.x + coneLen * Math.cos(a), y: obs.y - coneLen * Math.sin(a) };
    });

    return { cx, cy, R, orbitR, obs, arc, sat, cone, altKm, elMax, half, pt };
  }, [pass, maskDeg]);

  const d = (pts: { x: number; y: number }[]) =>
    pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');

  const { cx, cy, R, obs, arc, sat, cone, altKm, elMax } = geom;
  const lead = arc.slice(0, 41);

  return (
    <figure className="viz">
      <svg viewBox="0 0 720 520" className="viz-svg" role="img"
        aria-label={pass
          ? `Observing geometry for ${pass.name}, culminating at ${pass.el_max} degrees`
          : 'Observing geometry'}>
        <rect x="0" y="0" width="720" height="520" fill="#000000" />

        {field.map((s, i) => (
          <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="#FFFFFF"
            opacity={s.o} />
        ))}

        {/* Terminator: the boundary the site has to cross before it is dark. */}
        <path className="viz-term"
          d={`M 0 ${cy - R * 1.02} Q 360 ${cy - R - 130} 720 ${cy - R * 0.86}`} />
        <text className="viz-tick" x="14" y={cy - R * 1.02 - 12}>TWILIGHT BOUNDARY</text>

        {/* Earth limb. */}
        <circle className="viz-earth" cx={cx} cy={cy} r={R} />
        <circle className="viz-atmos" cx={cx} cy={cy} r={R + 26} />

        {/* Mask cone: everything below these lines is refused. */}
        <path className="viz-cone"
          d={`M ${cone[0]!.x} ${cone[0]!.y} L ${obs.x} ${obs.y} L ${cone[1]!.x} ${cone[1]!.y}`} />
        <text className="viz-tick" x={cone[1]!.x + 6} y={cone[1]!.y}>
          {maskDeg}° MASK
        </text>

        {/* Orbit: gray where unobserved, accent across the observed arc. */}
        <path className="viz-orbit" d={d(arc)} />
        <path className="viz-orbit-sel" d={d(lead)} />

        {/* Line of sight at culmination. */}
        <line className="viz-los" x1={obs.x} y1={obs.y} x2={sat.x} y2={sat.y} />

        <circle className="viz-sat" cx={sat.x} cy={sat.y} r="5" />
        <circle className="viz-obs" cx={obs.x} cy={obs.y} r="4" />
        <text className="viz-tick" x={obs.x + 12} y={obs.y + 4}>OBSERVER</text>

        <text className="viz-tick" x={sat.x + 14} y={sat.y - 14}>
          {Math.round(altKm).toLocaleString()} KM
        </text>
      </svg>

      <figcaption className="viz-cap">
        <span className="viz-cap-name">{pass ? pass.name : 'No pass selected'}</span>
        <span className="viz-cap-grid">
          <span className="metric">
            <span className="metric-k">Max elev.</span>
            <span className="viz-cap-v num">{elMax.toFixed(1)}°</span>
          </span>
          <span className="metric">
            <span className="metric-k">Culmination</span>
            <span className="viz-cap-v num">
              {pass ? `${hhmmss(pass.tca)} UTC` : '—'}
            </span>
          </span>
          <span className="metric">
            <span className="metric-k">Azimuth</span>
            <span className="viz-cap-v num">
              {pass ? `${Math.round(pass.az_tca)}° ${pass.dir_tca}` : '—'}
            </span>
          </span>
        </span>
      </figcaption>
    </figure>
  );
}
