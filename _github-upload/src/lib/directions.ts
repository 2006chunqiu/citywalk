import type { Stop } from "@/data/routes";

// 超过这个直线距离（公里）的相邻站点不走走路线规划，直接用直线兜底
const MAX_SEGMENT_KM = 8;

interface WalkingResponse {
  status: string;
  info?: string;
  route?: {
    paths?: Array<{
      steps?: Array<{ polyline?: string }>;
    }>;
  };
}

/** "lng,lat;lng,lat" -> [[lng, lat], ...] */
function parsePolyline(polyline: string): Array<[number, number]> {
  const points: Array<[number, number]> = [];
  for (const pair of polyline.split(";")) {
    const [lng, lat] = pair.split(",").map(Number);
    if (Number.isFinite(lng) && Number.isFinite(lat)) points.push([lng, lat]);
  }
  return points;
}

function haversineKm(a: Stop, b: Stop): number {
  const R = 6371;
  const dLat = ((b.lat - a.lat) * Math.PI) / 180;
  const dLng = ((b.lng - a.lng) * Math.PI) / 180;
  const lat1 = (a.lat * Math.PI) / 180;
  const lat2 = (b.lat * Math.PI) / 180;
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** 调高德步行路径规划，返回沿道路的坐标序列；失败或距离过远返回 null */
async function walkingSegment(from: Stop, to: Stop): Promise<Array<[number, number]> | null> {
  if (haversineKm(from, to) > MAX_SEGMENT_KM) return null;

  const url =
    `/api/amapgeo/v3/direction/walking` +
    `?origin=${from.lng},${from.lat}` +
    `&destination=${to.lng},${to.lat}`;

  const res = await fetch(url);
  if (!res.ok) return null;

  const data = (await res.json()) as WalkingResponse;
  const steps = data.route?.paths?.[0]?.steps;
  if (!steps || steps.length === 0) return null;

  const coords: Array<[number, number]> = [];
  for (const step of steps) {
    if (!step.polyline) continue;
    for (const point of parsePolyline(step.polyline)) {
      const last = coords[coords.length - 1];
      if (!last || last[0] !== point[0] || last[1] !== point[1]) coords.push(point);
    }
  }

  return coords.length > 1 ? coords : null;
}

/** 把整条路线的相邻站点逐段做步行规划，拼成一条沿道路的折线 */
export async function buildWalkingPath(stops: Stop[]): Promise<Array<[number, number]>> {
  if (stops.length < 2) return stops.map((s) => [s.lng, s.lat] as [number, number]);

  const segments = await Promise.all(
    stops
      .slice(0, -1)
      .map((from, i) => walkingSegment(from, stops[i + 1]).catch(() => null))
  );

  const path: Array<[number, number]> = [];
  const pushUnique = (point: [number, number]) => {
    const last = path[path.length - 1];
    if (!last || last[0] !== point[0] || last[1] !== point[1]) path.push(point);
  };

  for (let i = 0; i < stops.length - 1; i++) {
    const a: [number, number] = [stops[i].lng, stops[i].lat];
    const b: [number, number] = [stops[i + 1].lng, stops[i + 1].lat];
    pushUnique(a);
    const segment = segments[i];
    if (segment) {
      for (const point of segment) pushUnique(point);
    }
    pushUnique(b);
  }

  return path;
}
