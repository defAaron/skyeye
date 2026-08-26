import { useState, type FormEvent } from 'react'
import './SearchArea.css'
import { postGeocode, SkyEyeApiError } from '../api/client'
import { describeError } from '../lib/errorCopy'
import type { GeocodeResponse, LpbCategory } from '../types'

const CATEGORIES: { id: LpbCategory; label: string }[] = [
  { id: 'elderly_hiker', label: 'Elderly hiker' },
  { id: 'elderly', label: 'Elderly' },
  { id: 'dementia', label: 'Dementia / wanderer' },
  { id: 'child', label: 'Child (1–6)' },
  { id: 'youth', label: 'Youth (7–12)' },
  { id: 'hiker', label: 'Hiker' },
  { id: 'hunter', label: 'Hunter' },
  { id: 'unknown', label: 'Unknown / unspecified' },
]

const DEFAULT_LOCATION = 'Bruce Trail, Milton, Ontario'
const DEFAULT_HOURS = 4.5
const DEFAULT_CATEGORY: LpbCategory = 'elderly_hiker'

interface SearchAreaProps {
  geocodeConfigured: boolean | null
  searchArea: GeocodeResponse | null
  disabled: boolean
  onGeocoded: (result: GeocodeResponse) => void
}

export default function SearchArea({
  geocodeConfigured,
  searchArea,
  disabled,
  onGeocoded,
}: SearchAreaProps) {
  const [location, setLocation] = useState(DEFAULT_LOCATION)
  const [hours, setHours] = useState(String(DEFAULT_HOURS))
  const [category, setCategory] = useState<LpbCategory>(DEFAULT_CATEGORY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<{ code: string; message: string } | null>(null)

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    const elapsed = Number(hours)
    setBusy(true)
    setError(null)
    try {
      const result = await postGeocode({
        location_text: location,
        elapsed_hours: elapsed,
        category,
      })
      onGeocoded(result)
    } catch (caught: unknown) {
      const code = caught instanceof SkyEyeApiError ? caught.code : 'BAD_RESPONSE'
      const message =
        caught instanceof SkyEyeApiError
          ? caught.message
          : 'Geocoding failed before returning a result.'
      setError({ code, message })
    } finally {
      setBusy(false)
    }
  }

  const copy = error ? describeError(error.code) : null
  const unavailable = geocodeConfigured === false

  return (
    <section className="card" aria-labelledby="search-heading">
      <h2 id="search-heading" className="card__title">
        Search area
      </h2>
      <p className="card__body">
        Geocode a last-known location and size a search ring from elapsed time and
        subject category. This is a simplified Lost Person Behavior heuristic — it
        does not confirm where anyone is, and it does not run detection. Map tiles
        are never detector input.
      </p>

      {unavailable && (
        <p className="notice notice--error" role="status">
          Geocoding is not configured on the backend. Detection still works; the map
          stays empty until a Maps key is present.
        </p>
      )}

      <form className="search-form" onSubmit={(event) => void onSubmit(event)}>
        <label className="search-form__field">
          <span className="search-form__label">Last-known location</span>
          <input
            className="search-form__input"
            type="text"
            name="location_text"
            maxLength={200}
            value={location}
            disabled={busy || disabled || unavailable}
            autoComplete="off"
            onChange={(event) => setLocation(event.target.value)}
          />
        </label>

        <div className="search-form__row">
          <label className="search-form__field">
            <span className="search-form__label">Hours since last seen</span>
            <input
              className="search-form__input search-form__input--narrow"
              type="number"
              name="elapsed_hours"
              min={0.1}
              max={72}
              step={0.1}
              value={hours}
              disabled={busy || disabled || unavailable}
              onChange={(event) => setHours(event.target.value)}
            />
          </label>

          <label className="search-form__field search-form__field--grow">
            <span className="search-form__label">Subject category</span>
            <select
              className="search-form__input"
              name="category"
              value={category}
              disabled={busy || disabled || unavailable}
              onChange={(event) => setCategory(event.target.value as LpbCategory)}
            >
              {CATEGORIES.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="search-form__actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={busy || disabled || unavailable || !location.trim()}
          >
            {busy ? 'Geocoding…' : 'Geocode search area'}
          </button>
        </div>
      </form>

      {copy && error && (
        <p className="notice notice--error" role="alert">
          <strong>{copy.title}.</strong> {error.message} {copy.hint}
        </p>
      )}

      {searchArea && (
        <dl className="facts facts--compact">
          <div className="facts__row">
            <dt>Matched place</dt>
            <dd>{searchArea.formatted_address}</dd>
          </div>
          <div className="facts__row">
            <dt>Coordinates</dt>
            <dd>
              {searchArea.lat.toFixed(5)}, {searchArea.lng.toFixed(5)}
            </dd>
          </div>
          <div className="facts__row">
            <dt>Search radius</dt>
            <dd>{searchArea.radius_m.toLocaleString()} m</dd>
          </div>
          <div className="facts__row">
            <dt>Category / elapsed</dt>
            <dd>
              {searchArea.category} · {searchArea.elapsed_hours} h
            </dd>
          </div>
        </dl>
      )}
      {searchArea && <p className="card__hint">{searchArea.lpb_note}</p>}
    </section>
  )
}
