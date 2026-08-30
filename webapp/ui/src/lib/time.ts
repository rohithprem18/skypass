/* The planner speaks UTC. A mission console shows UTC too -- it is the frame
 * every element set, forecast hour and log entry is already in, and converting
 * silently is how observation logs end up an hour wrong. Local time is offered
 * where the observer needs to be somewhere at a moment, and labelled when it is.
 */

export const utc = (iso: string): Date => new Date(iso + 'Z');

/** HH:MM in UTC -- the console default. */
export const hhmm = (iso: string): string =>
  utc(iso).toISOString().slice(11, 16);

/** HH:MM:SS in UTC, for AOS/culmination/LOS where seconds matter. */
export const hhmmss = (iso: string): string =>
  utc(iso).toISOString().slice(11, 19);

/** Local wall-clock time, for the one place the observer stands. */
export const localHM = (iso: string): string =>
  utc(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

/** Fractional hours since UTC midnight -- the timeline's x coordinate. */
export function hoursOfDay(iso: string): number {
  const d = utc(iso);
  return d.getUTCHours() + d.getUTCMinutes() / 60 + d.getUTCSeconds() / 3600;
}

export const dayKey = (iso: string): string => iso.slice(0, 10);

/** "MON 31" -- the seven-night strip header. */
export function shortDay(dateIso: string): { dow: string; day: string } {
  const d = new Date(dateIso + 'T00:00:00Z');
  return {
    dow: d.toLocaleDateString('en-GB', { weekday: 'short', timeZone: 'UTC' })
      .toUpperCase(),
    day: String(d.getUTCDate()).padStart(2, '0'),
  };
}

/** "Tuesday · September 01" */
export function longDay(dateIso: string): string {
  const d = new Date(dateIso + 'T00:00:00Z');
  const wd = d.toLocaleDateString('en-GB', { weekday: 'long', timeZone: 'UTC' });
  const mo = d.toLocaleDateString('en-GB', { month: 'long', timeZone: 'UTC' });
  return `${wd} · ${mo} ${String(d.getUTCDate()).padStart(2, '0')}`;
}

/** "30 AUG — 05 SEP" for the navigation window field. */
export function windowLabel(fromIso: string, toIso: string): string {
  const f = (s: string) => {
    const d = utc(s);
    return `${String(d.getUTCDate()).padStart(2, '0')} `
      + d.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })
        .toUpperCase();
  };
  return `${f(fromIso)} — ${f(toIso)}`;
}

export function dayLabel(iso: string): string {
  const d = utc(iso);
  const now = new Date();
  const same = (a: Date, b: Date) => a.toDateString() === b.toDateString();
  if (same(d, now)) return 'Tonight';
  if (same(d, new Date(now.getTime() + 86_400_000))) return 'Tomorrow';
  return d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
}

export function duration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  return m >= 1 ? `${m}m ${String(seconds % 60).padStart(2, '0')}s` : `${seconds}s`;
}

/** HH:MM:SS countdown -- the live-mode clock reads to the second. */
export function clock(ms: number): string {
  if (ms <= 0) return '00:00:00';
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return [h, m, s % 60].map((v) => String(v).padStart(2, '0')).join(':');
}

export function countdown(ms: number): string {
  if (ms <= 0) return 'now';
  const s = Math.floor(ms / 1000);
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d) return `${d}d ${h}h`;
  if (h) return `${h}h ${m}m`;
  return `${m}m ${s % 60}s`;
}

export function brightness(mag: number | null): string | null {
  if (mag === null) return null;
  if (mag <= 0) return 'brilliant';
  if (mag <= 2) return 'bright';
  if (mag <= 4) return 'easy';
  if (mag <= 5.5) return 'faint';
  return 'very faint';
}

/** Signed magnitude, because the sign is the whole story below zero. */
export const mag = (m: number | null): string =>
  m === null ? '—' : (m > 0 ? `+${m.toFixed(1)}` : m.toFixed(1));

export const pct = (v: number | null, digits = 0): string =>
  v === null ? '—' : `${(v * 100).toFixed(digits)}%`;
