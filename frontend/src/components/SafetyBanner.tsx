import './SafetyBanner.css'

/**
 * Always rendered, never dismissible. The wording is fixed by the API contract's
 * `disclaimer` field and must stay identical.
 */
export const SAFETY_DISCLAIMER =
  "SkyEye surfaces possible leads only. It does not confirm a person's location or safety. Contact 911 / local SAR immediately."

export default function SafetyBanner() {
  return (
    <div className="safety-banner" role="alert" aria-live="assertive">
      <span className="safety-banner__mark" aria-hidden="true">
        !
      </span>
      <p className="safety-banner__text">{SAFETY_DISCLAIMER}</p>
    </div>
  )
}
