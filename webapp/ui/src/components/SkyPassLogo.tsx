export function SkyPassLogo({ animated = true }: { animated?: boolean }) {
  // Exact mathematical orbit ellipse path shared by both track line and animateMotion
  const pathD = "M 14,21 A 76 13 -6 1 0 166,21 A 76 13 -6 1 0 14,21";

  return (
    <div className="skypass-orbit-brand">
      <svg className="skypass-orbit-svg" width="180" height="42" viewBox="0 0 180 42" fill="none">
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

        {/* The Exact Dotted Orbit Track Line */}
        <path
          d={pathD}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.25"
          strokeDasharray="4 4"
          className="orbit-ellipse-line"
        />

        {/* Orbiting Satellite locked to the Exact Track Path */}
        <g className="sat-motion-group">
          {animated && (
            <animateMotion
              path={pathD}
              dur="6s"
              repeatCount="indefinite"
              rotate="auto"
            />
          )}

          {/* Center offset for satellite figure */}
          <g transform="translate(-14, -14)">
            {/* Green Emitted Beam Line to Center */}
            <line x1="14" y1="14" x2="-6" y2="30" stroke="#76B900" strokeWidth="2" strokeDasharray="2 2" className="sat-beam-line" />

            {/* 3D Solar Panel Left */}
            <polygon points="2,8 9,4 9,10 2,14" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.6" />

            {/* 3D Solar Panel Right */}
            <polygon points="15,12 22,8 22,14 15,18" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.6" />

            {/* Solar Panel Boom */}
            <line x1="9" y1="7" x2="15" y2="15" stroke="#94a3b8" strokeWidth="1.2" strokeLinecap="round" />

            {/* 3D Bus Body */}
            <polygon points="9,9 15,6 18,9 12,12" fill="#f8fafc" />
            <polygon points="9,9 12,12 12,17 9,14" fill="#cbd5e1" />
            <polygon points="12,12 18,9 18,14 12,17" fill="#94a3b8" />

            {/* Dish */}
            <path d="M11 15 Q 15 19 19 16" fill="none" stroke="#76B900" strokeWidth="1.5" strokeLinecap="round" />
            <line x1="15" y1="17" x2="17" y2="20" stroke="#76B900" strokeWidth="1.2" />

            {/* Green Light Emitter Dot */}
            <circle cx="17" cy="20" r="2.2" fill="#76B900" filter="url(#satGreenGlow)" className="sat-emitter" />
            <circle cx="17" cy="20" r="0.8" fill="#FFFFFF" />
          </g>
        </g>
      </svg>

      {/* Centered Brand Text */}
      <span className="nav-mark brand-text">SkyPass</span>
    </div>
  );
}
