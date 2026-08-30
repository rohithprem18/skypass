import type { Plan, View } from '../types';
import type { Verdict } from '../lib/verdict';
import { HeroViz } from './HeroViz';
import { Pipeline } from './Pipeline';
import { hhmm } from '../lib/time';

/* The overview answers one question and then stops: is observing worth it?
 *
 * Night ranking lives on the Planner and the measured results live on the
 * Analysis page. Repeating either here made the first screen a summary of the
 * rest of the console instead of an answer, so this page carries the verdict,
 * the geometry of the pass it recommends, and the state of the run that
 * produced it. */

interface Props {
  plan: Plan;
  verdict: Verdict | null;
  elementAge: string;
  onView: (v: View) => void;
}

const CONFIDENCE_LABEL = { high: 'High', medium: 'Medium', low: 'Low' } as const;

export function Overview({ plan, verdict, elementAge, onView }: Props) {
  const v = verdict;

  return (
    <>
      {/* ---------------------------------------------------------- hero -- */}
      <section className="band band-dark">
        <div className="wrap pad-lg hero">
          <div className="hero-text">
            <p className="hero-eyebrow">
              <span className="sq sq-sm" aria-hidden="true" />
              Tonight · {plan.site.name.split(',')[0]}
            </p>

            <h1 className="t-hero hero-call">
              {v ? v.headline : 'No plan yet.'}
            </h1>

            <p className="t-body hero-reason">{v?.reason}</p>

            <dl className="hero-metrics">
              <div className="metric">
                <dt className="metric-k">Best window</dt>
                <dd className="metric-v num">
                  {v?.window
                    ? `${hhmm(v.window.from)} — ${hhmm(v.window.to)}`
                    : '—'}
                </dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Clear sky</dt>
                <dd className="metric-v num">
                  {v?.clearSky == null ? '—' : `${Math.round(v.clearSky * 100)}%`}
                </dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Scheduled</dt>
                <dd className="metric-v num">
                  {plan.passes.length} pass{plan.passes.length === 1 ? '' : 'es'}
                </dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Forecast confidence</dt>
                <dd className="metric-v">
                  {v ? CONFIDENCE_LABEL[v.confidence] : '—'}
                </dd>
              </div>
            </dl>

            <div className="hero-actions">
              <button type="button" className="btn btn-primary"
                onClick={() => onView('schedule')}>
                View observation plan
              </button>
              <button type="button" className="btn btn-outline"
                onClick={() => onView('passes')}>
                Explore passes
              </button>
            </div>
          </div>

          <HeroViz pass={v?.best ?? null} maskDeg={plan.site.mask} />
        </div>

        <div className="wrap pad-sm pipe-band">
          <Pipeline funnel={plan.funnel} mode={plan.mode}
            runtimeS={plan.runtime_s} propagations={plan.propagations}
            weatherUsed={plan.weather_used} elementAge={elementAge} />
        </div>
      </section>
    </>
  );
}
