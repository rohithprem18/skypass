import { useEffect, useRef } from 'react';
import type { Settings, Station } from '../types';

/* Every input that changes what gets planned, in one panel.
 *
 * The console has no sidebar, so this is where site, horizon and the scoring
 * constraints live. Each control carries one line saying what it does to the
 * result -- these are not preferences, they change the schedule.
 */

interface Props {
  settings: Settings;
  stations: Station[];
  busy: boolean;
  onChange: (patch: Partial<Settings>) => void;
  onRun: () => void;
  onLocate: () => void;
  onClose: () => void;
}

const canLocate = typeof navigator !== 'undefined'
  && 'geolocation' in navigator && window.isSecureContext;

export function SettingsPanel({ settings: s, stations, busy, onChange, onRun,
                                onLocate, onClose }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!ref.current?.contains(t)
          && !(t instanceof Element && t.closest('[data-gear]'))) onClose();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDown);
    };
  }, [onClose]);

  const usingCoords = s.lat.trim() !== '' && s.lon.trim() !== '';

  return (
    <>
      {/* A scrim, so the panel reads as a layer over the console rather than
          a section spliced into it. Clicking it counts as an outside click. */}
      <div className="settings-scrim" aria-hidden="true" />
      <div className="settings band band-dark" ref={ref} role="dialog"
        aria-modal="true" aria-label="Plan settings">
        <div className="wrap settings-in">
          <div className="settings-grid">
            <label className="field">
              <span className="field-k">Ground station</span>
              <select className="select"
                value={usingCoords ? '' : s.station}
                onChange={(e) => onChange({ station: e.target.value, lat: '', lon: '' })}>
                {usingCoords && <option value="">My location</option>}
                {stations.map((st) => (
                  <option key={st.key} value={st.key}>{st.name}</option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field-k">Planning horizon</span>
              <select className="select" value={s.days}
                onChange={(e) => onChange({ days: e.target.value })}>
                <option value="1">24 hours</option>
                <option value="2">2 days</option>
                <option value="3">3 days</option>
                <option value="5">5 days</option>
                <option value="7">7 days</option>
              </select>
            </label>

            <label className="field">
              <span className="field-k">Mode</span>
              <select className="select" value={s.mode}
                onChange={(e) => onChange({ mode: e.target.value as Settings['mode'] })}>
                <option value="optical">Optical</option>
                <option value="radio">Radio</option>
              </select>
            </label>

            <label className="field">
              <span className="field-k">Horizon mask</span>
              <select className="select" value={s.mask}
                onChange={(e) => onChange({ mask: e.target.value })}>
                <option value="5">5°</option>
                <option value="10">10°</option>
                <option value="20">20°</option>
                <option value="30">30°</option>
              </select>
            </label>

            <label className="field">
              <span className="field-k">Passes per night</span>
              <select className="select" value={s.capacity}
                onChange={(e) => onChange({ capacity: e.target.value })}>
                <option value="0">No limit</option>
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="5">5</option>
              </select>
            </label>

            <div className="field settings-actions">
              <span className="field-k">Run</span>
              <div className="settings-run">
                <button type="button" className="btn btn-primary btn-sm"
                  onClick={onRun} disabled={busy}>
                  {busy ? 'Planning…' : 'Plan'}
                </button>
                {canLocate && (
                  <button type="button" className="btn btn-outline btn-sm"
                    onClick={onLocate}>
                    Use my location
                  </button>
                )}
              </div>
            </div>
          </div>

          <div className="settings-foot">
            <label className="check">
              <input type="checkbox" checked={s.weather}
                onChange={(e) => onChange({ weather: e.target.checked })} />
              <span>Use cloud forecast</span>
            </label>
            <p className="t-meta settings-note">
              A per-night cap is what makes the forecast worth consulting: with no
              limit the scheduler keeps everything that does not overlap, and the
              weather has nothing to decide between.
            </p>
          </div>
          </div>
      </div>
    </>
  );
}
