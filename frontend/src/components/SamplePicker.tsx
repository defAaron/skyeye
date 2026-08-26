import './SamplePicker.css'
import { SCENARIO_LABELS } from '../lib/format'
import type { Sample } from '../types'

interface SamplePickerProps {
  samples: Sample[]
  selectedId: string | null
  /** Null when an upload owns the input slot; sample rows are then locked out. */
  disabled: boolean
  onSelect: (sample: Sample) => void
}

export default function SamplePicker({
  samples,
  selectedId,
  disabled,
  onSelect,
}: SamplePickerProps) {
  if (samples.length === 0) {
    return (
      <p className="card__hint">
        The demo corpus is empty. Run the fixture download script on the backend to
        populate it, then reload this page.
      </p>
    )
  }

  return (
    <ul className="samples" aria-label="Demo corpus samples">
      {samples.map((sample) => {
        const selected = sample.id === selectedId
        return (
          <li key={sample.id}>
            <button
              type="button"
              className="sample"
              aria-pressed={selected}
              disabled={disabled}
              onClick={() => onSelect(sample)}
            >
              <span className="sample__head">
                <span className="sample__label">{sample.label}</span>
                <span
                  className={`badge badge--${sample.scenario}`}
                  title={`Scenario: ${SCENARIO_LABELS[sample.scenario] ?? sample.scenario}`}
                >
                  {SCENARIO_LABELS[sample.scenario] ?? sample.scenario}
                </span>
              </span>
              <span className="sample__meta">
                <span className="sample__dims">
                  {sample.width} × {sample.height} px
                </span>
                <span className="sample__terrain">{sample.terrain}</span>
                {sample.geo && (
                  <span className="sample__geo">demo map tag</span>
                )}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
