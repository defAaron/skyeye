import { useCallback, useEffect, useRef, useState } from 'react'
import './DetectPanel.css'
import {
  DETECT_TIMEOUT_MS,
  getSamples,
  postDetect,
  resolveApiUrl,
  SkyEyeApiError,
} from '../api/client'
import { describeError } from '../lib/errorCopy'
import { formatBytes, formatPercent, formatSeconds, safeHttpUrl } from '../lib/format'
import type { DetectResponse, HealthResponse, Sample } from '../types'
import type { LatLng } from '../lib/geo'
import DetectionList from './DetectionList'
import DetectionOverlay from './DetectionOverlay'
import SamplePicker from './SamplePicker'
import UploadZone, { type UploadRejection } from './UploadZone'

const DEFAULT_CONF = 0.25
const CONF_MIN = 0.01
const CONF_MAX = 0.95
const FALLBACK_MAX_UPLOAD_BYTES = 26_214_400
const FALLBACK_ALLOWED_TYPES = ['image/jpeg', 'image/png']

type SamplesState =
  | { status: 'loading' }
  | { status: 'ready'; samples: Sample[] }
  | { status: 'error'; code: string; message: string }

/** What was actually submitted, frozen so results never drift from the picker. */
interface Subject {
  src: string
  alt: string
  sample: Sample | null
  fileName: string | null
}

interface LastRequest {
  file?: File
  sampleId?: string
  conf: number
}

type RunState =
  | { status: 'idle' }
  | { status: 'running'; startedAt: number }
  | { status: 'done'; result: DetectResponse; subject: Subject }
  | {
      status: 'error'
      code: string
      message: string
      /** Carried so a retry replays exactly what was submitted. */
      request: LastRequest
      subject: Subject
    }

interface DetectPanelProps {
  health: HealthResponse | null
  origin: LatLng | null
  activeId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
  onResults: (result: DetectResponse | null) => void
}

export default function DetectPanel({
  health,
  origin,
  activeId,
  onHover,
  onSelect,
  onResults,
}: DetectPanelProps) {
  const [samplesState, setSamplesState] = useState<SamplesState>({ status: 'loading' })
  const [selectedSample, setSelectedSample] = useState<Sample | null>(null)
  const [upload, setUpload] = useState<{ file: File; previewUrl: string } | null>(null)
  const [inputError, setInputError] = useState<UploadRejection | null>(null)
  const [conf, setConf] = useState(DEFAULT_CONF)
  const [run, setRun] = useState<RunState>({ status: 'idle' })
  const [tick, setTick] = useState(0)

  const abortRef = useRef<AbortController | null>(null)
  const objectUrlsRef = useRef<string[]>([])

  const maxUploadBytes = health?.limits.max_upload_bytes ?? FALLBACK_MAX_UPLOAD_BYTES
  const allowedTypes = health?.limits.allowed_types ?? FALLBACK_ALLOWED_TYPES

  useEffect(() => {
    let active = true
    getSamples()
      .then((result) => {
        if (active) setSamplesState({ status: 'ready', samples: result.samples })
      })
      .catch((error: unknown) => {
        if (!active) return
        const code = error instanceof SkyEyeApiError ? error.code : 'BAD_RESPONSE'
        const message =
          error instanceof SkyEyeApiError ? error.message : 'Could not load the demo corpus.'
        setSamplesState({ status: 'error', code, message })
      })
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    const urls = objectUrlsRef.current
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
      abortRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    if (run.status !== 'running') return
    const timer = window.setInterval(() => setTick(Date.now()), 250)
    return () => window.clearInterval(timer)
  }, [run.status])

  const elapsedMs = run.status === 'running' ? Math.max(0, tick - run.startedAt) : 0

  const submit = useCallback(async (request: LastRequest, subject: Subject) => {
    const controller = new AbortController()
    abortRef.current = controller
    setRun({ status: 'running', startedAt: Date.now() })
    onResults(null)

    try {
      const result = await postDetect({ ...request, signal: controller.signal })
      setRun({ status: 'done', result, subject })
      onResults(result)
    } catch (error: unknown) {
      const code = error instanceof SkyEyeApiError ? error.code : 'BAD_RESPONSE'
      const message =
        error instanceof SkyEyeApiError
          ? error.message
          : 'The detection run failed before returning a result.'
      setRun({ status: 'error', code, message, request, subject })
    } finally {
      abortRef.current = null
    }
  }, [onResults])

  function chooseSample(sample: Sample | null) {
    setInputError(null)
    setSelectedSample(sample)
  }

  function acceptUpload(file: File) {
    setInputError(null)
    const previewUrl = URL.createObjectURL(file)
    // Superseded previews are kept alive until unmount on purpose: a finished run may
    // still be rendering its overlay from an earlier blob URL.
    objectUrlsRef.current.push(previewUrl)
    setUpload({ file, previewUrl })
  }

  function clearInput() {
    setSelectedSample(null)
    setUpload(null)
    setInputError(null)
  }

  function onDetect() {
    if (selectedSample) {
      void submit(
        { sampleId: selectedSample.id, conf },
        {
          src: resolveApiUrl(selectedSample.image_url),
          alt: `Sample imagery: ${selectedSample.label}`,
          sample: selectedSample,
          fileName: null,
        },
      )
      return
    }
    if (upload) {
      void submit(
        { file: upload.file, conf },
        {
          src: upload.previewUrl,
          alt: `Submitted image: ${upload.file.name}`,
          sample: null,
          fileName: upload.file.name,
        },
      )
    }
  }

  const previewSrc = selectedSample
    ? resolveApiUrl(selectedSample.image_url)
    : upload?.previewUrl ?? null
  const previewAlt = selectedSample
    ? `Sample imagery: ${selectedSample.label}`
    : upload
      ? `Selected image: ${upload.file.name}`
      : ''
  const hasInput = Boolean(selectedSample || upload)
  const running = run.status === 'running'
  const errorCopy = run.status === 'error' ? describeError(run.code) : null

  return (
    <>
      <section className="card card--wide" aria-labelledby="detect-heading">
        <h2 id="detect-heading" className="card__title">
          Detect
        </h2>
        <p className="card__body">
          Submit one drone-altitude frame. SkyEye returns person-shaped candidates ranked
          by confidence for a human to verify — it never confirms that a person is
          present.
        </p>

        <div className="detect__bento">
          <div className="detect__group">
            <h3 className="detect__legend">1 — Choose a sample from the demo corpus</h3>
          {samplesState.status === 'loading' && (
            <p className="card__hint">Loading the demo corpus…</p>
          )}
          {samplesState.status === 'error' && (
            <p className="notice notice--error">
              {describeError(samplesState.code).title}. {samplesState.message}
            </p>
          )}
          {samplesState.status === 'ready' && (
            <SamplePicker
              samples={samplesState.samples}
              selectedId={selectedSample?.id ?? null}
              disabled={running || Boolean(upload)}
              onSelect={chooseSample}
            />
          )}
          {upload && (
            <p className="card__hint">
              Sample selection is locked while your own image is loaded — only one image
              source can be submitted at a time.
            </p>
          )}
        </div>

        <div className="detect__group">
          <h3 className="detect__legend">2 — Or add your own image</h3>
          <UploadZone
            allowedTypes={allowedTypes}
            maxUploadBytes={maxUploadBytes}
            disabled={running || Boolean(selectedSample)}
            onAccept={acceptUpload}
            onReject={(rejection) => {
              setUpload(null)
              setInputError(rejection)
            }}
          />
          {inputError && (
            <p className="notice notice--error" role="alert">
              <strong>{describeError(inputError.code).title}.</strong>{' '}
              {inputError.message} {describeError(inputError.code).hint}
            </p>
          )}
        </div>

        <div className="detect__group detect__group--run">
          <h3 className="detect__legend">3 — Set the confidence floor and run</h3>

          <div className="selection" aria-live="polite">
            {hasInput ? (
              <>
                <span className="selection__text">
                  Ready to submit:{' '}
                  <strong>
                    {selectedSample ? selectedSample.label : upload?.file.name}
                  </strong>
                  {selectedSample ? (
                    <span className="selection__sub">
                      {' '}
                      · sample · {selectedSample.width} × {selectedSample.height} px
                    </span>
                  ) : (
                    upload && (
                      <span className="selection__sub">
                        {' '}
                        · your upload · {formatBytes(upload.file.size)}
                      </span>
                    )
                  )}
                </span>
                <button
                  type="button"
                  className="button button--ghost"
                  disabled={running}
                  onClick={clearInput}
                >
                  Clear selection
                </button>
              </>
            ) : (
              <span className="selection__text selection__text--empty">
                Nothing selected yet. Choose one sample or add one image.
              </span>
            )}
          </div>

          {previewSrc && (
            <img className="detect__preview" src={previewSrc} alt={previewAlt} />
          )}

          <div className="conf">
            <label className="conf__label" htmlFor="conf-slider">
              Confidence floor
            </label>
            <input
              id="conf-slider"
              className="conf__slider"
              type="range"
              min={CONF_MIN}
              max={CONF_MAX}
              step={0.01}
              value={conf}
              disabled={running}
              onChange={(event) => setConf(Number(event.target.value))}
            />
            <input
              className="conf__number"
              type="number"
              min={CONF_MIN}
              max={CONF_MAX}
              step={0.01}
              value={conf}
              disabled={running}
              aria-label="Confidence floor, numeric"
              onChange={(event) => {
                const next = Number(event.target.value)
                if (Number.isFinite(next)) {
                  setConf(Math.min(CONF_MAX, Math.max(CONF_MIN, next)))
                }
              }}
            />
            <span className="conf__value">{formatPercent(conf)}</span>
          </div>
          <p className="card__hint">
            Candidates scoring below this floor are not returned. Lowering it surfaces
            weaker, noisier candidates; raising it hides all but the strongest. Default is{' '}
            {formatPercent(DEFAULT_CONF)}.
          </p>

          <div className="detect__actions">
            <button
              type="button"
              className="button button--primary"
              disabled={!hasInput || running}
              onClick={onDetect}
            >
              {running ? 'Running detection…' : 'Detect candidates'}
            </button>
            {running && (
              <button
                type="button"
                className="button button--ghost"
                onClick={() => abortRef.current?.abort()}
              >
                Cancel run
              </button>
            )}
          </div>
        </div>
        </div>
      </section>

      {running && (
        <section className="card card--wide" aria-labelledby="running-heading" aria-live="polite">
          <h2 id="running-heading" className="card__title">
            Running
          </h2>
          <div className="running">
            <span className="spinner" aria-hidden="true" />
            <div>
              <p className="running__lead">
                Tiled inference in progress — {(elapsedMs / 1000).toFixed(1)} s elapsed
              </p>
              <p className="card__hint">
                Large frames are split into hundreds of overlapping tiles and scored one
                at a time on the CPU. Ten seconds to well over a minute is normal. The run
                stops itself after {Math.round(DETECT_TIMEOUT_MS / 1000)} seconds.
              </p>
            </div>
          </div>
        </section>
      )}

      {run.status === 'error' && errorCopy && (
        <section className="card card--wide card--error" aria-labelledby="error-heading">
          <h2 id="error-heading" className="card__title">
            Run did not complete
          </h2>
          <p className="notice notice--error" role="alert">
            <strong>{errorCopy.title}.</strong> {run.message}
          </p>
          <p className="card__hint">{errorCopy.hint}</p>
          {errorCopy.retryable && (
            <div className="detect__actions">
              <button
                type="button"
                className="button button--primary"
                onClick={() => void submit(run.request, run.subject)}
              >
                Try the run again
              </button>
            </div>
          )}
        </section>
      )}

      {run.status === 'done' && (
        <ResultsCard
          result={run.result}
          subject={run.subject}
          origin={origin}
          activeId={activeId}
          onHover={onHover}
          onSelect={onSelect}
        />
      )}
    </>
  )
}

interface ResultsCardProps {
  result: DetectResponse
  subject: Subject
  origin: LatLng | null
  activeId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}

function ResultsCard({
  result,
  subject,
  origin,
  activeId,
  onHover,
  onSelect,
}: ResultsCardProps) {
  const { detections, meta } = result
  const count = detections.length
  const sourceLink = safeHttpUrl(subject.sample?.source_url)

  return (
    <section className="card card--wide" aria-labelledby="results-heading">
      <h2 id="results-heading" className="card__title">
        Candidates for review
      </h2>

      <p className="card__body">
        {count === 0
          ? 'No candidates above the confidence threshold.'
          : `${count} person-shaped ${count === 1 ? 'candidate' : 'candidates'} to verify, strongest first.`}
      </p>

      <DetectionOverlay
        imageSrc={subject.src}
        imageAlt={subject.alt}
        imageWidth={result.image_width}
        imageHeight={result.image_height}
        detections={detections}
        activeId={activeId}
        onHover={onHover}
        onSelect={onSelect}
      />

      {count === 0 ? (
        <div className="notice notice--empty">
          <p>
            <strong>Nothing scored at or above the {formatPercent(meta.conf_threshold)} confidence
            floor in this frame.</strong>
          </p>
          <p>
            That is a statement about the detector, not about the ground. It does{' '}
            <strong>not</strong> mean nobody is there. A person can be under canopy, in
            shadow, partly buried, in unusual posture, or simply too few pixels across for
            this model at this altitude. Search this area by other means regardless.
          </p>
          <p>
            Lowering the confidence floor will surface weaker candidates, at the cost of
            more noise to review.
          </p>
        </div>
      ) : (
        <>
          <DetectionList
            detections={detections}
            activeId={activeId}
            origin={origin}
            onHover={onHover}
            onSelect={onSelect}
          />
          <p className="card__hint">
            Every row above is an unverified possible lead. Pass promising leads to 911 or
            your local SAR coordinator — they decide what happens next.
          </p>
        </>
      )}

      {result.meta.geo?.demo_placement && (
        <p className="notice notice--empty">
          Map pins for this sample are a <strong>demo placement</strong> on the Bruce
          Trail / Milton conservation area. This photograph was not captured there.
          Pixel boxes are projected with an assumed ground sample distance so they can
          be reviewed on the map — they are not GPS from an aircraft.
        </p>
      )}

      <p className="disclaimer" role="note">
        {result.disclaimer}
      </p>

      {subject.sample && (
        <p className="credit">
          Sample imagery: {subject.sample.source} · {subject.sample.license} ·{' '}
          {subject.sample.attribution}
          {sourceLink && (
            <>
              {' · '}
              <a
                className="credit__link"
                href={sourceLink}
                target="_blank"
                rel="noopener noreferrer"
              >
                source page
              </a>
            </>
          )}
        </p>
      )}

      <dl className="facts facts--compact">
        <div className="facts__row">
          <dt>Tiles processed</dt>
          <dd>{meta.tiles}</dd>
        </div>
        <div className="facts__row">
          <dt>Confidence floor used</dt>
          <dd>
            {meta.conf_threshold} ({formatPercent(meta.conf_threshold)})
          </dd>
        </div>
        <div className="facts__row">
          <dt>Inference time</dt>
          <dd>
            {formatSeconds(meta.inference_ms)} ({meta.inference_ms} ms)
          </dd>
        </div>
        <div className="facts__row">
          <dt>Model</dt>
          <dd>{meta.model}</dd>
        </div>
        <div className="facts__row">
          <dt>Image source</dt>
          <dd>{meta.source === 'sample' ? (meta.sample_id ?? 'sample') : 'upload'}</dd>
        </div>
        <div className="facts__row">
          <dt>Image size</dt>
          <dd>
            {result.image_width} × {result.image_height} px
          </dd>
        </div>
      </dl>
    </section>
  )
}
