import type { Funnel } from '../types';

/* The pipeline as a status strip, not an architecture diagram.
 *
 * An observer does not need the block diagram; they need to know the run
 * completed and how much survived each filter. Green marks the stages that
 * actually produced something, so a stage that emptied the list is visible at
 * a glance instead of hidden in a number.
 */

interface Props {
  funnel: Funnel;
  mode: 'optical' | 'radio';
  runtimeS: number;
  propagations: number;
  weatherUsed: boolean;
  elementAge: string;
}

export function Pipeline({ funnel: f, mode, runtimeS, propagations,
                           weatherUsed, elementAge }: Props) {
  const stages: [string, string, boolean][] = [
    ['TLE', elementAge, true],
    ['SGP4', `${propagations.toLocaleString()} calls`, propagations > 0],
    ['Pass extraction', f.geometric.toLocaleString(), f.geometric > 0],
    ...(mode === 'optical'
      ? ([['Visibility', f.bright.toLocaleString(), f.bright > 0]] as [string, string, boolean][])
      : []),
    ['Weather', weatherUsed ? `${f.clear.toLocaleString()} clear` : 'not used',
      weatherUsed && f.clear > 0],
    ['Scheduler', `${f.scheduled} selected`, f.scheduled > 0],
    ['Calendar', f.scheduled > 0 ? 'ready' : 'empty', f.scheduled > 0],
  ];

  return (
    <div className="pipe">
      <div className="pipe-stages">
        {stages.map(([label, value, on], i) => (
          <div key={label} className={'pipe-stage' + (on ? ' is-on' : '')}>
            {i > 0 && <span className="pipe-arrow" aria-hidden="true" />}
            <span className="pipe-body">
              <span className="pipe-k">{label}</span>
              <span className="pipe-v">
                <span className={'sq sq-sm' + (on ? '' : ' sq-muted')}
                  aria-hidden="true" />
                <span className="num">{value}</span>
              </span>
            </span>
          </div>
        ))}
      </div>
      <p className="pipe-note t-meta num">
        {f.catalogue.toLocaleString()} objects propagated in {runtimeS}s
      </p>
    </div>
  );
}
