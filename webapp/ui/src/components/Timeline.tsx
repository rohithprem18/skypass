import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { HourCloud, Interval, Pass } from '../types';
import { hhmm, utc } from '../lib/time';

/* The night on one time axis.
 *
 * Four registers share a single x scale so they can be read against each
 * other, which is the whole point: a pass is only worth anything where the
 * darkness band is open and the cloud trace is low. Conflicts are drawn as a
 * connector from the pass that lost to the pass that took its slot, so the
 * scheduler's decision is visible in the same picture as its inputs.
 */

/* An observing night is 8-14 hours, which fits the width of a desktop chart.
   Rather than fix a scale and let the end of the night scroll out of sight --
   taking the schedule labels with it -- the hour width is derived from the
   container, and only an unusually long span falls back to scrolling. */
const MIN_PX_HOUR = 58;
const MAX_PX_HOUR = 150;
const LANE_H = 20;
const ROW = { axis: 30, dark: 30, cloud: 62, gapY: 14, sel: 40 };

/** Lightest to darkest; painted in this order so the bands nest visually. */
const PHASES = ['day', 'civil', 'nautical', 'astronomical'] as const;


interface Props {
  night: string;
  passes: Pass[];               // every candidate on this night
  darkness: Interval[];
  bands: Record<string, Interval[]>;
  hourly: HourCloud[];
  selectedId: number | null;
  onSelect: (p: Pass) => void;
}

/** Greedy lane packing so overlapping passes stack instead of colliding. */
function lanes(passes: Pass[]): Map<Pass, number> {
  const out = new Map<Pass, number>();
  const ends: number[] = [];
  for (const p of [...passes].sort((a, b) => a.aos.localeCompare(b.aos))) {
    const s = utc(p.aos).getTime();
    const e = utc(p.los).getTime();
    let lane = ends.findIndex((t) => t <= s);
    if (lane === -1) { lane = ends.length; ends.push(e); } else { ends[lane] = e; }
    out.set(p, lane);
  }
  return out;
}

export function Timeline({ night, passes, darkness, bands, hourly,
                           selectedId, onSelect }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [avail, setAvail] = useState(0);

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const measure = () => setAvail(el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const model = useMemo(() => {
    if (!passes.length && !darkness.length) return null;

    const times = [
      ...passes.flatMap((p) => [utc(p.aos).getTime(), utc(p.los).getTime()]),
      ...darkness.flatMap((d) => [utc(d.from).getTime(), utc(d.to).getTime()]),
    ];
    if (!times.length) return null;

    const HOUR = 3_600_000;
    const t0 = Math.floor(Math.min(...times) / HOUR) * HOUR - HOUR;
    const t1 = Math.ceil(Math.max(...times) / HOUR) * HOUR + HOUR;
    const hours = Math.max(1, (t1 - t0) / HOUR);
    const pxHour = avail > 0
      ? Math.min(MAX_PX_HOUR, Math.max(MIN_PX_HOUR, avail / hours))
      : MIN_PX_HOUR;
    const width = hours * pxHour;
    const x = (ms: number) => ((ms - t0) / (t1 - t0)) * width;

    const lane = lanes(passes);
    const laneCount = Math.max(1, ...[...lane.values()].map((v) => v + 1));

    const yDark = ROW.axis;
    const yCloud = yDark + ROW.dark + 6;
    const yPass = yCloud + ROW.cloud + ROW.gapY;
    const passH = laneCount * LANE_H;
    const ySel = yPass + passH + ROW.gapY;
    const height = ySel + ROW.sel + 8;

    const ticks = Array.from({ length: hours + 1 }, (_, i) => t0 + i * HOUR);

    // Cloud trace, clipped to the drawn window.
    const pts = hourly
      .map((h) => ({ t: utc(h.t).getTime(), v: h.cloud }))
      .filter((h) => h.t >= t0 - HOUR && h.t <= t1 + HOUR)
      .sort((a, b) => a.t - b.t);
    const cloudPath = pts.length
      ? pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)} `
          + `${(yCloud + ROW.cloud - p.v * ROW.cloud).toFixed(1)}`).join(' ')
      : '';
    const cloudArea = pts.length
      ? `${cloudPath} L${x(pts[pts.length - 1]!.t).toFixed(1)} ${yCloud + ROW.cloud}`
        + ` L${x(pts[0]!.t).toFixed(1)} ${yCloud + ROW.cloud} Z`
      : '';

    return { t0, t1, width, height, x, ticks, lane, yDark, yCloud, yPass,
             ySel, cloudPath, cloudArea, passH };
  }, [passes, darkness, hourly, avail]);

  if (!model) {
    return <p className="t-body muted">No passes on this night.</p>;
  }

  const { width, height, x, ticks, lane, yDark, yCloud, yPass, ySel,
          cloudPath, cloudArea, passH } = model;

  const ordered = passes.filter((p) => p.selected)
    .sort((a, b) => a.aos.localeCompare(b.aos));
  const byId = new Map(passes.map((p) => [p.norad_id + p.aos, p]));

  /* Row labels and the cloud axis live in a static gutter beside the chart
     rather than floating over it. As an overlay they sat on top of the
     darkness band and collided with the chart's own axis text; a real column
     also keeps them readable while the chart scrolls sideways. */
  const rows: [string, number, number][] = [
    ['Darkness', yDark, ROW.dark],
    ['Cloud cover', yCloud, ROW.cloud],
    ['Passes', yPass, passH],
    ['Selected', ySel, ROW.sel],
  ];

  return (
    <div className="tl">
      <div className="tl-gutter" style={{ blockSize: height }} aria-hidden="true">
        {rows.map(([label, top, h]) => (
          <span key={label} className="tl-row-k"
            style={{ insetBlockStart: top, blockSize: h }}>{label}</span>
        ))}
        <span className="tl-axis-v" style={{ insetBlockStart: yCloud - 6 }}>100%</span>
        <span className="tl-axis-v"
          style={{ insetBlockStart: yCloud + ROW.cloud - 8 }}>0%</span>
      </div>

      <div className="tl-scroll" ref={scrollRef}>
        <svg className="tl-svg" width={width} height={height}
          viewBox={`0 0 ${width} ${height}`} role="img"
          aria-label={`Observation timeline for ${night}`}>

          {/* hour grid + axis */}
          {ticks.map((t) => (
            <g key={t}>
              <line className="c-grid" x1={x(t)} y1={ROW.axis - 8} x2={x(t)}
                y2={height} />
              <text className="c-label" x={x(t) + 4} y={16}>
                {hhmm(new Date(t).toISOString().slice(0, 19))}
              </text>
            </g>
          ))}

          {/* Twilight as a graded ramp. The bands nest -- astronomical inside
              nautical inside civil -- so painting them in order gives dusk its
              actual shape instead of a single on/off block. */}
          <rect className="tl-daylight" x="0" y={yDark} width={width}
            height={ROW.dark} />
          {PHASES.map((phase) => (bands[phase] ?? []).map((b) => (
            <rect key={phase + b.from} className={`tl-band tl-band-${phase}`}
              x={x(utc(b.from).getTime())} y={yDark}
              width={Math.max(1, x(utc(b.to).getTime()) - x(utc(b.from).getTime()))}
              height={ROW.dark} />
          )))}
          {/* Only the darkest band is labelled. At low latitudes the four
              thresholds are minutes apart and four labels overlap into an
              unreadable smear; the legend names the rest. */}
          {(bands.astronomical ?? []).map((b) => {
            const px = x(utc(b.from).getTime());
            const w = x(utc(b.to).getTime()) - px;
            return w > 70 ? (
              <text key={`l${b.from}`} className="tl-phase" x={px + 5}
                y={yDark + ROW.dark - 5}>ASTRONOMICAL DARK</text>
            ) : null;
          })}

          {/* cloud cover */}
          {cloudArea && <path className="tl-cloud-area" d={cloudArea} />}
          {cloudPath && <path className="tl-cloud" d={cloudPath} />}
          <line className="c-axis" x1="0" y1={yCloud + ROW.cloud} x2={width}
            y2={yCloud + ROW.cloud} />

          {/* conflict connectors, drawn under the intervals */}
          {passes.filter((p) => !p.selected && p.conflicts.length).map((p) => {
            const c = p.conflicts[0]!;
            const won = byId.get(c.norad_id + c.aos);
            if (!won) return null;
            const y1 = yPass + (lane.get(p) ?? 0) * LANE_H + LANE_H / 2;
            const y2 = yPass + (lane.get(won) ?? 0) * LANE_H + LANE_H / 2;
            const x1 = x(utc(p.aos).getTime());
            const x2 = x(utc(won.aos).getTime());
            return (
              <path key={`c${p.norad_id}${p.aos}`} className="tl-link"
                d={`M${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`} />
            );
          })}

          {/* every candidate pass */}
          {passes.map((p) => {
            const px = x(utc(p.aos).getTime());
            const w = Math.max(3, x(utc(p.los).getTime()) - px);
            const y = yPass + (lane.get(p) ?? 0) * LANE_H;
            const on = p.__id != null && p.__id === selectedId;
            return (
              <g key={p.norad_id + p.aos} className="tl-pass"
                onClick={() => onSelect(p)} role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') onSelect(p); }}>
                <title>{`${p.name} · ${hhmm(p.aos)}–${hhmm(p.los)} · ${p.el_max}°`
                  + (p.selected ? ' · selected' : p.conflicts.length ? ' · conflict' : '')}</title>
                <rect
                  className={'tl-int'
                    + (p.selected ? ' is-sel' : p.conflicts.length ? ' is-conf' : '')
                    + (on ? ' is-focus' : '')}
                  x={px} y={y + 3} width={w} height={LANE_H - 7} rx="1" />
                {/* Deliberately unlabelled. A conflicting pass often starts
                    seconds later, so a name here runs straight across the
                    interval beside it. The schedule row below names what was
                    chosen; everything else carries a tooltip. */}
              </g>
            );
          })}

          {/* The schedule itself, numbered to match the run sheet.
              Eight scheduled passes clustered into two groups drew eight name
              labels on top of each other; a number always fits, and the full
              name is added only where the gap to the next pass can hold it. */}
          <line className="c-axis" x1="0" y1={ySel - 6} x2={width} y2={ySel - 6} />
          {ordered.map((p, i) => {
            const px = x(utc(p.aos).getTime());
            const w = Math.max(3, x(utc(p.los).getTime()) - px);
            const n = String(i + 1).padStart(2, '0');
            const next = ordered[i + 1];
            const room = (next ? x(utc(next.aos).getTime()) : width) - (px + w);
            const full = `${p.name} · ${p.el_max}°`;
            const fits = room > full.length * 5.4 + 26;
            return (
              <g key={`s${p.norad_id}${p.aos}`} className="tl-pass"
                onClick={() => onSelect(p)} role="button" tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter') onSelect(p); }}>
                <title>{`${n} · ${p.name} · ${hhmm(p.aos)} · ${p.el_max}°`}</title>
                <rect className="tl-int is-sel" x={px} y={ySel + 4} width={w}
                  height={LANE_H - 6} rx="1" />
                <text className="tl-int-n" x={px + w / 2} y={ySel + LANE_H + 14}
                  textAnchor="middle">{n}</text>
                {fits && (
                  <text className="tl-int-t" x={px + w + 6}
                    y={ySel + LANE_H - 4}>{full}</text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
