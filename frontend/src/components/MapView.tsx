import { useEffect, useRef } from "react";
import * as L from "leaflet";
import "leaflet/dist/leaflet.css";
import { amapMarkerUrl, type Route } from "@/data/routes";

interface MapViewProps {
  route: Route | null;
  path?: Array<[number, number]> | null;
  activeStop: number | null;
  onSelectStop: (index: number) => void;
  onError?: () => void;
}

const WUHAN_CENTER: [number, number] = [30.593, 114.305];
const TILE_URL =
  "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}";

function escapeHtml(text: string) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function popupHtml(route: Route, index: number) {
  const stop = route.stops[index];
  return `
    <div style="min-width:200px;font-family:inherit">
      <div style="display:flex;justify-content:space-between;gap:8px;font-size:10px;color:#7a7a72">
        <span>第 ${index + 1} 站 · ${escapeHtml(stop.kind)}</span>
        <span>${escapeHtml(stop.stay)}</span>
      </div>
      <h4 style="margin:4px 0 0;font-size:15px;font-weight:600">${escapeHtml(stop.name)}</h4>
      <p style="margin:6px 0 0;font-size:11px;line-height:1.6;color:#5f5f57">${escapeHtml(
        stop.desc,
      )}</p>
      <a href="${amapMarkerUrl(stop)}" target="_blank" rel="noreferrer"
         style="display:inline-block;margin-top:10px;padding:5px 10px;border-radius:999px;background:#14524c;color:#fff;font-size:11px;text-decoration:none">
        高德导航到这里
      </a>
    </div>`;
}

export function MapView({
  route,
  path,
  activeStop,
  onSelectStop,
  onError,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const layerRef = useRef<L.LayerGroup | null>(null);
  const markersRef = useRef<L.Marker[]>([]);
  const routeRef = useRef<Route | null>(null);
  routeRef.current = route;

  // 初始化地图（只做一次）
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: WUHAN_CENTER,
      zoom: 12,
      zoomControl: false,
      attributionControl: true,
    });

    const tiles = L.tileLayer(TILE_URL, {
      subdomains: ["1", "2", "3", "4"],
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.amap.com/">高德地图</a>',
    }).addTo(map);

    let tileErrors = 0;
    tiles.on("tileerror", () => {
      tileErrors += 1;
      if (tileErrors >= 6) onError?.();
    });

    L.control
      .zoom({ position: "bottomright", zoomInTitle: "放大", zoomOutTitle: "缩小" })
      .addTo(map);

    mapRef.current = map;
    layerRef.current = L.layerGroup().addTo(map);

    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
      markersRef.current = [];
    };
  }, [onError]);

  // 画路线和站点
  useEffect(() => {
    const map = mapRef.current;
    const layer = layerRef.current;
    if (!map || !layer) return;

    layer.clearLayers();
    markersRef.current = [];

    if (!route || route.stops.length === 0) return;

    const coords: Array<[number, number]> =
      path && path.length > 1
        ? path.map(([lng, lat]) => [lat, lng] as [number, number])
        : route.stops.map((s) => [s.lat, s.lng] as [number, number]);

    const line = L.polyline(coords, {
      color: route.color,
      weight: 6,
      opacity: 0.82,
      lineJoin: "round",
    }).addTo(layer);

    route.stops.forEach((stop, index) => {
      const icon = L.divIcon({
        className: "",
        iconSize: [30, 30],
        iconAnchor: [15, 15],
        popupAnchor: [0, -14],
        html: `<div style="width:30px;height:30px;border-radius:999px;background:${route.color};border:2px solid #fff;color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center;box-shadow:0 8px 16px -8px rgba(0,0,0,.6)">${index + 1}</div>`,
      });

      const marker = L.marker([stop.lat, stop.lng], { icon })
        .addTo(layer)
        .bindPopup(popupHtml(route, index), { maxWidth: 260, closeButton: true });

      marker.on("click", () => onSelectStop(index));
      markersRef.current.push(marker);
    });

    map.fitBounds(line.getBounds(), { padding: [40, 40], maxZoom: 16 });
  }, [route, path, onSelectStop]);

  // 选中站点时聚焦并打开气泡
  useEffect(() => {
    const map = mapRef.current;
    const marker = activeStop !== null ? markersRef.current[activeStop] : null;
    if (!map || !marker || !routeRef.current) return;

    map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 15.5), { duration: 0.5 });
    marker.openPopup();
  }, [activeStop]);

  return <div ref={containerRef} className="h-full w-full" />;
}
