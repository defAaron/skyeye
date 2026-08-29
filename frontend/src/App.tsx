import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { apiBaseUrl, getHealth, SkyEyeApiError } from './api/client'
import DetectPanel from './components/DetectPanel'
import ReportIntake from './components/ReportIntake'
import SafetyBanner from './components/SafetyBanner'
import SearchArea from './components/SearchArea'
import SearchMap from './components/SearchMap'
import type { DetectResponse, ExtractResponse, GeocodeResponse, HealthResponse } from './types'

type HealthState =
  | { status: 'loading' }
  | { status: 'online'; health: HealthResponse }
  | { status: 'offline'; code: string; message: string }

function LogoMark() {
  return (
    <div className="console-nav__logo">
      <img src="/icon.png" alt="" className="console-nav__logo-img" />
    </div>
  )
}

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })
  const [searchArea, setSearchArea] = useState<GeocodeResponse | null>(null)
  const [intake, setIntake] = useState<ExtractResponse | null>(null)
  const [detectResult, setDetectResult] = useState<DetectResponse | null>(null)
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  const [pinnedId, setPinnedId] = useState<string | null>(null)

  useEffect(() => {
    let active = true

    getHealth()
      .then((result) => {
        if (active) setHealth({ status: 'online', health: result })
      })
      .catch((error: unknown) => {
        if (!active) return
        if (error instanceof SkyEyeApiError) {
          setHealth({ status: 'offline', code: error.code, message: error.message })
        } else {
          setHealth({
            status: 'offline',
            code: 'UNKNOWN',
            message: 'Unexpected error while contacting the backend.',
          })
        }
      })

    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    document.title = 'SkyEye — Detection console'
    document.body.classList.add('console-body')
    return () => {
      document.body.classList.remove('console-body')
    }
  }, [])

  const onResults = useCallback((result: DetectResponse | null) => {
    setDetectResult(result)
    setHoveredId(null)
    setPinnedId(null)
  }, [])

  const onSelect = useCallback((id: string) => {
    setPinnedId((current) => (current === id ? null : id))
  }, [])

  const activeId = hoveredId ?? pinnedId
  const origin = searchArea ? { lat: searchArea.lat, lng: searchArea.lng } : null
  const geocodeConfigured =
    health.status === 'online' ? health.health.geocode?.configured ?? false : null
  const extractConfigured =
    health.status === 'online' ? health.health.extract?.configured ?? false : null

  return (
    <div className="console">
      <div className="console-chrome">
        <SafetyBanner />

        <header className="console-nav">
          <div className="console-nav__brand">
            <LogoMark />
            <h1 className="page__title">SkyEye</h1>
          </div>
          <p className="page__eyebrow">
            <a className="page__back" href="/">
              ← SkyEye
            </a>
          </p>
        </header>
      </div>

      <div className="page">
        <p className="page__subtitle">
          Drone-altitude person detection — leads to verify, never confirmations.
        </p>

        <main className="page__main">
          <section className="card card--wide" aria-labelledby="honesty-heading">
            <h2 id="honesty-heading" className="card__title">
              What this actually runs on
            </h2>
            <p className="card__body">
              Detection runs on drone-altitude photographs, not satellite or map tiles.
              Public satellite imagery resolves at roughly 30–50 cm per pixel, which
              renders a person as 1–2 pixels — far too little signal for any detector to
              work with. SkyEye therefore never treats map tiles as detector input. The
              map below is for last-known location, a search ring, and reviewing
              projected candidate pins.
            </p>
          </section>

          <section className="card card--wide" aria-labelledby="status-heading">
            <h2 id="status-heading" className="card__title">
              Backend status
            </h2>

            {health.status === 'loading' && (
              <p className="status status--pending">
                <span className="status__dot" aria-hidden="true" />
                Checking backend…
              </p>
            )}

            {health.status === 'online' && (
              <>
                <p className="status status--online">
                  <span className="status__dot" aria-hidden="true" />
                  Backend online
                </p>
                <dl className="facts facts--bento">
                  <div className="facts__row">
                    <dt>Version</dt>
                    <dd>{health.health.version}</dd>
                  </div>
                  <div className="facts__row">
                    <dt>Model weights</dt>
                    <dd>{health.health.model.weights}</dd>
                  </div>
                  <div className="facts__row">
                    <dt>Device</dt>
                    <dd>{health.health.model.device}</dd>
                  </div>
                  <div className="facts__row">
                    <dt>Weights loaded</dt>
                    <dd>
                      {health.health.model.loaded
                        ? 'yes'
                        : 'not yet — loads lazily on first detection'}
                    </dd>
                  </div>
                  <div className="facts__row">
                    <dt>Geocoding</dt>
                    <dd>
                      {health.health.geocode?.configured
                        ? 'configured'
                        : 'not configured'}
                    </dd>
                  </div>
                  <div className="facts__row">
                    <dt>Report extract</dt>
                    <dd>
                      {health.health.extract?.configured
                        ? [
                            health.health.extract.gemini ? 'gemini' : null,
                            health.health.extract.groq ? 'groq' : null,
                          ]
                            .filter(Boolean)
                            .join(' + ') || 'configured'
                        : 'not configured'}
                    </dd>
                  </div>
                </dl>
              </>
            )}

            {health.status === 'offline' && (
              <>
                <p className="status status--offline">
                  <span className="status__dot" aria-hidden="true" />
                  Backend unreachable
                </p>
                <p className="card__body">
                  <code className="code">{health.code}</code> — {health.message}
                </p>
                <p className="card__hint">
                  {apiBaseUrl()
                    ? 'The Render API did not respond. Status 137 is an out-of-memory kill. The shipped image is ONNX Runtime (no PyTorch) and still wants Standard / 2 GB. Reload this page after the service is up.'
                    : 'Start the Flask backend on port 5001, then reload this page.'}
                </p>
              </>
            )}
          </section>

          <ReportIntake
            extractConfigured={extractConfigured}
            disabled={false}
            onExtracted={setIntake}
          />

          <SearchArea
            geocodeConfigured={geocodeConfigured}
            searchArea={searchArea}
            disabled={false}
            intake={intake}
            onGeocoded={setSearchArea}
          />

          <SearchMap
            searchArea={searchArea}
            detections={detectResult?.detections ?? []}
            activeId={activeId}
            onHover={setHoveredId}
            onSelect={onSelect}
          />

          <DetectPanel
            health={health.status === 'online' ? health.health : null}
            origin={origin}
            activeId={activeId}
            onHover={setHoveredId}
            onSelect={onSelect}
            onResults={onResults}
          />
        </main>
      </div>
    </div>
  )
}
