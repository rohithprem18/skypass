import type { Pass } from '../types';
import { hhmmss, mag, pct } from '../lib/time';

/* Why the scheduler chose what it chose.
 *
 * The comparison is the point. A single opaque score invites the reader to
 * either trust it or ignore it; putting the winner and the loser side by side
 * on the four terms that actually enter the objective lets an observer
 * disagree with the weighting, which is the only kind of explanation worth
 * showing. The footer names the algorithm because "optimal" is a claim, and a
 * claim should say what it is optimal under.
 */

interface Props {
  pass: Pass;
  rival: Pass | null;
  onClose: () => void;
  onOpen: (p: Pass) => void;
}

type Row = {
  key: string;
  a: string;
  b: string;
  /** True when the left-hand pass is better on this term. */
  aWins: boolean | null;
};

function rows(win: Pass, lose: Pass): Row[] {
  const cmp = (x: number | null, y: number | null, higher: boolean) => {
    if (x === null || y === null) return null;
    return higher ? x > y : x < y;
  };
  return [
    { key: 'Elevation', a: `${win.el_max}°`, b: `${lose.el_max}°`,
      aWins: cmp(win.el_max, lose.el_max, true) },
    { key: 'Cloud', a: pct(win.cloud), b: pct(lose.cloud),
      aWins: cmp(win.cloud, lose.cloud, false) },
    { key: 'Sunlit', a: pct(win.sunlit), b: pct(lose.sunlit),
      aWins: cmp(win.sunlit, lose.sunlit, true) },
    { key: 'Magnitude', a: mag(win.magnitude), b: mag(lose.magnitude),
      aWins: cmp(win.magnitude, lose.magnitude, false) },
    { key: 'Score', a: win.score.toFixed(2), b: lose.score.toFixed(2),
      aWins: cmp(win.score, lose.score, true) },
  ];
}

const REASON: Record<string, string> = {
  Elevation: 'Higher culmination',
  Cloud: 'Lower cloud probability',
  Sunlit: 'Greater sunlit fraction',
  Magnitude: 'Brighter at culmination',
};

export function DecisionPanel({ pass, rival, onClose, onOpen }: Props) {
  // Orient the panel around whichever pass actually won its slot.
  const win = pass.selected ? pass : rival;
  const lose = pass.selected ? rival : pass;

  return (
    <aside className="band band-dark decision" aria-label="Scheduler decision">
      <div className="decision-in">
        <header className="decision-head">
          <p className="t-label">Scheduler decision</p>
          <button type="button" className="icon-btn" onClick={onClose}
            aria-label="Close">
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none"
              stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
              <path d="M3 3l10 10M13 3L3 13" strokeLinecap="round" />
            </svg>
          </button>
        </header>

        <h2 className="t-section decision-name">{(win ?? pass).name}</h2>
        <p className="decision-status">
          {(win ?? pass).selected
            ? <><span className="sq sq-sm" aria-hidden="true" /> Selected</>
            : <><span className="sq sq-sm sq-muted" aria-hidden="true" /> Not scheduled</>}
          <span className="muted num">
            {' '}· {hhmmss((win ?? pass).aos)} UTC
          </span>
        </p>

        <p className="decision-score num">{(win ?? pass).score.toFixed(2)}</p>
        <p className="t-label">Objective value</p>

        {win && lose ? (
          <>
            <table className="decision-table">
              <thead>
                <tr>
                  <th scope="col"><span className="sr-only">Term</span></th>
                  <th scope="col" className="is-win">{win.name}</th>
                  <th scope="col">
                    <button type="button" className="decision-rival"
                      onClick={() => onOpen(lose)}>{lose.name}</button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows(win, lose).map((r) => (
                  <tr key={r.key}>
                    <th scope="row" className="t-label">{r.key}</th>
                    <td className={'num' + (r.aWins === true ? ' is-win' : '')}>
                      {r.a}
                    </td>
                    <td className={'num' + (r.aWins === false ? ' is-win' : '')}>
                      {r.b}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="t-label decision-why-k">Why selected</p>
            <ul className="decision-why">
              {rows(win, lose)
                .filter((r) => r.aWins === true && REASON[r.key])
                .map((r) => (
                  <li key={r.key}>
                    <span className="sq sq-sm" aria-hidden="true" />
                    {REASON[r.key]}
                  </li>
                ))}
              <li>
                <span className="sq sq-sm" aria-hidden="true" />
                Higher objective value in a conflicting slot
              </li>
            </ul>
          </>
        ) : (
          <p className="t-body decision-solo">
            {pass.selected
              ? 'This pass took its slot uncontested — nothing else above the '
                + 'visibility floor overlapped it.'
              : 'This pass was not scheduled and did not conflict with a '
                + 'selected pass. It fell below the objective threshold, or the '
                + 'per-night capacity was already spent.'}
          </p>
        )}

        <footer className="decision-foot">
          <span className="sq sq-sm" aria-hidden="true" />
          <span className="t-label-lg">Optimal</span>
          <span className="t-meta">
            Weighted interval scheduling · exact dynamic programming
          </span>
        </footer>
      </div>
    </aside>
  );
}

