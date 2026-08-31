export function SkyPassLogo({ animated = true }: { animated?: boolean }) {
  return (
    <div className="skypass-orbit-brand">
      {/* Dashed Ellipse Orbit Track */}
      <svg className="skypass-orbit-ring" width="170" height="44" viewBox="0 0 170 44" fill="none" aria-hidden="true">
        <ellipse
          cx="85"
          cy="22"
          rx="80"
          ry="15"
          transform="rotate(-6 85 22)"
          fill="none"
          stroke="var(--accent)"
          strokeWidth="1.25"
          strokeDasharray="4 4"
          className="orbit-ellipse-line"
        />
      </svg>

      {/* Orbiting Satellite Figure locked to exact ellipse and pointing to SkyPass */}
      <div className={animated ? 'sat-orbit-mover is-animated' : 'sat-orbit-mover'}>
        <svg
          width="32"
          height="32"
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

            <linearGradient id="satBeamCone" x1="0" y1="0" x2="0" y2="100%">
              <stop offset="0%" stopColor="rgba(163, 230, 53, 0.55)" />
              <stop offset="100%" stopColor="rgba(118, 185, 0, 0)" />
            </linearGradient>

            <filter id="satGreenGlow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Green signal beam emitted from 22,22 straight down (+y). That axis is the one
              the orbit keyframes rotate, so it always faces the SkyPass text at the ellipse centre. */}
          <polygon points="22,22 14,44 30,44" fill="url(#satBeamCone)" className="sat-beam-cone" />
          <line x1="22" y1="22" x2="22" y2="44" stroke="#76B900" strokeWidth="2.5" strokeDasharray="3 2" className="sat-beam-line" />

          {/* 3D Solar Panel Left */}
          <polygon points="3,13 13,7 13,15 3,21" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.6" />

          {/* 3D Solar Panel Right — lifted clear of the beam cone below the bus */}
          <polygon points="25,11 35,5 35,13 25,19" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.6" />

          {/* Solar Panel Boom (bus is drawn over its midsection for depth) */}
          <line x1="12" y1="12" x2="26" y2="14" stroke="#94a3b8" strokeWidth="1.2" strokeLinecap="round" />

          {/* 3D Bus Body */}
          <polygon points="13,13 21,9 25,13 17,17" fill="#f8fafc" />
          <polygon points="13,13 17,17 17,24 13,20" fill="#cbd5e1" />
          <polygon points="17,17 25,13 25,20 17,24" fill="#94a3b8" />

          {/* Parabolic dish mounted under the bus, mouth facing down the beam axis */}
          <path d="M15 23 Q 22 14 29 23" fill="rgba(118, 185, 0, 0.18)" stroke="#76B900" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          <line x1="22" y1="17" x2="22" y2="22" stroke="#94a3b8" strokeWidth="1" strokeLinecap="round" />

          {/* Glowing Green Emitter Lens */}
          <circle cx="22" cy="22" r="2.5" fill="#76B900" filter="url(#satGreenGlow)" className="sat-emitter" />
          <circle cx="22" cy="22" r="1" fill="#FFFFFF" />
        </svg>
      </div>

      {/* Centered Brand Text */}
      <span className="nav-mark brand-text">SkyPass</span>
    </div>
  );
}
