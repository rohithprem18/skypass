import { useMemo } from 'react';
import type { Interval, Pass, Plan } from '../types';
import { nightAxis } from '../lib/night';
import { FORECAST, confidentDays } from '../lib/research';
import { hhmm, longDay, utc } from '../lib/time';

/* Weather, as an observer needs it: not a forecast page but a matrix of
 * whether each hour is worth being outside for. Cloud alone does not decide
 * that -- an hour is only useful when the sky is also dark and something is
 * actually passing over -- so all three rows share one column.
 */

interface Props {
  plan: Plan;
  night: string;
  passes: Pass[];
}

const inAny = (ms: number, spans: Interval[]) =>
  spans.some((s) => utc(s.from).getTime() <= ms && ms < utc(s.to).getTime());

export function Weather({ plan, night, passes }: Props) {
  const cols = useMemo(() => {
    const HOUR = 3_600_000;
    const axis = nightAxis(plan, passes);
    const times = axis.from && axis.to
      ? [utc(axis.from).getTime(), utc(axis.to).getTime()]
      : plan.hourly.map((h) => utc(h.t).getTime());
    if (!times.length) return [];
    const t0 = Math.floor(Math.min(...times) / HOUR) * HOUR;
    const t1 = Math.ceil(Math.max(...times) / HOUR) * HOUR;

    const cloudAt = new Map(
      plan.hourly.map((h) => [Math.floor(utc(h.t).getTime() / HOUR) * HOUR, h.cloud]),
    );

    const out = [];
    for (let t = t0; t <= t1; t += HOUR) {
      const overlapping = passes.filter(
        (p) => utc(p.aos).getTime() < t + HOUR && t < utc(p.los).getTime());
      out.push({
        t,
        label: hhmm(new Date(t).toISOString().slice(0, 19)),
        cloud: cloudAt.get(t) ?? null,
        dark: inAny(t + HOUR / 2, plan.darkness),
        passes: overlapping.length,
        selected: overlapping.filter((p) => p.selected).length,
      });
    }
    return out;
  }, [plan, passes]);

  const days = confidentDays();

  return (
    <>
      <section className="band">
        <div className="wrap pad-lg">
          <header className="sec-head">
            <h1 className="t-page">Observation weather</h1>
            <p className="t-body muted sec-lede">
              Hour by hour for {longDay(night)}. An hour earns the accent only when the
              sky is dark, the cloud is workable, and something is actually
              overhead.
            </p>
          </header>

          {cols.length ? (
            <div className="matrix-wrap">
              <table className="matrix">
                <thead>
                  <tr>
                    <th scope="col" className="t-label">Time</th>
                    {cols.map((c) => (
                      <th key={c.t} scope="col" className="num">{c.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row" className="t-label">Cloud</th>
                    {cols.map((c) => (
                      <td key={c.t}
                        className={'num' + (c.cloud !== null && c.cloud <= 0.4
                          ? ' is-good' : '')}>
                        {c.cloud === null ? '—' : Math.round(c.cloud * 100)}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="t-label">Dark sky</th>
                    {cols.map((c) => (
                      <td key={c.t} className={c.dark ? 'is-good' : ''}>
                        {c.dark
                          ? <span className="sq sq-sm" aria-label="dark" />
                          : <span className="muted" aria-label="not dark">—</span>}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="t-label">Passes</th>
                    {cols.map((c) => (
                      <td key={c.t} className="num">
                        {c.passes || <span className="muted">0</span>}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row" className="t-label">Selected</th>
                    {cols.map((c) => (
                      <td key={c.t}
                        className={'num' + (c.selected ? ' is-good' : '')}>
                        {c.selected || <span className="muted">0</span>}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          ) : (
            <p className="t-body muted">
              No forecast hours available for this night.
            </p>
          )}
        </div>
      </section>

      {/* ------------------------------------------ forecast reliability -- */}
      <section className="band">
        <hr className="rule" />
        <div className="wrap pad-lg reliability">
          <div className="reliability-text">
            <h2 className="t-page">How far should you trust the forecast?</h2>
            <p className="t-body muted sec-lede">
              Forecast skill exceeds persistence primarily through approximately
              day three. Long-range recommendations therefore receive reduced
              confidence rather than being presented as equally certain.
            </p>
            <dl className="reliability-facts">
              <div className="metric">
                <dt className="metric-k">Day 1 skill</dt>
                <dd className="metric-v num">{FORECAST.day1}</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Day 7 skill</dt>
                <dd className="metric-v num">{FORECAST.day7}</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Persistence</dt>
                <dd className="metric-v num">{FORECAST.persistence}</dd>
              </div>
            </dl>
          </div>

          <SkillChart days={days} />
        </div>
      </section>
    </>
  );
}

function SkillChart({ days }: { days: number }) {
  const W = 560;
  const H = 320;
  const PAD = { l: 46, r: 24, t: 24, b: 46 };
  const series = FORECAST.skillByLead.slice(1);       // leads 1..7
  const maxY = 0.4;

  const x = (lead: number) =>
    PAD.l + ((lead - 1) / 6) * (W - PAD.l - PAD.r);
  const y = (v: number) => H - PAD.b - (v / maxY) * (H - PAD.t - PAD.b);

  const d = series
    .map((v, i) => `${i ? 'L' : 'M'}${x(i + 1).toFixed(1)} ${y(v).toFixed(1)}`)
    .join(' ');

  return (
    <figure className="reliability-chart">
      <svg className="chart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label="Heidke skill score against forecast lead time, compared with 24-hour persistence">
        {[0, 0.1, 0.2, 0.3, 0.4].map((v) => (
          <g key={v}>
            <line className="c-grid" x1={PAD.l} y1={y(v)} x2={W - PAD.r} y2={y(v)} />
            <text className="c-label" x={PAD.l - 8} y={y(v) + 3} textAnchor="end">
              {v.toFixed(2)}
            </text>
          </g>
        ))}

        {/* Persistence: the baseline the forecast has to beat to be worth using. */}
        <line className="c-compare" x1={PAD.l} y1={y(FORECAST.persistence)}
          x2={W - PAD.r} y2={y(FORECAST.persistence)} />
        <text className="c-label" x={W - PAD.r} y={y(FORECAST.persistence) - 7}
          textAnchor="end">24-HOUR PERSISTENCE</text>

        {/* Planning horizon: where skill stops beating the baseline. */}
        <line className="rel-marker" x1={x(days + 0.5)} y1={PAD.t}
          x2={x(days + 0.5)} y2={H - PAD.b} />
        <text className="c-label-strong" x={x(days + 0.5) + 7} y={PAD.t + 11}>
          RECOMMENDED
        </text>
        <text className="c-label-strong" x={x(days + 0.5) + 7} y={PAD.t + 25}>
          PLANNING HORIZON
        </text>

        <path className="c-series" d={d} />
        {series.map((v, i) => (
          <circle key={i} className="c-dot" cx={x(i + 1)} cy={y(v)} r="4" />
        ))}

        <line className="c-axis" x1={PAD.l} y1={H - PAD.b} x2={W - PAD.r}
          y2={H - PAD.b} />
        {series.map((_, i) => (
          <text key={i} className="c-label" x={x(i + 1)} y={H - PAD.b + 16}
            textAnchor="middle">{i + 1}</text>
        ))}
        <text className="c-label" x={(W + PAD.l) / 2} y={H - 10}
          textAnchor="middle">FORECAST LEAD · DAYS</text>
        <text className="c-label" x={14} y={PAD.t - 8}>HEIDKE SKILL SCORE</text>
      </svg>
    </figure>
  );
}
