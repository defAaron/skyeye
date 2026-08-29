import './SamplePicker.css'
import { SCENARIO_LABELS } from '../lib/format'
import type { Sample } from '../types'

interface SamplePickerProps {
  samples: Sample[]
  selectedId: string | null
  /** True when an upload owns the input slot; sample choice is then locked out. */
  disabled: boolean
  onSelect: (sample: Sample | null) => void
}

function optionLabel(sample: Sample): string {
  const scenario = SCENARIO_LABELS[sample.scenario] ?? sample.scenario
  const parts = [
    sample.label,
    scenario,
    `${sample.width} × ${sample.height} px`,
    sample.terrain,
  ]
  if (sample.geo) parts.push('demo map tag')
  return parts.join(' · ')
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

  const selected = samples.find((sample) => sample.id === selectedId) ?? null

  return (
    <div className="samples">
      <select
        className="samples__select"
        aria-label="Demo corpus samples"
        disabled={disabled}
        value={selectedId ?? ''}
        onChange={(event) => {
          const next = samples.find((sample) => sample.id === event.target.value) ?? null
          onSelect(next)
        }}
      >
        <option value="">Choose a sample…</option>
        {samples.map((sample) => (
          <option key={sample.id} value={sample.id}>
            {optionLabel(sample)}
          </option>
        ))}
      </select>

      {selected && (
        <div className="sample">
          <div className="sample__head">
            <span className="sample__label">{selected.label}</span>
            <span
              className={`badge badge--${selected.scenario}`}
              title={`Scenario: ${SCENARIO_LABELS[selected.scenario] ?? selected.scenario}`}
            >
              {SCENARIO_LABELS[selected.scenario] ?? selected.scenario}
            </span>
          </div>
          <div className="sample__meta">
            <span className="sample__dims">
              {selected.width} × {selected.height} px
            </span>
            <span className="sample__terrain">{selected.terrain}</span>
            {selected.geo && <span className="sample__geo">demo map tag</span>}
          </div>
        </div>
      )}
    </div>
  )
}
