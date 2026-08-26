export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const mb = bytes / (1024 * 1024)
  if (mb < 1) return `${Math.round(bytes / 1024)} KB`
  return `${mb.toFixed(1)} MB`
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`
}

export function formatSeconds(ms: number): string {
  const seconds = ms / 1000
  return seconds >= 10 ? `${Math.round(seconds)} s` : `${seconds.toFixed(1)} s`
}

/** Only http(s) may reach an href; a `javascript:` or `data:` URL in metadata must not. */
export function safeHttpUrl(candidate: string | null | undefined): string | null {
  if (!candidate) return null
  try {
    const url = new URL(candidate, window.location.origin)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}

export const SCENARIO_LABELS: Record<string, string> = {
  obvious_person: 'obvious person',
  cluttered: 'cluttered',
  true_negative: 'true negative',
}
