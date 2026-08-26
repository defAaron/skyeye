import './DetectionOverlay.css'
import type { Detection } from '../types'

interface DetectionOverlayProps {
  imageSrc: string
  imageAlt: string
  /** Pixel dimensions of the submitted image; also the SVG user-coordinate space. */
  imageWidth: number
  imageHeight: number
  detections: Detection[]
  activeId: string | null
  onHover: (id: string | null) => void
  onSelect: (id: string) => void
}

export default function DetectionOverlay({
  imageSrc,
  imageAlt,
  imageWidth,
  imageHeight,
  detections,
  activeId,
  onHover,
  onSelect,
}: DetectionOverlayProps) {
  // A reticle around the active box: candidates are often only a few dozen pixels
  // wide in a 4000 px frame, which is a couple of screen pixels once scaled down.
  const reticleInset = Math.max(imageWidth, imageHeight) * 0.012

  return (
    <div className="overlay">
      <div
        className="overlay__frame"
        style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}
      >
        <img className="overlay__image" src={imageSrc} alt={imageAlt} />

        <svg
          className="overlay__svg"
          viewBox={`0 0 ${imageWidth} ${imageHeight}`}
          preserveAspectRatio="xMidYMid meet"
          aria-hidden="true"
        >
          {detections.map((detection, index) => {
            const [x1, y1, x2, y2] = detection.bbox_xyxy
            const active = detection.id === activeId
            return (
              <g
                key={detection.id}
                className={`box${active ? ' box--active' : ''}`}
                onMouseEnter={() => onHover(detection.id)}
                onMouseLeave={() => onHover(null)}
                onClick={() => onSelect(detection.id)}
              >
                {active && (
                  <rect
                    className="box__reticle"
                    x={x1 - reticleInset}
                    y={y1 - reticleInset}
                    width={x2 - x1 + reticleInset * 2}
                    height={y2 - y1 + reticleInset * 2}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                <rect
                  className="box__rect"
                  x={x1}
                  y={y1}
                  width={Math.max(x2 - x1, 1)}
                  height={Math.max(y2 - y1, 1)}
                  vectorEffect="non-scaling-stroke"
                />
                <title>
                  Candidate {index + 1} — {(detection.confidence * 100).toFixed(1)}%
                  confidence, requires verification
                </title>
              </g>
            )
          })}
        </svg>

        {detections.map((detection, index) => {
          const [x1, y1] = detection.bbox_xyxy
          const active = detection.id === activeId
          return (
            <span
              key={detection.id}
              className={`overlay__tag${active ? ' overlay__tag--active' : ''}`}
              style={{
                left: `${(x1 / imageWidth) * 100}%`,
                top: `${(y1 / imageHeight) * 100}%`,
              }}
              aria-hidden="true"
            >
              {index + 1}
            </span>
          )
        })}
      </div>
    </div>
  )
}
