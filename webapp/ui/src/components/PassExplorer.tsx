import { useMemo, useState } from 'react';
import type { Pass } from '../types';
import { hhmmss, mag, pct } from '../lib/time';

/* A scientific database view of the candidate set.
 *
 * Every row is a pass that cleared the visibility floor, scheduled or not.
 * Status is text plus a hairline rule rather than a coloured badge per state:
 * with a few hundred rows on screen, badges become the only thing the eye can
 * see, and the numbers are what the observer came for.
 */

type SortKey = 'aos' | 'el_max' | 'cloud' | 'magnitude' | 'score' | 'name';

interface Props {
  passes: Pass[];
  selectedId: number | null;
  onSelect: (p: Pass) => void;
}

const COLUMNS: [SortKey | null, string, boolean][] = [
  ['name', 'Satellite', false],
  [null, 'NORAD', true],
  ['aos', 'AOS', true],
  [null, 'Max', true],
  [null, 'LOS', true],
  ['el_max', 'Elev', true],
  ['cloud', 'Cloud', true],
  [null, 'Sunlit', true],
  ['magnitude', 'Mag', true],
  ['score', 'Score', true],
  [null, 'Status', false],
];

export function PassExplorer({ passes, selectedId, onSelect }: Props) {
  const [q, setQ] = useState('');
  const [minEl, setMinEl] = useState(false);
  const [lowCloud, setLowCloud] = useState(false);
  const [sunlitOnly, setSunlitOnly] = useState(false);
  const [scheduledOnly, setScheduledOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>('aos');
  const [desc, setDesc] = useState(false);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = passes.filter((p) => {
      if (needle && !p.name.toLowerCase().includes(needle)
          && !String(p.norad_id).includes(needle)) return false;
      if (minEl && p.el_max < 30) return false;
      if (lowCloud && (p.cloud === null || p.cloud > 0.4)) return false;
      if (sunlitOnly && (p.sunlit === null || p.sunlit < 0.5)) return false;
      if (scheduledOnly && !p.selected) return false;
      return true;
    });
    const dir = desc ? -1 : 1;
    out = [...out].sort((a, b) => {
      const va = a[sort];
      const vb = b[sort];
      if (va === null) return 1;
      if (vb === null) return -1;
      if (typeof va === 'string' && typeof vb === 'string') {
        return dir * va.localeCompare(vb);
      }
      return dir * ((va as number) - (vb as number));
    });
    return out;
  }, [passes, q, minEl, lowCloud, sunlitOnly, scheduledOnly, sort, desc]);

  const click = (key: SortKey | null) => {
    if (!key) return;
    if (key === sort) setDesc((d) => !d);
    else { setSort(key); setDesc(key !== 'aos' && key !== 'name'); }
  };

  return (
    <>
      <div className="explorer-bar">
        <input
          className="input explorer-search"
          type="search"
          placeholder="Search satellite or NORAD ID…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search satellites"
        />
        <div className="explorer-chips">
          <button type="button" className={'chip' + (minEl ? ' is-on' : '')}
            aria-pressed={minEl} onClick={() => setMinEl((v) => !v)}>
            Min elevation ≥ 30°
          </button>
          <button type="button" className={'chip' + (lowCloud ? ' is-on' : '')}
            aria-pressed={lowCloud} onClick={() => setLowCloud((v) => !v)}>
            Cloud ≤ 40%
          </button>
          <button type="button" className={'chip' + (sunlitOnly ? ' is-on' : '')}
            aria-pressed={sunlitOnly} onClick={() => setSunlitOnly((v) => !v)}>
            Sunlit only
          </button>
          <button type="button"
            className={'chip' + (scheduledOnly ? ' is-on' : '')}
            aria-pressed={scheduledOnly}
            onClick={() => setScheduledOnly((v) => !v)}>
            Scheduled
          </button>
        </div>
      </div>

      <p className="t-meta explorer-count num">
        {rows.length.toLocaleString()} of {passes.length.toLocaleString()} passes
      </p>

      <div className="tablewrap explorer-table">
        <table className="data">
          <thead>
            <tr>
              {COLUMNS.map(([key, label, right]) => (
                <th key={label} scope="col"
                  className={(key ? 'sortable ' : '') + (right ? 'ta-end' : '')}
                  aria-sort={key && key === sort
                    ? (desc ? 'descending' : 'ascending') : undefined}
                  onClick={() => click(key)}>
                  {label}
                  {key === sort && <span aria-hidden="true">{desc ? ' ↓' : ' ↑'}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.norad_id + p.aos}
                className={(p.selected ? 'is-scheduled'
                  : p.conflicts.length ? 'is-conflict' : '')
                  + (p.__id != null && p.__id === selectedId ? ' is-sel' : '')}
                onClick={() => onSelect(p)}>
                <td className="txt">{p.name}</td>
                <td className="ta-end">{p.norad_id}</td>
                <td className="ta-end">{hhmmss(p.aos)}</td>
                <td className="ta-end">{hhmmss(p.tca)}</td>
                <td className="ta-end">{hhmmss(p.los)}</td>
                <td className="ta-end">{p.el_max.toFixed(1)}°</td>
                <td className="ta-end">{pct(p.cloud)}</td>
                <td className="ta-end">{pct(p.sunlit)}</td>
                <td className="ta-end">{mag(p.magnitude)}</td>
                <td className="ta-end">{p.score.toFixed(2)}</td>
                <td className="txt">
                  <span className="status">
                    {p.selected
                      ? <><span className="sq sq-sm" aria-hidden="true" />Selected</>
                      : p.conflicts.length
                        ? <><span className="sq sq-sm sq-muted" aria-hidden="true" />Conflict</>
                        : <span className="muted">Candidate</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <p className="explorer-empty t-body muted">
            No passes match these filters.
          </p>
        )}
      </div>
    </>
  );
}
