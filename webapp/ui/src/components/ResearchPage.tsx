import { Analysis } from './Analysis';
import { Experiments } from './Experiments';
import { PROPAGATION } from '../lib/research';

interface Props {
  onBack: () => void;
}

export function ResearchPage({ onBack }: Props) {
  return (
    <div className="research-page">
      <header className="band band-dark nav">
        <div className="wrap nav-in">
          <button type="button" className="nav-brand" onClick={onBack} title="Back to planning setup">
            <span className="nav-mark">SkyPass</span>
          </button>

          <div style={{ marginInlineStart: 'auto', display: 'flex', gap: 'var(--s-3)' }}>
            <button type="button" className="btn btn-outline btn-sm" onClick={onBack}>
              ← Back to Planning
            </button>
          </div>
        </div>
      </header>

      <main className="research-content">
        <Analysis />
        <Experiments />
      </main>

      <footer className="band band-dark app-foot">
        <div className="wrap pad-sm app-foot-in">
          <p className="t-meta">
            SkyPass · every figure comes from the same package the paper validates.
          </p>
          <p className="t-meta num">
            {PROPAGATION.catalogue} objects · {PROPAGATION.passes.toLocaleString()} passes
          </p>
        </div>
      </footer>
    </div>
  );
}
