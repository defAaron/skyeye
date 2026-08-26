import { useEffect, useState } from 'react'
import './App.css'
import { getHealth, SkyEyeApiError } from './api/client'
import DetectPanel from './components/DetectPanel'
import SafetyBanner from './components/SafetyBanner'
import type { HealthResponse } from './types'

type HealthState =
  | { status: 'loading' }
  | { status: 'online'; health: HealthResponse }
  | { status: 'offline'; code: string; message: string }

export default function App() {
  const [health, setHealth] = useState<HealthState>({ status: 'loading' })

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

  return (
    <>
      <SafetyBanner />

      <div className="page">
        <header className="page__header">
          <h1 className="page__title">SkyEye</h1>
          <p className="page__subtitle">
            Drone-altitude person detection — leads to verify, never confirmations.
          </p>
        </header>

        <main className="page__main">
          <section className="card" aria-labelledby="honesty-heading">
            <h2 id="honesty-heading" className="card__title">
              What this actually runs on
            </h2>
            <p className="card__body">
              Detection runs on drone-altitude photographs, not satellite or map tiles.
              Public satellite imagery resolves at roughly 30–50 cm per pixel, which
              renders a person as 1–2 pixels — far too little signal for any detector to
              work with. SkyEye therefore never treats map tiles as detector input.
            </p>
          </section>

          <section className="card" aria-labelledby="status-heading">
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
                <dl className="facts">
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
                  Start the Flask backend on port 5001, then reload this page.
                </p>
              </>
            )}
          </section>

          <DetectPanel health={health.status === 'online' ? health.health : null} />
        </main>
      </div>
    </>
  )
}
