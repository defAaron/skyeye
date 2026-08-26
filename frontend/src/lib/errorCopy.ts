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
  TIMEOUT: {
    title: 'The detection run took too long and was stopped',
    hint: 'Tiled inference on the CPU is slow on very large images. Nothing was assessed. Try again, or submit a smaller image.',
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
  title: 'Detection could not be completed',
  hint: 'Nothing was assessed. Treat this as no information rather than an all-clear, and try again.',
  retryable: true,
}

export function describeError(code: string): ErrorCopy {
  return COPY[code] ?? FALLBACK
}
