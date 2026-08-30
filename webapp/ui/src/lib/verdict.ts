import type { Interval, Pass, Plan } from '../types';
import { confidentDays, WEATHER } from './research';
import { utc } from './time';

/* Turning a plan into a decision.
 *
 * exp4 found weather-awareness is worth about nothing to an observer who goes
 * out every night (-1.5%) and a great deal to one who picks nights (+55.0%).
 * The useful output is therefore a recommendation about tonight and a ranking
 * of nights -- not a catalogue of passes. This module makes that call, says
 * why, and states how far ahead the forecast can still be trusted.
 */

export type Call = 'go' | 'marginal' | 'skip' | 'none';

export interface Verdict {
  call: Call;
  headline: string;
  reason: string;
  best: Pass | null;
  tonight: Pass[];
  /** Darkness window intersected with usable forecast, if one exists. */
  window: Interval | null;
  clearSky: number | null;
  scheduled: number;
  confidence: 'high' | 'medium' | 'low';
  confidentDays: number;
}

/** Worth leaving the house for: high enough and bright enough to find. */
export const isGood = (p: Pass): boolean =>
  p.el_max >= 25 && (p.magnitude === null || p.magnitude <= 4.5);

/** Cloud fraction at or below which a night reads as usable. */
export const CLEAR = 0.4;

export { confidentDays };

const overlap = (a: Interval, b: Interval): Interval | null => {
  const s = Math.max(utc(a.from).getTime(), utc(b.from).getTime());
  const e = Math.min(utc(a.to).getTime(), utc(b.to).getTime());
  return s < e
    ? { from: new Date(s).toISOString().slice(0, 19),
        to: new Date(e).toISOString().slice(0, 19) }
    : null;
};

/** The run of dark hours whose forecast is usable -- where to actually work. */
export function bestWindow(plan: Plan, from: number): Interval | null {
  const dark = plan.darkness.filter((d) => utc(d.to).getTime() > from);
  if (!dark.length) return null;
  if (!plan.hourly.length) return dark[0] ?? null;

  // Contiguous runs of hours under the clear threshold.
  const runs: Interval[] = [];
  let start: string | null = null;
  for (const h of plan.hourly) {
    if (h.cloud <= CLEAR) {
      start ??= h.t;
    } else if (start) {
      runs.push({ from: start, to: h.t });
      start = null;
    }
  }
  if (start) {
    const last = plan.hourly[plan.hourly.length - 1];
    if (last) runs.push({ from: start, to: last.t });
  }

  let best: Interval | null = null;
  let span = 0;
  for (const d of dark) {
    for (const r of runs) {
      const o = overlap(d, r);
      if (!o) continue;
      const len = utc(o.to).getTime() - utc(o.from).getTime();
      if (len > span) { span = len; best = o; }
    }
  }
  // No clear run inside darkness: the dark window is still the honest answer.
  return best ?? dark[0] ?? null;
}

export function verdictFor(plan: Plan | null, now: number): Verdict | null {
  if (!plan) return null;

  const pool = plan.passes.length ? plan.passes : plan.if_clear;
  const nights = [...new Set(pool.map((p) => p.night))].sort();
  const first = nights[0];
  const tonight = first
    ? pool.filter((p) => p.night === first && utc(p.los).getTime() > now)
    : [];

  const clouds = tonight.map((p) => p.cloud).filter((c): c is number => c != null);
  const meanCloud = clouds.length
    ? clouds.reduce((a, b) => a + b, 0) / clouds.length : null;
  const clearSky = meanCloud === null ? null : 1 - meanCloud;

  const good = tonight.filter(isGood);
  const best = [...tonight].sort((a, b) => b.score - a.score)[0] ?? null;
  const days = confidentDays();
  const window = bestWindow(plan, now);

  // Confidence is a property of the forecast horizon, not of this night.
  const horizon = Number(plan.window.days);
  const confidence = !plan.weather_used ? 'low'
    : horizon <= days ? 'high' : horizon <= days + 2 ? 'medium' : 'low';

  const base = {
    best, tonight, window, clearSky, scheduled: tonight.length,
    confidence, confidentDays: days,
  } as const;

  if (!tonight.length) {
    return {
      ...base, call: 'none',
      headline: 'Nothing left tonight.',
      reason: 'No observable passes remain in this window. Try a longer '
        + 'horizon, a lower elevation mask, or radio mode.',
    };
  }

  if (plan.weather_used && meanCloud !== null && meanCloud > 0.75) {
    return {
      ...base, call: 'skip',
      headline: 'Not worth observing.',
      reason: `${Math.round(meanCloud * 100)}% cloud is forecast across `
        + `${tonight.length} pass${tonight.length === 1 ? '' : 'es'}. `
        + `Cloud varies ${WEATHER.betweenWithinRatio}× more between nights than `
        + 'within one, so the effort is better spent on a clearer night.',
    };
  }

  if (good.length && (meanCloud === null || meanCloud <= CLEAR)) {
    return {
      ...base, call: 'go',
      headline: 'Worth observing.',
      reason: `${good.length} high-quality optical pass`
        + `${good.length === 1 ? '' : 'es'} `
        + (window ? 'coincide with a clear-sky window tonight. ' : 'tonight. ')
        + `Best culminates at ${best?.el_max ?? 0}° ${best?.dir_tca ?? ''}.`,
    };
  }

  return {
    ...base, call: 'marginal',
    headline: 'Marginal tonight.',
    reason: good.length
      ? `${good.length} usable pass${good.length === 1 ? '' : 'es'}`
        + (meanCloud !== null ? `, but ${Math.round(meanCloud * 100)}% cloud` : '')
        + '. Worth setting up only if you are already outside.'
      : 'Everything above the horizon tonight is low or faint. Nothing here '
        + 'justifies setting an alarm.',
  };
}
