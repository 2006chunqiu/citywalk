/** 地球半径（米） */
const R = 6378137

const rad = (d) => (d * Math.PI) / 180

/** 两点球面距离，单位米 */
export function haversineM(a, b) {
  if (!a || !b || a.lng == null || b.lng == null) return 0
  const dLat = rad(b.lat - a.lat)
  const dLng = rad(b.lng - a.lng)
  const s =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(s))
}

/** 点到折线的最短距离（米），用于偏航判定 */
export function distanceToPolyline(point, path) {
  if (!path || path.length < 2) return 0
  let min = Infinity
  for (let i = 0; i < path.length - 1; i++) {
    const d = distanceToSegment(point, path[i], path[i + 1])
    if (d < min) min = d
  }
  return min
}

/** 点到线段的最短距离（局部平面近似，适合公里级范围） */
export function distanceToSegment(p, a, b) {
  const kx = Math.cos(rad(p.lat)) * 111320
  const ky = 110540
  const px = (p.lng - a.lng) * kx
  const py = (p.lat - a.lat) * ky
  const bx = (b.lng - a.lng) * kx
  const by = (b.lat - a.lat) * ky
  const len2 = bx * bx + by * by
  if (len2 === 0) return Math.hypot(px, py)
  let t = (px * bx + py * by) / len2
  t = Math.max(0, Math.min(1, t))
  return Math.hypot(px - t * bx, py - t * by)
}

/** 米转可读文本 */
export function fmtDistance(m) {
  if (m < 1000) return `${Math.round(m)} 米`
  return `${(m / 1000).toFixed(1)} 公里`
}

/** 秒转可读文本 */
export function fmtDuration(s) {
  const h = Math.floor(s / 3600)
  const m = Math.round((s % 3600) / 60)
  return h ? `${h} 小时 ${m} 分钟` : `${m} 分钟`
}
