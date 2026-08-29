import type {
  ApiError,
  ApiErrorCode,
  DetectResponse,
  ExtractRequest,
  ExtractResponse,
  GeocodeRequest,
  GeocodeResponse,
  HealthResponse,
  SamplesResponse,
} from '../types'

/** Codes the client itself raises when the failure never reached a contract response. */
export type ClientErrorCode = 'NETWORK_ERROR' | 'BAD_RESPONSE' | 'TIMEOUT' | 'CANCELLED'

export class SkyEyeApiError extends Error {
  readonly code: ApiErrorCode | ClientErrorCode | string
  readonly status: number | null

  constructor(
    code: ApiErrorCode | ClientErrorCode | string,
    message: string,
    status: number | null = null,
  ) {
    super(message)
    this.name = 'SkyEyeApiError'
    this.code = code
    this.status = status
  }
}

/** Empty in Vite dev (relative `/api` via the proxy). Render origin on Vercel. */
export function apiBaseUrl(): string {
  return (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/+$/, '')
}

/** Join a contract path such as `/api/health` to the configured API origin. */
export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${apiBaseUrl()}${normalized}`
}

/**
 * Prefix a contract-relative media path (`sample.image_url`) for the `<img>`
 * tag. Absolute http(s), blob, and data URLs are left alone.
 */
export function resolveApiUrl(path: string): string {
  if (!path) return path
  if (/^https?:\/\//i.test(path) || path.startsWith('blob:') || path.startsWith('data:')) {
    return path
  }
  return apiUrl(path)
}

function networkErrorMessage(): string {
  return apiBaseUrl()
    ? 'Could not reach the SkyEye API.'
    : 'Could not reach the SkyEye backend. Is it running on port 5001?'
}

function isApiError(body: unknown): body is ApiError {
  if (typeof body !== 'object' || body === null) return false
  const { error } = body as { error?: unknown }
  if (typeof error !== 'object' || error === null) return false
  const { code, message } = error as { code?: unknown; message?: unknown }
  return typeof code === 'string' && typeof message === 'string'
}

async function unwrap<T>(response: Response): Promise<T> {
  let body: unknown
  try {
    body = await response.json()
  } catch {
    body = undefined
  }

  if (!response.ok) {
    if (isApiError(body)) {
      throw new SkyEyeApiError(body.error.code, body.error.message, response.status)
    }
    throw new SkyEyeApiError(
      'BAD_RESPONSE',
      `Backend returned ${response.status} ${response.statusText}.`,
      response.status,
    )
  }

  if (body === undefined) {
    throw new SkyEyeApiError(
      'BAD_RESPONSE',
      'Backend returned a response that was not valid JSON.',
      response.status,
    )
  }

  return body as T
}

async function request<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(apiUrl(path), { headers: { Accept: 'application/json' } })
  } catch {
    throw new SkyEyeApiError('NETWORK_ERROR', networkErrorMessage())
  }

  return unwrap<T>(response)
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health')
}

export function getSamples(): Promise<SamplesResponse> {
  return request<SamplesResponse>('/api/samples')
}

export const EXTRACT_TIMEOUT_MS = 30_000

export async function postExtract(body: ExtractRequest): Promise<ExtractResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), EXTRACT_TIMEOUT_MS)
  try {
    let response: Response
    try {
      response = await fetch(apiUrl('/api/extract'), {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch {
      if (controller.signal.aborted) {
        throw new SkyEyeApiError(
          'TIMEOUT',
          'Report extraction took too long and was stopped.',
        )
      }
      throw new SkyEyeApiError('NETWORK_ERROR', networkErrorMessage())
    }
    return await unwrap<ExtractResponse>(response)
  } finally {
    clearTimeout(timer)
  }
}

export const GEOCODE_TIMEOUT_MS = 15_000

export async function postGeocode(body: GeocodeRequest): Promise<GeocodeResponse> {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), GEOCODE_TIMEOUT_MS)
  try {
    let response: Response
    try {
      response = await fetch(apiUrl('/api/geocode'), {
        method: 'POST',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      })
    } catch {
      if (controller.signal.aborted) {
        throw new SkyEyeApiError(
          'TIMEOUT',
          'Geocoding took too long and was stopped.',
        )
      }
      throw new SkyEyeApiError('NETWORK_ERROR', networkErrorMessage())
    }
    return await unwrap<GeocodeResponse>(response)
  } finally {
    clearTimeout(timer)
  }
}

/** Tiled CPU inference on a large frame routinely runs tens of seconds. */
export const DETECT_TIMEOUT_MS = 180_000

export interface DetectRequest {
  /** Exactly one of `file` or `sampleId`; the contract rejects both together. */
  file?: File
  sampleId?: string
  conf: number
  /** Caller-owned cancellation, layered under the client's own timeout. */
  signal?: AbortSignal
}

export async function postDetect({
  file,
  sampleId,
  conf,
  signal,
}: DetectRequest): Promise<DetectResponse> {
  if (file && sampleId) {
    throw new SkyEyeApiError(
      'AMBIGUOUS_INPUT',
      'Submit either an upload or a sample, not both.',
    )
  }
  if (!file && !sampleId) {
    throw new SkyEyeApiError('NO_IMAGE', 'Choose a sample or an image to submit.')
  }

  const form = new FormData()
  if (file) form.append('image', file)
  if (sampleId) form.append('sample_id', sampleId)
  form.append('conf', String(conf))

  // Hand-rolled rather than AbortSignal.timeout/any so a timeout stays
  // distinguishable from a user cancellation in the catch below.
  const controller = new AbortController()
  let timedOut = false
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, DETECT_TIMEOUT_MS)
  const onCallerAbort = () => controller.abort()
  signal?.addEventListener('abort', onCallerAbort)

  try {
    let response: Response
    try {
      response = await fetch(apiUrl('/api/detect'), {
        method: 'POST',
        headers: { Accept: 'application/json' },
        body: form,
        signal: controller.signal,
      })
    } catch {
      if (timedOut) {
        throw new SkyEyeApiError(
          'TIMEOUT',
          `The run passed ${Math.round(DETECT_TIMEOUT_MS / 1000)} seconds without a response and was stopped.`,
        )
      }
      if (signal?.aborted) {
        throw new SkyEyeApiError('CANCELLED', 'The run was cancelled.')
      }
      throw new SkyEyeApiError('NETWORK_ERROR', networkErrorMessage())
    }

    return await unwrap<DetectResponse>(response)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onCallerAbort)
  }
}
