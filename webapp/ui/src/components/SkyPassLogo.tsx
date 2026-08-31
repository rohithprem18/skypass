export function SkyPassLogo({ animated = true }: { animated?: boolean }) {
  return (
    <div className="skypass-orbit-brand">
      {/* Dashed Orbital Ellipse Ring around SkyPass text */}
      <svg className="skypass-orbit-ring" width="168" height="42" viewBox="0 0 168 42" fill="none" aria-hidden="true">
        <ellipse
          cx="84"
          cy="21"
          rx="76"
          ry="15"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.25"
          strokeDasharray="4 4"
          className="orbit-ellipse-line"
        />
      </svg>

      {/* Orbiting Satellite Figure */}
      <div className={animated ? 'sat-orbit-mover is-animated' : 'sat-orbit-mover'}>
        <svg
          width="26"
          height="26"
          viewBox="0 0 44 44"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="sat-orbit-svg"
          aria-hidden="true"
        >
          <defs>
            <linearGradient id="satSolarGrad" x1="0" y1="0" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#1e3a8a" />
              <stop offset="50%" stopColor="#0284c7" />
              <stop offset="100%" stopColor="#0369a1" />
            </linearGradient>

            <filter id="satGreenGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Emitted Light Beam Line towards SkyPass center */}
          <line x1="24" y1="28" x2="0" y2="44" stroke="#76B900" strokeWidth="2" strokeDasharray="2 2" className="sat-beam-line" />

          {/* 3D Solar Panel Left */}
          <polygon points="3,13 13,7 13,15 3,21" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.75" />

          {/* 3D Solar Panel Right */}
          <polygon points="21,19 31,13 31,21 21,27" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.75" />

          {/* Solar Panel Boom */}
          <line x1="13" y1="11" x2="21" y2="23" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />

          {/* 3D Bus Cube */}
          <polygon points="13,13 21,9 25,13 17,17" fill="#f8fafc" />
          <polygon points="13,13 17,17 17,24 13,20" fill="#cbd5e1" />
          <polygon points="17,17 25,13 25,20 17,24" fill="#94a3b8" />

          {/* Dish */}
          <path d="M16 21 Q 21 26 26 23" fill="none" stroke="#76B900" strokeWidth="2" strokeLinecap="round" />
          <line x1="21" y1="23.5" x2="24" y2="28" stroke="#76B900" strokeWidth="1.5" />

          {/* Glowing Green Emitter */}
          <circle cx="24" cy="28" r="2.5" fill="#76B900" filter="url(#satGreenGlow)" className="sat-emitter" />
          <circle cx="24" cy="28" r="1" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Brand Text in Center */}
      <span className="nav-mark brand-text">SkyPass</span>
    </div>
  );
}
