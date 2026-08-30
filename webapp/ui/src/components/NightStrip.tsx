import type { NightSummary } from '../types';
import { shortDay } from '../lib/time';

/* The nights, as a vertical list beside the timeline.
 *
 * This is the screen exp4 argues for: weather-awareness is worth -1.5% to an
 * observer locked into a nightly quota and +55.0% to one who can move effort
 * between nights, so the night -- not the pass -- has to be the thing being
 * compared and chosen.
 *
 * Vertical because the list grows with the planning horizon. Laid out in
 * columns, an eight-night window ran past the width of the page and pushed the
 * timeline below the fold; stacked, it sits beside the timeline at any horizon
 * and every row stays the same shape.
 */

interface Props {
  nights: NightSummary[];
  active: string | null;
  onPick: (night: string) => void;
}

const VERDICT_LABEL: Record<NightSummary['verdict'], string> = {
  best: 'Best night',
  good: 'Good',
  skip: 'Skip',
};

export function NightStrip({ nights, active, onPick }: Props) {
  if (!nights.length) return null;

  return (
    <ol className="nights" role="listbox" aria-label="Observing nights">
      {nights.map((n) => {
        const { dow, day } = shortDay(n.night);
        const cloud = n.cloud === null ? null : Math.round(n.cloud * 100);
        const on = n.verdict !== 'skip';
        const isActive = active === n.night;
        return (
          <li key={n.night}>
            <button
              type="button"
              role="option"
              aria-selected={isActive}
              className={`night night-${n.verdict}` + (isActive ? ' is-active' : '')}
              onClick={() => onPick(n.night)}
            >
              <span className="night-rule" aria-hidden="true" />

              <span className="night-head">
                <span className="night-date">
                  <span className="night-dow">{dow}</span>
                  <span className="night-day num">{day}</span>
                </span>
                <span className="night-tag">
                  {n.verdict === 'best' && (
                    <span className="sq sq-sm" aria-hidden="true" />
                  )}
                  {VERDICT_LABEL[n.verdict]}
                </span>
              </span>

              <span className="night-stats num">
                <span>{cloud === null ? '—' : `${cloud}%`} cloud</span>
                <span className="night-dot" aria-hidden="true">·</span>
                <span>{n.passes} pass{n.passes === 1 ? '' : 'es'}</span>
              </span>

              <span className="night-sel">
                {on && n.selected > 0 && (
                  <span className="sq sq-sm" aria-hidden="true" />
                )}
                <span className="num">
                  {n.selected > 0 ? `${n.selected} selected` : 'none scheduled'}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
