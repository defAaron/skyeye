/** Distance and bearing from last-known location to a detection pin. */

export interface LatLng {
  lat: number
  lng: number
}

const CARDINALS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const

export function haversineMeters(from: LatLng, to: LatLng): number {
  const phi1 = (from.lat * Math.PI) / 180
  const phi2 = (to.lat * Math.PI) / 180
  const dPhi = ((to.lat - from.lat) * Math.PI) / 180
  const dLambda = ((to.lng - from.lng) * Math.PI) / 180
  const a =
    Math.sin(dPhi / 2) ** 2 + Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2) ** 2
  return 2 * 6_371_000 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export function bearingDegrees(from: LatLng, to: LatLng): number {
  const phi1 = (from.lat * Math.PI) / 180
  const phi2 = (to.lat * Math.PI) / 180
  const dLambda = ((to.lng - from.lng) * Math.PI) / 180
  const y = Math.sin(dLambda) * Math.cos(phi2)
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(dLambda)
  return (Math.atan2(y, x) * 180) / Math.PI
}

export function cardinalFromBearing(bearing: number): string {
  const normalized = ((bearing % 360) + 360) % 360
  const index = Math.round(normalized / 45) % 8
  return CARDINALS[index]
}

export function formatOffset(from: LatLng, to: LatLng): string {
  const meters = haversineMeters(from, to)
  const cardinal = cardinalFromBearing(bearingDegrees(from, to))
  const distance =
    meters < 1000 ? `${Math.round(meters)} m` : `${(meters / 1000).toFixed(1)} km`
  return `${distance} ${cardinal} of last-known location`
}

export function hasGeo<T extends { lat: number | null; lng: number | null }>(
  detection: T,
): detection is T & { lat: number; lng: number } {
  return detection.lat !== null && detection.lng !== null
}
