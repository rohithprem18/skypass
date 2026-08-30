import type { Crossing, HourCloud, Interval, Pass, Plan } from '../types';

/* The extent of one observing night.
 *
 * Both the timeline and the weather matrix draw a single night out of a
 * multi-day plan, and both need the same answer to the same question: where
 * does this night start and stop? Deriving it from the passes alone gives a
 * window a few minutes wide when a night holds one pass; deriving it from
 * darkness alone ignores passes that sit in twilight either side. The union of
 * the two, padded by an hour, is what a reader expects to see.
 */

export interface NightAxis {
  from: string | null;
  to: string | null;
  darkness: Interval[];
  bands: Record<string, Interval[]>;
  hourly: HourCloud[];
  twilight: Record<string, Crossing[]>;
}

const shift = (iso: string, hours: number): string =>
  new Date(new Date(iso + 'Z').getTime() + hours * 3_600_000)
    .toISOString().slice(0, 19);

export function nightAxis(plan: Plan, passes: Pass[]): NightAxis {
  const empty: NightAxis = { from: null, to: null, darkness: [], bands: {},
                             hourly: [], twilight: {} };
  if (!passes.length) return empty;

  const first = passes[0]!;
  const pFrom = passes.reduce((a, p) => (p.aos < a ? p.aos : a), first.aos);
  const pTo = passes.reduce((a, p) => (p.los > a ? p.los : a), first.los);

  const darkness = plan.darkness.filter(
    (d) => d.from < shift(pTo, 1) && shift(pFrom, -1) < d.to);

  // Union of the passes and the darkness that surrounds them, then padded.
  const lo = darkness.length && darkness[0]!.from < pFrom ? darkness[0]!.from : pFrom;
  const hiDark = darkness.length ? darkness[darkness.length - 1]!.to : pTo;
  const hi = hiDark > pTo ? hiDark : pTo;
  const from = shift(lo, -1);
  const to = shift(hi, 1);

  return {
    from,
    to,
    darkness,
    bands: Object.fromEntries(
      Object.entries(plan.bands ?? {}).map(([k, v]) =>
        [k, v.filter((b) => b.from < to && from < b.to)])),
    /* One sample either side of the window is kept so the cloud trace reaches
       both edges of the chart. Filtering strictly inside it made the line
       begin in mid-air at whatever value the first in-range hour happened to
       hold, which reads as a broken chart rather than as weather. */
    hourly: (() => {
      const inside = plan.hourly.filter((h) => h.t >= from && h.t <= to);
      const before = [...plan.hourly].reverse().find((h) => h.t < from);
      const after = plan.hourly.find((h) => h.t > to);
      return [...(before ? [before] : []), ...inside, ...(after ? [after] : [])];
    })(),
    twilight: Object.fromEntries(
      Object.entries(plan.twilight).map(([k, v]) =>
        [k, v.filter((c) => c.t >= from && c.t <= to)])),
  };
}
