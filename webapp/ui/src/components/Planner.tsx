import type { Pass, Plan } from '../types';
import { NightStrip } from './NightStrip';
import { Timeline } from './Timeline';
import { nightAxis } from '../lib/night';
import { hhmm, longDay } from '../lib/time';

/* The planner: pick a night, then read it on one time axis.
 *
 * Night selection carries the weather value (exp4), so it stays permanently on
 * screen rather than scrolling away once a night is chosen. Side by side, the
 * choice and its consequence are visible at once -- click down the list and
 * the timeline answers beside it, with no scrolling between the two.
 */

interface Props {
  plan: Plan;
  night: string;
  passes: Pass[];
  selectedId: number | null;
  onNight: (n: string) => void;
  onSelect: (p: Pass) => void;
}

export function Planner({ plan, night, passes, selectedId, onNight,
                          onSelect }: Props) {
  const axis = nightAxis(plan, passes);
  const dark = axis.darkness;
  const scheduled = passes.filter((p) => p.selected).length;
  const conflicts = passes.filter((p) => !p.selected && p.conflicts.length).length;

  return (
    <section className="band">
      <div className="wrap pad-md">
        <header className="sec-head">
          <h1 className="t-page">Observation planner</h1>
          <p className="t-body muted sec-lede">
            {plan.nights.length} night{plan.nights.length === 1 ? '' : 's'} in
            this window. Select one to work it out on the timeline.
          </p>
        </header>

        <div className="planner">
          <aside className="planner-nights">
            <p className="t-label planner-nights-k">Nights</p>
            <NightStrip nights={plan.nights} active={night} onPick={onNight} />
          </aside>

          <div className="planner-main">
            <header className="tl-head">
              <div>
                <h2 className="t-section">{longDay(night)}</h2>
                <p className="t-meta num">
                  {dark.length
                    ? `Dark sky · ${hhmm(dark[0]!.from)} — `
                      + `${hhmm(dark[dark.length - 1]!.to)} UTC`
                    : 'The sky never gets dark in this window'}
                </p>
              </div>
              <dl className="tl-facts">
                <div className="metric">
                  <dt className="metric-k">Candidates</dt>
                  <dd className="tl-fact-v num">{passes.length}</dd>
                </div>
                <div className="metric">
                  <dt className="metric-k">Scheduled</dt>
                  <dd className="tl-fact-v num">{scheduled}</dd>
                </div>
                <div className="metric">
                  <dt className="metric-k">Conflicts</dt>
                  <dd className="tl-fact-v num">{conflicts}</dd>
                </div>
              </dl>
            </header>

            <Timeline night={night} passes={passes} darkness={dark}
              bands={axis.bands} hourly={axis.hourly}
              selectedId={selectedId} onSelect={onSelect} />

            <ul className="tl-legend">
              <li><span className="lg lg-sel" aria-hidden="true" />Scheduled</li>
              <li><span className="lg lg-conf" aria-hidden="true" />Lost a conflict</li>
              <li><span className="lg lg-cand" aria-hidden="true" />Candidate</li>
              <li><span className="lg lg-dark" aria-hidden="true" />Astronomical dark</li>
              <li><span className="lg lg-twi" aria-hidden="true" />Twilight</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
