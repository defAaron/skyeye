import { useState, type FormEvent } from 'react'
import './ReportIntake.css'
import { postExtract, SkyEyeApiError } from '../api/client'
import { describeError } from '../lib/errorCopy'
import type { ExtractResponse } from '../types'

export const DEFAULT_REPORT = `My dad went missing around 3pm near Bruce Trail, Milton.
He's 70, wearing a red jacket, last seen walking near the
conservation area entrance.`

interface ReportIntakeProps {
  extractConfigured: boolean | null
  disabled: boolean
  onExtracted: (result: ExtractResponse) => void
}

export default function ReportIntake({
  extractConfigured,
  disabled,
  onExtracted,
}: ReportIntakeProps) {
  const [report, setReport] = useState(DEFAULT_REPORT)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)
  const [extracted, setExtracted] = useState<ExtractResponse | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const result = await postExtract({ report_text: report })
      setExtracted(result)
      onExtracted(result)
    } catch (caught: unknown) {
      const code = caught instanceof SkyEyeApiError ? caught.code : 'BAD_RESPONSE'
      const message =
        caught instanceof SkyEyeApiError
          ? caught.message
          : 'Report extraction failed before returning a result.'
      setError({ code, message })
    } finally {
      setBusy(false)
    }
  }

  const copy = error ? describeError(error.code) : null
  const unavailable = extractConfigured === false
  const subjectBits = extracted
    ? [
        extracted.subject.age != null ? `age ${extracted.subject.age}` : null,
        extracted.subject.clothing,
        extracted.subject.distinguishing_features,
      ].filter(Boolean)
    : []

  return (
    <section className="card" aria-labelledby="intake-heading">
      <h2 id="intake-heading" className="card__title">
        Report intake
      </h2>
      <p className="card__body">
        Type what a caller knows in plain language. A language model extracts a
        last-known place, elapsed time, and subject category for you to review —
        it does not geocode, detect, or confirm anyone&apos;s location.
      </p>

      {unavailable && (
        <p className="notice notice--error" role="status">
          Report extraction is not configured. Add a Gemini or Groq key on the
          backend, or fill the search-area fields by hand.
        </p>
      )}

      <form className="intake-form" onSubmit={(event) => void onSubmit(event)}>
        <label className="search-form__field">
          <span className="search-form__label">Free-text report</span>
          <textarea
            className="search-form__input intake-form__textarea"
            name="report_text"
            rows={6}
            maxLength={4000}
            value={report}
            disabled={busy || disabled || unavailable}
            onChange={(event) => setReport(event.target.value)}
          />
        </label>
        <p className="card__hint">{report.trim().length} / 4000 characters</p>
        <div className="search-form__actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={busy || disabled || unavailable || !report.trim()}
          >
            {busy ? 'Extracting…' : 'Extract structured fields'}
          </button>
        </div>
      </form>

      {copy && error && (
        <p className="notice notice--error" role="alert">
          <strong>{copy.title}.</strong> {error.message} {copy.hint}
        </p>
      )}

      {extracted && (
        <>
          <dl className="facts facts--compact">
            <div className="facts__row">
              <dt>Last-known place</dt>
              <dd>{extracted.location_text}</dd>
            </div>
            <div className="facts__row">
              <dt>Time last seen</dt>
              <dd>{extracted.time_last_seen ?? 'not stated'}</dd>
            </div>
            <div className="facts__row">
              <dt>Elapsed hours</dt>
              <dd>{extracted.elapsed_hours}</dd>
            </div>
            <div className="facts__row">
              <dt>Subject category</dt>
              <dd>{extracted.subject.category}</dd>
            </div>
            <div className="facts__row">
              <dt>Description</dt>
              <dd>{subjectBits.length ? subjectBits.join(' · ') : 'not stated'}</dd>
            </div>
            <div className="facts__row">
              <dt>Terrain hint</dt>
              <dd>{extracted.terrain_hint ?? 'not stated'}</dd>
            </div>
            <div className="facts__row">
              <dt>Extractor</dt>
              <dd>{extracted.provider}</dd>
            </div>
          </dl>
          <p className="card__hint">{extracted.disclaimer}</p>
        </>
      )}
    </section>
  )
}
