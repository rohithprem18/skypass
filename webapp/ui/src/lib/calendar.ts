import type { Pass } from '../types';
import { brightness, hhmmss, mag, pct } from './time';

/* Handing a pass to a calendar.
 *
 * Google's template URL creates exactly one event, so it cannot carry a whole
 * night's schedule -- that is what the .ics export is for, and Google Calendar
 * imports those. A per-pass link is still worth having: it is the fastest path
 * to a reminder on a phone for the one pass someone actually cares about.
 */

/** UTC ISO without separators, which is the only format Google accepts. */
const stamp = (iso: string): string => iso.replace(/[-:]/g, '') + 'Z';

export function googleCalendarUrl(p: Pass, site: string): string {
  const word = brightness(p.magnitude);
  const details = [
    `Look ${p.dir_tca} at ${hhmmss(p.tca)} UTC.`,
    `Rises ${p.dir_aos} ${hhmmss(p.aos)}, culminates ${p.el_max}°, `
      + `sets ${p.dir_los} ${hhmmss(p.los)}.`,
    p.magnitude !== null
      ? `Magnitude ${mag(p.magnitude)}${word ? ` (${word})` : ''}.` : '',
    p.cloud !== null ? `Forecast cloud ${pct(p.cloud)}.` : '',
    `NORAD ${p.norad_id}. Planned by SkyPass.`,
  ].filter(Boolean).join('\n');

  const q = new URLSearchParams({
    action: 'TEMPLATE',
    text: `${p.name} pass · ${p.el_max}° ${p.dir_tca}`,
    dates: `${stamp(p.aos)}/${stamp(p.los)}`,
    details,
    location: site,
  });
  return `https://calendar.google.com/calendar/render?${q.toString()}`;
}
