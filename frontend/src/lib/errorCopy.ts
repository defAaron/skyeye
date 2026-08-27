/**
 * Human-readable copy for every error code in docs/api-contract.md, plus the codes
 * the client raises itself. The backend's own `message` is shown as supporting detail;
 * raw JSON and stack traces are never surfaced.
 */

export interface ErrorCopy {
  title: string
  hint: string
  /** Whether re-submitting the same input could plausibly succeed. */
  retryable: boolean
}

const COPY: Record<string, ErrorCopy> = {
  NO_IMAGE: {
    title: 'No image was submitted',
    hint: 'Pick a sample from the demo corpus or add your own drone-altitude photo, then run detection again.',
    retryable: false,
  },
  AMBIGUOUS_INPUT: {
    title: 'Two image sources were submitted at once',
    hint: 'Clear the current selection so exactly one image source is active, then run detection again.',
    retryable: false,
  },
  UNSUPPORTED_TYPE: {
    title: 'That file type is not supported',
    hint: 'SkyEye accepts JPEG and PNG only. Export the frame from your drone footage as a JPEG and try again.',
    retryable: false,
  },
  INVALID_IMAGE: {
    title: 'The file could not be read as an image',
    hint: 'The bytes did not decode. The file may be truncated or corrupted — try re-exporting it.',
    retryable: false,
  },
  SAMPLE_NOT_FOUND: {
    title: 'That sample is no longer available',
    hint: 'The demo corpus may have changed since this page loaded. Reload the page to refresh the sample list.',
    retryable: false,
  },
  FILE_TOO_LARGE: {
    title: 'The file is larger than the upload limit',
    hint: 'Re-export the frame at a smaller file size, or use a lower JPEG quality setting, and try again.',
    retryable: false,
  },
  IMAGE_TOO_LARGE: {
    title: 'The image has too many pixels to process',
    hint: 'Scale the image down so its total pixel count is under the limit, then try again.',
    retryable: false,
  },
  INFERENCE_FAILED: {
    title: 'The detection run failed part-way through',
    hint: 'Nothing was assessed, so treat this as no information at all — not as an all-clear. Try running it again.',
    retryable: true,
  },
  MODEL_UNAVAILABLE: {
    title: 'The detection model is not available yet',
    hint: 'The model weights are still being prepared on the server. No image can be assessed until they are ready.',
    retryable: true,
  },
  EMPTY_LOCATION: {
    title: 'No location was given',
    hint: 'Describe a last-known place — a trail name, park, or town — then geocode again.',
    retryable: false,
  },
  LOCATION_TOO_LONG: {
    title: 'That location description is too long',
    hint: 'Shorten it to a place name or address of at most 200 characters.',
    retryable: false,
  },
  INVALID_ELAPSED_HOURS: {
    title: 'Elapsed time is out of range',
    hint: 'Use a number of hours between 0.1 and 72.',
    retryable: false,
  },
  UNKNOWN_CATEGORY: {
    title: 'That subject category is not recognised',
    hint: 'Pick one of the Lost Person Behavior categories in the list.',
    retryable: false,
  },
  GEOCODE_NOT_FOUND: {
    title: 'No map location matched that description',
    hint: 'Try a more specific place name, or add the town or region.',
    retryable: true,
  },
  GEOCODE_FAILED: {
    title: 'Geocoding could not be completed',
    hint: 'The geocoding provider did not return a usable result. Try again in a moment.',
    retryable: true,
  },
  GEOCODE_UNAVAILABLE: {
    title: 'Geocoding is not available',
    hint: 'The backend has no Maps key, or the Geocoding API is not enabled for it. Detection still works without a map.',
    retryable: true,
  },
  EMPTY_REPORT: {
    title: 'No report was given',
    hint: 'Describe what you know in a few sentences — place, time, and who is missing — then extract again.',
    retryable: false,
  },
  REPORT_TOO_LONG: {
    title: 'That report is too long',
    hint: 'Shorten it to at most 4000 characters. A few sentences is enough.',
    retryable: false,
  },
  EXTRACT_INCOMPLETE: {
    title: 'No last-known place could be extracted',
    hint: 'Name a trail, park, or town in the report so a search area can be geocoded.',
    retryable: false,
  },
  EXTRACT_FAILED: {
    title: 'The report could not be extracted',
    hint: 'Neither language model returned a usable result. Try again in a moment, or fill the search-area fields by hand.',
    retryable: true,
  },
  EXTRACT_UNAVAILABLE: {
    title: 'Report extraction is not available',
    hint: 'The backend has no Gemini or Groq key. You can still type a last-known location and geocode by hand.',
    retryable: true,
  },
  TIMEOUT: {
    title: 'The request took too long and was stopped',
    hint: 'Nothing was assessed. Try again, or fill the search-area fields by hand.',
    retryable: true,
  },
  CANCELLED: {
    title: 'The detection run was cancelled',
    hint: 'Nothing was assessed. Run it again when you are ready.',
    retryable: true,
  },
  NETWORK_ERROR: {
    title: 'The SkyEye backend could not be reached',
    hint: 'Check that the backend is running on port 5001, then try again.',
    retryable: true,
  },
  BAD_RESPONSE: {
    title: 'The backend returned something unexpected',
    hint: 'The response did not match the API contract, so no result can be trusted. Try again.',
    retryable: true,
  },
}

const FALLBACK: ErrorCopy = {
  title: 'The request could not be completed',
  hint: 'Nothing was assessed. Treat this as no information rather than an all-clear, and try again.',
  retryable: true,
}

export function describeError(code: string): ErrorCopy {
  return COPY[code] ?? FALLBACK
}
