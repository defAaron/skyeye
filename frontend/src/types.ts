/**
 * Mirrors docs/api-contract.md. Shapes here may only change alongside that file.
 */

export interface HealthResponse {
  status: string
  version: string
  model: {
    loaded: boolean
    weights: string
    device: string
  }
  geocode: {
    configured: boolean
  }
  limits: {
    max_upload_bytes: number
    max_image_pixels: number
    allowed_types: string[]
  }
}

export type SampleScenario = 'obvious_person' | 'cluttered' | 'true_negative'

export interface Sample {
  id: string
  label: string
  scenario: SampleScenario
  width: number
  height: number
  terrain: string
  source: string
  source_url: string
  /** Several fixtures are CC BY / CC BY-SA; credit is a licence condition, not a nicety. */
  license: string
  attribution: string
  expected_min_detections: number
  image_url: string
  /** Null when the fixture is not tagged to a map location. */
  geo: SampleGeo | null
}

export interface SampleGeo {
  center_lat: number
  center_lng: number
  demo_placement: boolean
}

export interface SamplesResponse {
  samples: Sample[]
}

/** `[x_min, y_min, x_max, y_max]` in pixel space on the submitted image, origin top-left. */
export type BBoxXYXY = [number, number, number, number]

export interface Detection {
  id: string
  bbox_xyxy: BBoxXYXY
  confidence: number
  class_name: string
  /** WGS84 when the sample is georeferenced; otherwise null. Always null for uploads. */
  lat: number | null
  lng: number | null
}

export interface DetectResponse {
  image_width: number
  image_height: number
  detections: Detection[]
  meta: {
    source: 'upload' | 'sample'
    sample_id: string | null
    tiles: number
    conf_threshold: number
    inference_ms: number
    model: string
    geo: DetectGeo | null
  }
  disclaimer: string
}

export interface DetectGeo {
  center_lat: number
  center_lng: number
  gsd_m: number
  heading_deg: number
  demo_placement: boolean
}

export type LpbCategory =
  | 'child'
  | 'youth'
  | 'elderly'
  | 'elderly_hiker'
  | 'dementia'
  | 'hiker'
  | 'hunter'
  | 'unknown'

export interface GeocodeRequest {
  location_text: string
  elapsed_hours: number
  category: LpbCategory
}

export interface GeocodeResponse {
  lat: number
  lng: number
  formatted_address: string
  radius_m: number
  category: LpbCategory
  elapsed_hours: number
  lpb_note: string
}

export type ApiErrorCode =
  | 'NO_IMAGE'
  | 'AMBIGUOUS_INPUT'
  | 'UNSUPPORTED_TYPE'
  | 'INVALID_IMAGE'
  | 'SAMPLE_NOT_FOUND'
  | 'FILE_TOO_LARGE'
  | 'IMAGE_TOO_LARGE'
  | 'INFERENCE_FAILED'
  | 'MODEL_UNAVAILABLE'
  | 'EMPTY_LOCATION'
  | 'LOCATION_TOO_LONG'
  | 'INVALID_ELAPSED_HOURS'
  | 'UNKNOWN_CATEGORY'
  | 'GEOCODE_NOT_FOUND'
  | 'GEOCODE_FAILED'
  | 'GEOCODE_UNAVAILABLE'

export interface ApiError {
  error: {
    code: ApiErrorCode | string
    message: string
  }
}
