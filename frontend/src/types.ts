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
  /** Reserved for the later geocoding layer; always null in this phase. */
  lat: number | null
  /** Reserved for the later geocoding layer; always null in this phase. */
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
  }
  disclaimer: string
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

export interface ApiError {
  error: {
    code: ApiErrorCode | string
    message: string
  }
}
