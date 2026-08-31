import type { Plan, View } from '../types';
import { windowLabel } from '../lib/time';

/* Top navigation. No sidebar: a planning console spends its width on the
 * night, not on a permanent list of links. The active view is marked with the
 * accent and nothing else -- underline plus weight, no filled pill. */

const VIEWS: [View, string][] = [
  ['overview', 'Overview'],
  ['planner', 'Planner'],
  ['passes', 'Passes'],
  ['weather', 'Weather'],
  ['schedule', 'Schedule'],
];


interface Props {
  view: View;
  plan: Plan | null;
  elementAge: string;
  busy: boolean;
  settingsOpen: boolean;
  onView: (v: View) => void;
  onSettings: () => void;
  onLive: () => void;
  onHome: () => void;
}

export function Nav({ view, plan, elementAge, busy, settingsOpen,
                      onView, onSettings, onLive, onHome }: Props) {
  return (
    <header className="nav">
      <div className="wrap nav-in">
        <button type="button" className="nav-brand" onClick={onHome}
          title="Back to planning setup">
          <span className="nav-mark">SkyPass</span>
        </button>

        <nav className="nav-links" aria-label="Sections">
          {VIEWS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={'nav-link' + (view === key ? ' is-on' : '')}
              aria-current={view === key ? 'page' : undefined}
              onClick={() => onView(key)}
            >
              {label}
            </button>
          ))}
        </nav>

        <div className="nav-meta">
          {plan && (
            <>
              <div className="nav-field nav-hide-md">
                <span className="nav-k">Location</span>
                <span className="nav-v">{plan.site.name}</span>
              </div>
              <div className="nav-field nav-hide-md">
                <span className="nav-k">Window</span>
                <span className="nav-v num">
                  {windowLabel(plan.window.from, plan.window.to)}
                </span>
              </div>
            </>
          )}

          <span className="nav-status">
            {busy
              ? <><span className="spinner" />Planning</>
              : <><span className="sq sq-sm" aria-hidden="true" />
                  <span className="num">TLE · {elementAge}</span></>}
          </span>

          <button type="button" className="icon-btn" onClick={onLive}
            aria-label="Observation mode" title="Observation mode">
            <svg width="17" height="17" viewBox="0 0 20 20" fill="none"
              stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <circle cx="10" cy="10" r="2.5" />
              <path d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3" />
            </svg>
          </button>

          <button type="button"
            className={'icon-btn' + (settingsOpen ? ' is-on' : '')}
            data-gear onClick={onSettings} aria-expanded={settingsOpen}
            aria-label="Plan settings" title="Plan settings">
            <svg width="17" height="17" viewBox="0 0 20 20" fill="none"
              stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
              <circle cx="10" cy="10" r="2.6" />
              <path d="M10 1.6v2.2M10 16.2v2.2M3.1 6l1.9 1.1M15 12.9l1.9 1.1M3.1 14l1.9-1.1M15 7.1L16.9 6" />
            </svg>
          </button>
        </div>
      </div>
    </header>
  );
}
