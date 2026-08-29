import { useEffect, useState } from 'react'
import { SAFETY_DISCLAIMER } from '../components/SafetyBanner'
import GlobeScene from './GlobeScene'
import './LandingPage.css'

const stats = [
  { value: '< 30s', label: 'Time-to-first-lead target' },
  { value: 'LPB', label: 'Search-radius heuristic' },
  { value: 'YOLOv8', label: 'Tiled drone-altitude detect' },
]

const features = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="lp-icon" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.25 15a4.5 4.5 0 004.5 4.5H18a3.75 3.75 0 001.332-7.257 3 3 0 00-3.758-3.848 5.25 5.25 0 00-10.233 2.33A4.502 4.502 0 002.25 15z"
        />
      </svg>
    ),
    title: 'Report Intake',
    desc: 'A free-text missing-person report is extracted into structured facts: last-known place, elapsed time, clothing, and terrain hints.',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="lp-icon" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M7.5 3.75H6A2.25 2.25 0 003.75 6v1.5M16.5 3.75H18A2.25 2.25 0 0120.25 6v1.5m0 9V18A2.25 2.25 0 0118 20.25h-1.5m-9 0H6A2.25 2.25 0 013.75 18v-1.5M15 12a3 3 0 11-6 0 3 3 0 016 0z"
        />
      </svg>
    ),
    title: 'Search Ring',
    desc: 'Last-known location is geocoded and sized with a simplified Lost Person Behavior radius — a starting ring for responders, not an operational plan.',
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" className="lp-icon" stroke="currentColor" strokeWidth={1.5}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.348 14.652a3.75 3.75 0 010-5.304m5.304 0a3.75 3.75 0 010 5.304m-7.425 2.121a6.75 6.75 0 010-9.546m9.546 0a6.75 6.75 0 010 9.546M5.106 18.894c-3.808-3.807-3.808-9.981 0-13.789m13.788 0c3.808 3.808 3.808 9.982 0 13.79M12 12h.008v.007H12V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"
        />
      </svg>
    ),
    title: 'Aerial Detection',
    desc: 'Tiled YOLOv8 scans drone-altitude photographs for person-shaped candidates and returns ranked, scored boxes for a human to verify.',
  },
]

const steps = [
  {
    step: '01',
    title: 'Report Received',
    desc: 'A caller or coordinator describes what they know in plain language — place, time, clothing, and who is missing.',
  },
  {
    step: '02',
    title: 'Extract & Ring',
    desc: 'An LLM structures the report. The last-known point is geocoded and a Lost Person Behavior search ring is drawn on the map.',
  },
  {
    step: '03',
    title: 'Imagery Scanned',
    desc: 'Detection runs on drone-altitude photographs — not satellite or map tiles, which cannot resolve a person.',
  },
  {
    step: '04',
    title: 'Leads to Verify',
    desc: 'Ranked candidates appear as boxes and map pins. Confidence is always shown. Nothing is reported as found or confirmed.',
  },
]

function LogoMark({ size }: { size: 'nav' | 'foot' }) {
  return (
    <div className={`lp-logo-mark lp-logo-mark--${size}`}>
      <svg viewBox="0 0 24 24" fill="none" className={`lp-logo-svg lp-logo-svg--${size}`} stroke="currentColor" strokeWidth={2}>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"
        />
      </svg>
    </div>
  )
}

export default function LandingPage() {
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    document.title = 'SkyEye — AI-assisted missing person search'
    document.body.classList.add('lp-body')
    return () => {
      document.body.classList.remove('lp-body')
    }
  }, [])

  return (
    <div className="lp">
      <nav className="lp-nav">
        <div className="lp-brand">
          <LogoMark size="nav" />
          <span className="lp-brand-name">SkyEye</span>
        </div>
        <div className="lp-nav-links">
          <a href="#technology">Technology</a>
          <a href="#how">How It Works</a>
          <a href="#console">Console</a>
        </div>
        <a href="/app" className="lp-btn lp-btn--primary lp-nav-cta">
          Open console
        </a>
        <button
          type="button"
          className="lp-menu-toggle"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
          onClick={() => setMenuOpen(!menuOpen)}
        >
          <svg viewBox="0 0 24 24" fill="none" className="lp-menu-icon" stroke="currentColor" strokeWidth={2}>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d={menuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'}
            />
          </svg>
        </button>
      </nav>

      {menuOpen && (
        <div className="lp-mobile-menu">
          <a href="#technology" onClick={() => setMenuOpen(false)}>
            Technology
          </a>
          <a href="#how" onClick={() => setMenuOpen(false)}>
            How It Works
          </a>
          <a href="#console" onClick={() => setMenuOpen(false)}>
            Console
          </a>
          <a href="/app" className="lp-btn lp-btn--primary lp-mobile-cta" onClick={() => setMenuOpen(false)}>
            Open console
          </a>
        </div>
      )}

      <section className="lp-hero">
        <div className="lp-hero-copy">
          <div className="lp-badge">
            <span className="lp-badge-dot" />
            <span className="lp-badge-text">Leads to verify</span>
          </div>

          <h1 className="lp-hero-title">
            Every Second
            <br />
            <span className="lp-hero-title-muted">Counts.</span>
          </h1>

          <p className="lp-hero-body">
            SkyEye compresses SAR triage: extract a free-text report, draw a Lost Person Behavior
            search ring, and scan drone-altitude photographs for person-shaped candidates. It does
            not replace SAR teams, dispatch, or law enforcement.
          </p>

          <div className="lp-hero-actions">
            <a href="#how" className="lp-btn lp-btn--primary lp-btn--lg">
              See how it works
              <svg viewBox="0 0 16 16" fill="none" className="lp-btn-arrow" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 8h10M9 4l4 4-4 4" />
              </svg>
            </a>
            <a href="/app" className="lp-btn lp-btn--ghost lp-btn--lg">
              Open the console
            </a>
          </div>

          <div className="lp-stats">
            {stats.map((s) => (
              <div key={s.label}>
                <div className="lp-stat-value">{s.value}</div>
                <div className="lp-stat-label">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="lp-hero-globe">
          <div className="lp-globe-mount">
            <GlobeScene />
          </div>
          <div className="lp-globe-labels">
            <div className="lp-chip">
              <div className="lp-chip-kicker">Detection input</div>
              <div className="lp-chip-value">Drone-altitude photos</div>
            </div>
            <div className="lp-chip lp-chip--right">
              <div className="lp-chip-kicker">Not scanned</div>
              <div className="lp-chip-value">Satellite / map tiles</div>
            </div>
          </div>
        </div>
      </section>

      <section id="technology" className="lp-section">
        <div className="lp-section-inner lp-tech-grid">
          <div>
            <p className="lp-kicker">Core Technology</p>
            <h2 className="lp-section-title">
              Precision
              <br />
              at Scale
            </h2>
          </div>
          <div className="lp-feature-grid">
            {features.map((f) => (
              <div key={f.title} className="lp-feature">
                <div className="lp-feature-icon">{f.icon}</div>
                <h3 className="lp-feature-title">{f.title}</h3>
                <p className="lp-feature-desc">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how" className="lp-section lp-section--tint">
        <div className="lp-section-inner">
          <p className="lp-kicker">Pipeline</p>
          <h2 className="lp-section-title lp-section-title--spaced">How SkyEye Works</h2>
          <div className="lp-steps">
            {steps.map((s) => (
              <div key={s.step} className="lp-step">
                <div className="lp-step-num">{s.step}</div>
                <h3 className="lp-step-title">{s.title}</h3>
                <p className="lp-step-desc">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="console" className="lp-section">
        <div className="lp-cta">
          <p className="lp-kicker">The console</p>
          <h2 className="lp-cta-title">
            Start a
            <br />
            Search
          </h2>
          <p className="lp-cta-body">
            Open the working tool: paste a report, draw a Lost Person Behavior ring, and run
            detection on drone-altitude photographs. Every output is a lead to verify.
          </p>
          <a href="/app" className="lp-btn lp-btn--primary lp-btn--lg">
            Open the console
          </a>
        </div>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-brand">
          <LogoMark size="foot" />
          <span className="lp-footer-name">SkyEye</span>
        </div>
        <p className="lp-footer-copy">
          © 2026 SkyEye. RescueHacks — Emergency Response / Community Rescue.
        </p>
        <p className="lp-footer-disclaimer">{SAFETY_DISCLAIMER}</p>
      </footer>
    </div>
  )
}
