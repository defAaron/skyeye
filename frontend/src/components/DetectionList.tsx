import './DetectionList.css'
import { formatPercent } from '../lib/format'
import type { Detection } from '../types'
import { formatOffset, type LatLng } from '../lib/geo'

interface DetectionListProps {
  /** Already ranked by confidence descending by the API; never re-sorted here. */
  detections: Detection[]
  activeId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
  origin: LatLng | null
}

export default function DetectionList({
  detections,
  activeId,
  onHover,
  onSelect,
  origin,
}: DetectionListProps) {
  return (
    <ol className="candidates" aria-label="Candidates ranked by confidence, highest first">
      {detections.map((detection, index) => {
        const [x1, y1, x2, y2] = detection.bbox_xyxy
        const active = detection.id === activeId
        return (
          <li key={detection.id}>
            <button
              type="button"
              className={`candidate${active ? ' candidate--active' : ''}`}
              aria-pressed={active}
              onMouseEnter={() => onHover(detection.id)}
              onMouseLeave={() => onHover(null)}
              onFocus={() => onHover(detection.id)}
              onBlur={() => onHover(null)}
              onClick={() => onSelect(detection.id)}
            >
              <span className="candidate__rank" aria-hidden="true">
                {index + 1}
              </span>
              <span className="candidate__body">
                <span className="candidate__headline">
                  Candidate {index + 1} — {formatPercent(detection.confidence)} confidence
                  <span className="candidate__raw">
                    (raw {detection.confidence.toFixed(4)})
                  </span>
                </span>
                <span className="candidate__facts">
                  <span>
                    Pixel location: x {x1}–{x2}, y {y1}–{y2}
                  </span>
                  <span>
                    Box size: {x2 - x1} × {y2 - y1} px
                  </span>
                  {origin &&
                    detection.lat !== null &&
                    detection.lng !== null && (
                      <span>
                        {formatOffset(origin, { lat: detection.lat, lng: detection.lng })}
                      </span>
                    )}
                </span>
                <span className="candidate__note">
                  Person-shaped candidate. Requires human verification.
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}
