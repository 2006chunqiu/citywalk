import type { Stop } from "@/data/routes";

// 武汉三镇大致范围，超出这个范围的坐标视为无效
const WUHAN_BOUNDS = {
  minLng: 113.7,
  maxLng: 114.7,
  minLat: 30.2,
  maxLat: 30.9,
};

function inWuhan(lng: number, lat: number) {
  return (
    lng >= WUHAN_BOUNDS.minLng &&
    lng <= WUHAN_BOUNDS.maxLng &&
    lat >= WUHAN_BOUNDS.minLat &&
    lat <= WUHAN_BOUNDS.maxLat
  );
}

interface AmapPoiResponse {
  status: "1" | "0";
  info?: string;
  pois?: Array<{
    name: string;
    location: string; // "lng,lat"
    adname?: string; // 所在区
    typecode?: string;
  }>;
}

interface AmapGeocodeResponse {
  status: "1" | "0";
  info?: string;
  geocodes?: Array<{
    location: string; // "lng,lat"
    formatted_address?: string;
  }>;
}

export class GeocodeError extends Error {
  code: "MISSING_KEY" | "PROXY_ERROR" | "EMPTY" | "NETWORK";
  constructor(code: GeocodeError["code"], message: string) {
    super(message);
    this.code = code;
  }
}

async function parseLocationFromUrl(url: string): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(url);
  } catch (e) {
    throw new GeocodeError("NETWORK", `网络错误：${(e as Error).message}`);
  }

  if (res.status === 502) {
    const json = await res.json().catch(() => ({}));
    throw new GeocodeError("MISSING_KEY", json.message || "AMAP_WEB_KEY 未配置");
  }
  if (!res.ok) {
    throw new GeocodeError("PROXY_ERROR", `代理错误 ${res.status}`);
  }

  return await res.json();
}

/** 优先 POI 文本搜索（更精准），失败降级到地理编码 */
export async function geocodeAddress(address: string): Promise<{ lng: number; lat: number } | null> {
  // 1. POI 搜索
  try {
    const poiUrl = `/api/amapgeo/v3/place/text?keywords=${encodeURIComponent(address)}&city=${encodeURIComponent("武汉")}&output=json&offset=10`;
    const data = (await parseLocationFromUrl(poiUrl)) as AmapPoiResponse;
    if (data.status === "1" && data.pois && data.pois.length > 0) {
      // 优先选 typecode 以 11（风景名胜）或 19（地名地址）开头的，且在武汉范围内
      const candidates = data.pois
        .map((p) => {
          const [lngStr, latStr] = p.location.split(",");
          return {
            lng: parseFloat(lngStr),
            lat: parseFloat(latStr),
            typecode: p.typecode || "",
            name: p.name,
          };
        })
        .filter((c) => inWuhan(c.lng, c.lat) && !Number.isNaN(c.lng) && !Number.isNaN(c.lat));

      // 风景名胜(11) > 地名地址(19) > 其他
      const scenic = candidates.find((c) => c.typecode.startsWith("11"));
      if (scenic) return { lng: scenic.lng, lat: scenic.lat };
      const place = candidates.find((c) => c.typecode.startsWith("19"));
      if (place) return { lng: place.lng, lat: place.lat };
      if (candidates.length > 0) return { lng: candidates[0].lng, lat: candidates[0].lat };
    }
  } catch (e) {
    // POI 失败不阻塞，继续走地理编码
    if (e instanceof GeocodeError && e.code === "MISSING_KEY") throw e;
  }

  // 2. 降级：地理编码（拼成 "武汉+站点名" 缩小范围）
  try {
    const fullAddress = address.startsWith("武汉") ? address : `武汉${address}`;
    const geoUrl = `/api/amapgeo/v3/geocode/geo?address=${encodeURIComponent(fullAddress)}&city=${encodeURIComponent("武汉")}`;
    const data = (await parseLocationFromUrl(geoUrl)) as AmapGeocodeResponse;
    if (data.status === "1" && data.geocodes && data.geocodes.length > 0) {
      // 遍历所有候选，选第一个在武汉范围内的
      for (const g of data.geocodes) {
        const [lngStr, latStr] = g.location.split(",");
        const lng = parseFloat(lngStr);
        const lat = parseFloat(latStr);
        if (!Number.isNaN(lng) && !Number.isNaN(lat) && inWuhan(lng, lat)) {
          return { lng, lat };
        }
      }
    }
  } catch (e) {
    if (e instanceof GeocodeError && e.code === "MISSING_KEY") throw e;
  }

  return null;
}

/** 批量地理编码，静默跳过失败项，已在原位置上填充 lng/lat */
export async function geocodeStops(stops: Stop[]): Promise<{ stops: Stop[]; failed: number }> {
  let failed = 0;
  const results = await Promise.all(
    stops.map(async (stop) => {
      try {
        const coord = await geocodeAddress(stop.name);
        if (coord) {
          return { ...stop, lng: coord.lng, lat: coord.lat };
        }
        failed++;
        return null;
      } catch {
        failed++;
        return null;
      }
    })
  );

  // 给失败的站点分配一个占位坐标（围绕武汉中心散开），避免地图崩溃
  const WUHAN_CENTER = { lng: 114.305, lat: 30.593 };
  let fallbackIndex = 0;
  const fallbacks: Stop[] = [];
  for (let i = 0; i < stops.length; i++) {
    const r = results[i];
    if (r) {
      fallbacks.push(r);
    } else {
      const angle = (fallbackIndex / Math.max(stops.length, 1)) * Math.PI * 2;
      const radius = 0.008 + fallbackIndex * 0.004;
      fallbacks.push({
        ...stops[i],
        lng: WUHAN_CENTER.lng + Math.cos(angle) * radius,
        lat: WUHAN_CENTER.lat + Math.sin(angle) * radius,
      });
      fallbackIndex++;
    }
  }

  return { stops: fallbacks, failed };
}
