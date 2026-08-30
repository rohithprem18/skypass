import { PROPAGATION, SCHEDULER, TLE_AGE, WEATHER } from '../lib/research';

/* The findings, laid out as an argument rather than a wall of tiles.
 *
 * Each section states one measured result, shows the comparison that makes it
 * mean something, and says what follows for the observer. The accent marks
 * only the SkyPass series; every baseline stays grayscale, so the reader can
 * see which number is the claim.
 */

function Bar({ label, value, max, unit = '%', display, accent = false }: {
  label: string; value: number; max: number; unit?: string;
  display?: string; accent?: boolean;
}) {
  return (
    <div className="abar">
      <div className="abar-head">
        <span className="t-label">{label}</span>
        <span className={'abar-v num' + (accent ? ' accent' : '')}>
          {display ?? `${value.toLocaleString()}${unit}`}
        </span>
      </div>
      <div className="abar-track" aria-hidden="true">
        <i className={'abar-fill' + (accent ? '' : ' abar-muted')}
          style={{ inlineSize: `${Math.max(1.5, (value / max) * 100)}%` }} />
      </div>
    </div>
  );
}

export function Analysis() {
  return (
    <>
      <section className="band">
        <div className="wrap pad-lg">
          <h1 className="t-page analysis-title">What did SkyPass find?</h1>
          <p className="t-body muted sec-lede">
            Eight experiments over archived element sets and reanalysis-verified
            weather. Every figure below is reported in the paper and regenerated
            from the same result files.
          </p>
        </div>
      </section>

      {/* --------------------------------------------- weather awareness -- */}
      <section className="band">
        <hr className="rule" />
        <div className="wrap pad-lg finding">
          <div className="finding-lead">
            <p className="t-label">Weather awareness</p>
            <p className="finding-figure num">+{WEATHER.budgetGain}%</p>
            <p className="t-body muted">Clear-sky observation improvement</p>
          </div>
          <div className="finding-body">
            <div className="abars">
              <Bar label="No weather" value={WEATHER.blindClearRate} max={35} />
              <Bar label="SkyPass" value={WEATHER.clearRate} max={35} accent />
            </div>
            <dl className="finding-facts">
              <div className="metric">
                <dt className="metric-k">Fixed nightly quota</dt>
                <dd className="metric-v num">{WEATHER.quotaGain}%</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Cloud variance, between vs within night</dt>
                <dd className="metric-v num">{WEATHER.betweenWithinRatio}×</dd>
              </div>
            </dl>
            <p className="t-body finding-note">
              Weather awareness matters primarily when the observer can skip poor
              nights. Held to a fixed number of observations every night, the
              same forecast is worth {WEATHER.quotaGain}% — the forecast can only
              reshuffle passes within a night, and cloud barely varies at that
              scale.
            </p>
          </div>
        </div>
      </section>

      {/* -------------------------------------------------- propagation -- */}
      <section className="band">
        <hr className="rule" />
        <div className="wrap pad-lg finding">
          <div className="finding-lead">
            <p className="t-label">Propagation</p>
            <p className="finding-figure num">{PROPAGATION.reduction}×</p>
            <p className="t-body muted">Fewer SGP4 calls</p>
          </div>
          <div className="finding-body">
            <div className="abars">
              {/* Shown as "54.9M", not "54.864": a bare decimal at this scale
                  reads as fifty-four thousand in half the world's locales. */}
              <Bar label="Dense stepping" max={55}
                value={PROPAGATION.naiveCalls / 1e6}
                display={`${(PROPAGATION.naiveCalls / 1e6).toFixed(1)}M`} />
              <Bar label="SkyPass" max={55} accent
                value={PROPAGATION.fastCalls / 1e6}
                display={`${(PROPAGATION.fastCalls / 1e6).toFixed(1)}M`} />
            </div>
            <p className="t-meta">Propagator calls, 635 objects over 7 days</p>
            <dl className="finding-facts">
              <div className="metric">
                <dt className="metric-k">Recall</dt>
                <dd className="metric-v num">{PROPAGATION.recall}%</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Mean culmination error</dt>
                <dd className="metric-v num">{PROPAGATION.meanError} s</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Worst case</dt>
                <dd className="metric-v num">{PROPAGATION.worstError} s</dd>
              </div>
            </dl>
            <p className="t-body finding-note">
              Bracketing horizon crossings on an adaptive coarse step, then
              bisecting, misses {PROPAGATION.missed} of{' '}
              {PROPAGATION.passes.toLocaleString()} passes while agreeing with
              Skyfield to {PROPAGATION.meanError} s at culmination.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------------------------------------------- scheduler -- */}
      <section className="band">
        <hr className="rule" />
        <div className="wrap pad-lg finding">
          <div className="finding-lead">
            <p className="t-label">Scheduler</p>
            <p className="finding-figure num">{SCHEDULER.exactDp.toFixed(2)}%</p>
            <p className="t-body muted">
              Optimal on {SCHEDULER.trials.toLocaleString()} random instances
            </p>
          </div>
          <div className="finding-body">
            <div className="abars">
              <Bar label="Exact DP" value={SCHEDULER.exactDp} max={100} accent />
              <Bar label="Greedy by value" value={SCHEDULER.greedyValue} max={100} />
              <Bar label="Genetic algorithm" value={SCHEDULER.genetic} max={100} />
              <Bar label="Greedy by elevation" value={SCHEDULER.greedyElevation}
                max={100} />
            </div>
            <dl className="finding-facts">
              <div className="metric">
                <dt className="metric-k">Greedy by elevation, worst case</dt>
                <dd className="metric-v num">{SCHEDULER.greedyElevationWorst}%</dd>
              </div>
              <div className="metric">
                <dt className="metric-k">Genetic algorithm cost</dt>
                <dd className="metric-v num">
                  {SCHEDULER.geneticCost.toLocaleString()}×
                </dd>
              </div>
              <div className="metric">
                <dt className="metric-k">
                  {SCHEDULER.bigN.toLocaleString()} intervals
                </dt>
                <dd className="metric-v num">{SCHEDULER.bigMs} ms</dd>
              </div>
            </dl>
            <p className="t-body finding-note">
              Greedy by value is within {(100 - SCHEDULER.greedyValue).toFixed(2)}%
              of optimal on average, so the exact solver is not about beating it
              on the mean. It is about the guarantee: greedy by elevation — the
              heuristic an observer would use by hand — collapses to{' '}
              {SCHEDULER.greedyElevationWorst}% in the worst case, and the exact
              method is the cheapest option on the table.
            </p>
          </div>
        </div>
      </section>

      {/* ----------------------------------------------------- TLE age -- */}
      <section className="band band-dark">
        <div className="wrap pad-lg">
          <header className="sec-head">
            <h2 className="t-page">Fresh orbital data matters.</h2>
            <p className="t-body muted sec-lede">
              Median culmination error against fresh reference orbits, by the age
              of the element set used to predict it.
            </p>
          </header>

          <div className="age">
            {([
              ['Fresh', '< 1 day', TLE_AGE.fresh, 'ok'],
              ['1 week', '7–14 days', TLE_AGE.week, 'ok'],
              ['2 weeks', '14–30 days', TLE_AGE.fortnight, 'warn'],
              ['1 month', '30–90 days', TLE_AGE.month, 'bad'],
            ] as [string, string, number, string][]).map(([k, sub, v, tone]) => (
              <div key={k} className={`age-row age-${tone}`}>
                <div className="age-k">
                  <span className="t-label-lg">{k}</span>
                  <span className="t-meta">{sub}</span>
                </div>
                <div className="age-track" aria-hidden="true">
                  <i className="age-fill"
                    style={{ inlineSize: `${(v / TLE_AGE.month) * 100}%` }} />
                </div>
                <span className="age-v num">{v} s</span>
              </div>
            ))}
          </div>

          <p className="t-meta age-foot num">
            {TLE_AGE.comparisons.toLocaleString()} aged-element comparisons over{' '}
            {TLE_AGE.objects} objects. SkyPass refuses element sets older than
            seven days by default.
          </p>
        </div>
      </section>
    </>
  );
}
