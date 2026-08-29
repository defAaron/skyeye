import { useEffect } from 'react'
import {
  APILoadingStatus,
  APIProvider,
  Circle,
  ColorScheme,
  Map,
  Marker,
  useApiLoadingStatus,
  useMap,
} from '@vis.gl/react-google-maps'
import './SearchArea.css'
import { hasGeo } from '../lib/geo'
import type { Detection, GeocodeResponse } from '../types'

const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined

const MAPS_JS_HINT =
  'On the project that owns this browser key: enable Maps JavaScript API, link billing, and set HTTP referrers to https://skyeye-one.vercel.app/* and http://localhost:5173/* (the /* is required). Then open DevTools → Console and look for “Google Maps JavaScript API error: …MapError”.'

interface SearchMapProps {
  searchArea: GeocodeResponse | null
  detections: Detection[]
  activeId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}

export default function SearchMap({
  searchArea,
  detections,
  activeId,
  onHover,
  onSelect,
}: SearchMapProps) {
  const pins = detections.filter(hasGeo)

  return (
    <section className="card card--wide" aria-labelledby="map-heading">
      <h2 id="map-heading" className="card__title">
        Map
      </h2>
      <p className="card__body">
        Last-known location and the search ring live here. Candidate pins appear only
        when a georeferenced demo sample is run — they are projected from pixel boxes,
        not GPS from an aircraft. Satellite tiles are not scanned for people.
      </p>

      {!MAPS_KEY && (
        <p className="notice notice--error" role="status">
          No Maps JavaScript key is loaded. Add <code>VITE_GOOGLE_MAPS_API_KEY</code> to{' '}
          <code>frontend/.env.local</code> and restart Vite.
        </p>
      )}

      {MAPS_KEY && !searchArea && (
        <p className="card__hint">
          Geocode a last-known location above to draw the search area.
        </p>
      )}

      {MAPS_KEY && searchArea && (
        <div className="search-map">
          <APIProvider apiKey={MAPS_KEY} authReferrerPolicy="origin">
            <MapAuthBanner />
            <Map
              className="search-map__frame"
              defaultCenter={{ lat: searchArea.lat, lng: searchArea.lng }}
              defaultZoom={13}
              colorScheme={ColorScheme.LIGHT}
              gestureHandling="greedy"
              mapTypeId="roadmap"
              clickableIcons={false}
            >
              <FitToSearch area={searchArea} pins={pins} />
              <Circle
                center={{ lat: searchArea.lat, lng: searchArea.lng }}
                radius={searchArea.radius_m}
                strokeColor="#0c2461"
                strokeOpacity={0.9}
                strokeWeight={2}
                fillColor="#0c2461"
                fillOpacity={0.12}
                clickable={false}
              />
              <Marker
                position={{ lat: searchArea.lat, lng: searchArea.lng }}
                title="Last-known location (geocoded) — not a detection"
              />
              {pins.map((detection, index) => (
                <Marker
                  key={detection.id}
                  position={{ lat: detection.lat, lng: detection.lng }}
                  label={String(index + 1)}
                  title={`Candidate ${index + 1} — ${(detection.confidence * 100).toFixed(1)}% confidence — lead to verify`}
                  zIndex={detection.id === activeId ? 200 : 50}
                  onClick={() => onSelect(detection.id)}
                  onMouseOver={() => onHover(detection.id)}
                  onMouseOut={() => onHover(null)}
                />
              ))}
            </Map>
          </APIProvider>
        </div>
      )}

      {searchArea && pins.length === 0 && (
        <p className="card__hint">
          No candidate pins yet. Run detection on a demo sample tagged to this area
          (lawn or woodland fixtures) to project boxes onto the map. Beach samples
          are not tagged.
        </p>
      )}
    </section>
  )
}

function MapAuthBanner() {
  const status = useApiLoadingStatus()
  if (status !== APILoadingStatus.AUTH_FAILURE && status !== APILoadingStatus.FAILED) {
    return null
  }
  return (
    <p className="notice notice--error search-map__auth" role="status">
      Google Maps JavaScript did not load. {MAPS_JS_HINT}
    </p>
  )
}

function FitToSearch({
  area,
  pins,
}: {
  area: GeocodeResponse
  pins: Array<{ lat: number; lng: number }>
}) {
  const map = useMap()
  const pinKey = pins.map((pin) => `${pin.lat.toFixed(6)},${pin.lng.toFixed(6)}`).join('|')

  useEffect(() => {
    if (!map) return
    const dLat = area.radius_m / 111_320
    const cosLat = Math.max(Math.cos((area.lat * Math.PI) / 180), 1e-6)
    const dLng = area.radius_m / (111_320 * cosLat)
    const bounds = {
      north: area.lat + dLat,
      south: area.lat - dLat,
      east: area.lng + dLng,
      west: area.lng - dLng,
    }
    for (const pin of pins) {
      bounds.north = Math.max(bounds.north, pin.lat)
      bounds.south = Math.min(bounds.south, pin.lat)
      bounds.east = Math.max(bounds.east, pin.lng)
      bounds.west = Math.min(bounds.west, pin.lng)
    }
    map.fitBounds(bounds, 56)
  }, [map, area.lat, area.lng, area.radius_m, pinKey, pins])

  return null
}
