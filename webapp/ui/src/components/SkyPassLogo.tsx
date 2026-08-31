export function SkyPassLogo({ animated = true }: { animated?: boolean }) {
  return (
    <div className="skypass-brand">
      <div className="skypass-icon-wrap">
        <svg
          width="34"
          height="34"
          viewBox="0 0 44 44"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className={animated ? 'sat-3d-svg is-animated' : 'sat-3d-svg'}
          aria-hidden="true"
        >
          <defs>
            {/* Green glowing gradient for emitted beam */}
            <linearGradient id="satBeamGlow" x1="22" y1="26" x2="42" y2="38" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#76B900" stopOpacity="0.9" />
              <stop offset="60%" stopColor="#76B900" stopOpacity="0.35" />
              <stop offset="100%" stopColor="#76B900" stopOpacity="0" />
            </linearGradient>

            {/* Solar panel gradient */}
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

          {/* Emitted Light Cone / Beam to SkyPass text */}
          <polygon
            points="22,25 44,28 44,42 24,30"
            fill="url(#satBeamGlow)"
            className="sat-beam"
          />

          {/* 3D Solar Panel Left */}
          <polygon points="3,13 13,7 13,15 3,21" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.75" />
          <line x1="8" y1="10" x2="8" y2="18" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" />

          {/* 3D Solar Panel Right */}
          <polygon points="21,19 31,13 31,21 21,27" fill="url(#satSolarGrad)" stroke="#38bdf8" strokeWidth="0.75" />
          <line x1="26" y1="16" x2="26" y2="24" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" />

          {/* Solar Panel Connecting Boom */}
          <line x1="13" y1="11" x2="21" y2="23" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />

          {/* 3D Satellite Bus Body Cube */}
          <polygon points="13,13 21,9 25,13 17,17" fill="#f8fafc" />
          <polygon points="13,13 17,17 17,24 13,20" fill="#cbd5e1" />
          <polygon points="17,17 25,13 25,20 17,24" fill="#94a3b8" />

          {/* Parabolic Dish Antenna */}
          <path d="M16 21 Q 21 26 26 23" fill="none" stroke="#76B900" strokeWidth="2" strokeLinecap="round" />
          <line x1="21" y1="23.5" x2="24" y2="28" stroke="#76B900" strokeWidth="1.5" />

          {/* Emitter Lens (Glowing Green Dot) */}
          <circle cx="24" cy="28" r="2.5" fill="#76B900" filter="url(#satGreenGlow)" className="sat-emitter" />
          <circle cx="24" cy="28" r="1" fill="#FFFFFF" />

          {/* Light emission wave rings */}
          <circle cx="24" cy="28" r="5" fill="none" stroke="#76B900" strokeWidth="0.75" className="sat-wave wave-1" />
          <circle cx="24" cy="28" r="9" fill="none" stroke="#76B900" strokeWidth="0.5" className="sat-wave wave-2" />
        </svg>
      </div>

      <span className="nav-mark brand-text">SkyPass</span>
    </div>
  );
}
