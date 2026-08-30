import type { Pass } from '../types';
import { googleCalendarUrl } from '../lib/calendar';
import { duration, hhmmss, longDay, mag, pct } from '../lib/time';

/* The observation plan as a run sheet.
 *
 * This is the one screen that gets used outdoors in the dark, so it is a
 * numbered sequence with times and pointing, not a dashboard. Nothing here is
 * ranked or scored: by this point the decisions are made and what remains is
 * the order of operations.
 */

interface Props {
  night: string;
  siteName: string;
  passes: Pass[];
  icsHref: string;
  onSelect: (p: Pass) => void;
  onRecalculate: () => void;
}

export function Schedule({ night, siteName, passes, icsHref, onSelect,
                           onRecalculate }: Props) {
  const scheduled = passes
    .filter((p) => p.selected)
    .sort((a, b) => a.aos.localeCompare(b.aos));

  const totalS = scheduled.reduce((s, p) => s + p.duration_s, 0);
  const clouds = scheduled.map((p) => p.cloud).filter((c): c is number => c != null);
  const meanCloud = clouds.length
    ? clouds.reduce((a, b) => a + b, 0) / clouds.length : null;
  const firstClear = scheduled.find((p) => p.cloud !== null && p.cloud <= 0.4);

  return (
    <>
      <section className="band band-dark">
        <div className="wrap pad-md sched-head">
          <div className="sched-title-col">
            <p className="t-label">
              {scheduled.length ? (
                <><span className="sq sq-sm" aria-hidden="true" /> Observation plan ready</>
              ) : 'Observation plan'}
            </p>
            <h1 className="t-page sched-title">{longDay(night)}</h1>

            <div className="sched-actions">
              <a className={'btn btn-primary' + (scheduled.length ? '' : ' is-off')}
                href={icsHref} aria-disabled={!scheduled.length}>
                Export .ICS
              </a>

              <button type="button" className="btn-link" onClick={onRecalculate}>
                Recalculate <span aria-hidden="true">-&gt;</span>
              </button>
            </div>
            <p className="t-meta sched-actions-note">
              The .ics carries every observation at once and imports into Google
              Calendar, Apple Calendar or Outlook. Individual passes can be added
              to Google Calendar from the sheet below.
            </p>
          </div>

          <dl className="sched-facts">
            <div className="metric">
              <dt className="metric-k">Forecast</dt>
              <dd className="sched-v">
                {meanCloud === null ? 'Not used'
                  : firstClear ? `Clear from ${hhmmss(firstClear.aos).slice(0, 5)}`
                    : `${Math.round(meanCloud * 100)}% mean cloud`}
              </dd>
            </div>
            <div className="metric">
              <dt className="metric-k">Observations</dt>
              <dd className="sched-v num">{scheduled.length}</dd>
            </div>
            <div className="metric">
              <dt className="metric-k">Total on sky</dt>
              <dd className="sched-v num">{Math.round(totalS / 60)} min</dd>
            </div>
          </dl>
        </div>
      </section>

      <section className="band">
        <div className="wrap pad-md">
          {scheduled.length ? (
            <RunSheet scheduled={scheduled} siteName={siteName}
              onSelect={onSelect} />
          ) : (
            <p className="t-body muted">
              Nothing scheduled for this night. Either the forecast ruled it out
              or nothing cleared the visibility floor.
            </p>
          )}
        </div>
      </section>
    </>
  );
}

function RunSheet({ scheduled, siteName, onSelect }: {
  scheduled: Pass[];
  siteName: string;
  onSelect: (p: Pass) => void;
}) {
  return (
    <ol className="runsheet">
      {scheduled.map((p, i) => (
        <li key={p.norad_id + p.aos} className="run-item">
          <button type="button" className="run" onClick={() => onSelect(p)}>
            <span className="run-n num">
              {String(i + 1).padStart(2, '0')}
            </span>

            <span className="run-when">
              <span className="run-time num">{hhmmss(p.aos)}</span>
              <span className="t-meta">UTC</span>
            </span>

            <span className="run-body">
              <span className="run-name">{p.name}</span>
              <span className="t-meta num">
                NORAD {p.norad_id} - {duration(p.duration_s)}
              </span>
            </span>

            <span className="run-grid">
              <span className="metric">
                <span className="metric-k">AOS</span>
                <span className="run-v num">{hhmmss(p.aos)}</span>
              </span>
              <span className="metric">
                <span className="metric-k">Max</span>
                <span className="run-v num">{hhmmss(p.tca)}</span>
              </span>
              <span className="metric">
                <span className="metric-k">LOS</span>
                <span className="run-v num">{hhmmss(p.los)}</span>
              </span>
              <span className="metric">
                <span className="metric-k">Elevation</span>
                <span className="run-v num">{p.el_max.toFixed(1)} deg</span>
              </span>
              <span className="metric">
                <span className="metric-k">Azimuth</span>
                <span className="run-v num">
                  {Math.round(p.az_aos)} deg to {Math.round(p.az_los)} deg
                </span>
              </span>
              <span className="metric">
                <span className="metric-k">Cloud</span>
                <span className="run-v num">{pct(p.cloud)}</span>
              </span>
              <span className="metric">
                <span className="metric-k">Magnitude</span>
                <span className="run-v num">{mag(p.magnitude)}</span>
              </span>
            </span>
          </button>

          <a className="run-gcal" href={googleCalendarUrl(p, siteName)}
            target="_blank" rel="noreferrer noopener"
            onClick={(e) => e.stopPropagation()}>
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none"
              stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <rect x="2" y="3" width="12" height="11" rx="1" />
              <path d="M2 6.5h12M5.5 2v2.5M10.5 2v2.5" />
            </svg>
            Add to Google Calendar
          </a>
        </li>
      ))}
    </ol>
  );
}
